"""Password hashing and signed access tokens.

Strategy (documented in docs/API_CONTRACT.md):
- Passwords: PBKDF2-HMAC-SHA256 (RFC 8018) with a per-user random salt,
  240 000 iterations and a versioned, self-describing stored string.
- Tokens: JWT (HS256) signed with a server-side secret, with validated
  ``sub``/``role``/``iss``/``iat``/``exp`` claims and a bounded clock skew.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from typing import Any

import jwt
from passlib.hash import pbkdf2_sha256

from app.core.config import settings
from app.core.errors import AppError

PBKDF2_ITERATIONS = 240_000
_LEGACY_ALGORITHM = "pbkdf2_sha256"
_MAX_CLOCK_SKEW_SECONDS = 60


# --------------------------------------------------------------------------- #
# Password hashing
# --------------------------------------------------------------------------- #
def hash_password(password: str) -> str:
    """Hash with Passlib's established PBKDF2-SHA256 implementation."""
    return pbkdf2_sha256.using(rounds=PBKDF2_ITERATIONS).hash(password)


def verify_password(password: str, stored: str) -> bool:
    """Verify Passlib hashes and legacy custom hashes without invalidating users."""
    if stored.startswith(f"{_LEGACY_ALGORITHM}$"):
        try:
            _, iterations_s, salt_b64, hash_b64 = stored.split("$")
            iterations = int(iterations_s)
            if not 1 <= iterations <= 1_000_000:
                return False
            salt = base64.b64decode(salt_b64, validate=True)
            expected = base64.b64decode(hash_b64, validate=True)
            candidate = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), salt, iterations
            )
            return hmac.compare_digest(candidate, expected)
        except (ValueError, TypeError):
            return False
    try:
        return pbkdf2_sha256.verify(password, stored)
    except (ValueError, TypeError):
        return False


def password_hash_needs_upgrade(stored: str) -> bool:
    """Return whether a successful login should migrate the stored hash."""
    if stored.startswith(f"{_LEGACY_ALGORITHM}$"):
        return True
    try:
        return pbkdf2_sha256.needs_update(stored)
    except (ValueError, TypeError):
        return True


# --------------------------------------------------------------------------- #
# Access tokens
# --------------------------------------------------------------------------- #
def create_access_token(*, user_id: str, role: str) -> tuple[str, int]:
    """Create a signed access token. Returns ``(token, expires_in_seconds)``."""
    now = int(time.time())
    expires_in = settings.jwt_access_token_expire_minutes * 60
    payload: dict[str, Any] = {
        "sub": user_id,
        "role": role,
        "iss": settings.jwt_issuer,
        "iat": now,
        "exp": now + expires_in,
        "typ": "access",
    }
    token = jwt.encode(
        payload, settings.jwt_secret, algorithm=settings.jwt_algorithm
    )
    return token, expires_in


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate token claims. Raises AppError(401) on any failure."""
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            leeway=_MAX_CLOCK_SKEW_SECONDS,
            options={"require": ["sub", "role", "exp", "iat", "iss", "typ"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AppError(401, "token_expired", "Access token has expired") from exc
    except jwt.InvalidIssuerError as exc:
        raise AppError(401, "token_invalid", "Invalid token issuer") from exc
    except jwt.PyJWTError as exc:
        raise AppError(401, "token_invalid", "Access token is invalid") from exc

    if claims.get("typ") != "access":
        raise AppError(401, "token_invalid", "Unsupported token type")
    if claims.get("role") not in ("customer", "admin"):
        raise AppError(401, "token_invalid", "Token role claim is not valid")
    return claims
