import asyncio
import base64
import hashlib
from types import SimpleNamespace
from unittest.mock import AsyncMock
import sys
import uuid

import pytest

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.core.errors import AppError
from app.core.security import (
    hash_password,
    password_hash_needs_upgrade,
    verify_password,
)
from app.models import User
from app.services.auth_service import authenticate


def _legacy_hash(password: str) -> str:
    salt = b"legacy-user-salt"
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 240_000)
    return "$".join(
        (
            "pbkdf2_sha256",
            "240000",
            base64.b64encode(salt).decode(),
            base64.b64encode(digest).decode(),
        )
    )


def test_passlib_hash_round_trips_and_uses_configured_rounds():
    encoded = hash_password("CorrectHorseBatteryStaple")
    assert encoded.startswith("$pbkdf2-sha256$240000$")
    assert verify_password("CorrectHorseBatteryStaple", encoded)
    assert not verify_password("incorrect", encoded)
    assert not password_hash_needs_upgrade(encoded)


def test_legacy_hash_remains_valid_and_is_marked_for_upgrade():
    encoded = _legacy_hash("legacy-password")
    assert verify_password("legacy-password", encoded)
    assert not verify_password("wrong-password", encoded)
    assert password_hash_needs_upgrade(encoded)


def test_malformed_hash_is_rejected():
    assert not verify_password("password", "pbkdf2_sha256$not-a-valid-hash")


@pytest.mark.asyncio
async def test_successful_legacy_login_migrates_hash_without_resetting_account():
    user = User(
        id=uuid.uuid4(),
        email="legacy@example.test",
        full_name="Legacy Account",
        role="customer",
        is_active=True,
        password_hash=_legacy_hash("legacy-password"),
    )
    session = AsyncMock()
    session.execute.return_value = SimpleNamespace(
        scalar_one_or_none=lambda: user
    )

    authenticated_user, token, expires_in = await authenticate(
        session, email=user.email, password="legacy-password"
    )

    assert authenticated_user is user
    assert token
    assert expires_in > 0
    assert session.commit.await_count == 1
    assert user.password_hash.startswith("$pbkdf2-sha256$240000$")
    assert verify_password("legacy-password", user.password_hash)


@pytest.mark.asyncio
async def test_failed_legacy_login_does_not_migrate_or_commit():
    user = User(
        id=uuid.uuid4(),
        email="legacy@example.test",
        full_name="Legacy Account",
        role="customer",
        is_active=True,
        password_hash=_legacy_hash("legacy-password"),
    )
    original_hash = user.password_hash
    session = AsyncMock()
    session.execute.return_value = SimpleNamespace(
        scalar_one_or_none=lambda: user
    )

    with pytest.raises(AppError) as error:
        await authenticate(session, email=user.email, password="wrong-password")

    assert error.value.status_code == 401
    assert session.commit.await_count == 0
    assert user.password_hash == original_hash
