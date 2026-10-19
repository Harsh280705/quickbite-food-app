"""Authentication service: login and current-user resolution."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    password_hash_needs_upgrade,
    verify_password,
)
from app.models import User

logger = logging.getLogger("quickbite.auth")


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email.lower()))
    return result.scalar_one_or_none()


async def authenticate(
    session: AsyncSession, *, email: str, password: str
) -> tuple[User, str, int]:
    """Verify credentials and issue an access token.

    The same error is returned for unknown users and bad passwords so the
    endpoint cannot be used to enumerate accounts.  Passwords and tokens are
    never logged.
    """
    user = await get_user_by_email(session, email)
    if user is None or not user.is_active or not verify_password(
        password, user.password_hash if user else ""
    ):
        raise AppError(
            401,
            "invalid_credentials",
            "Email or password is incorrect",
        )
    if password_hash_needs_upgrade(user.password_hash):
        # Upgrade legacy hashes only after a successful password check. This
        # preserves existing accounts and never requires access to plaintext.
        user.password_hash = hash_password(password)
        await session.commit()
    token, expires_in = create_access_token(user_id=str(user.id), role=user.role)
    logger.info("login_success", extra={"user_id": str(user.id), "role": user.role})
    return user, token, expires_in


async def resolve_user_from_claims(
    session: AsyncSession, claims: dict
) -> User:
    """Load the user for a validated token; enforce active status."""
    user = await session.get(User, claims["sub"])
    if user is None:
        raise AppError(401, "invalid_credentials", "Account no longer exists")
    if not user.is_active:
        raise AppError(401, "account_disabled", "Account is disabled")
    return user


async def decode_and_load_user(session: AsyncSession, token: str) -> User:
    claims = decode_access_token(token)
    return await resolve_user_from_claims(session, claims)


async def register(
    session, *, email: str, password: str, full_name: str
) -> tuple:
    existing = await get_user_by_email(session, email)
    if existing is not None:
        raise AppError(409, "email_already_registered", "An account with this email already exists")
    user = User(
        email=email.lower().strip(),
        full_name=full_name.strip(),
        role="customer",
        password_hash=hash_password(password),
        is_active=True,
    )
    session.add(user)
    await session.flush()
    await session.commit()
    await session.refresh(user)
    token, expires_in = create_access_token(user_id=str(user.id), role=user.role)
    return user, token, expires_in
