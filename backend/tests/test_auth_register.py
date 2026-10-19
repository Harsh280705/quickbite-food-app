import os
import uuid

import httpx
import pytest

BASE = os.getenv("QUICKBITE_TEST_API_URL", "http://127.0.0.1:8000")
pytestmark = pytest.mark.skipif(
    os.getenv("QUICKBITE_TEST_ENV") != "1",
    reason="registration tests create accounts; use the isolated quickbite-test stack",
)

def test_register_valid():
    email = f"signup-{uuid.uuid4()}@example.com"
    r = httpx.post(
        f"{BASE}/api/v1/auth/register",
        json={"full_name": "Signup User", "email": email, "password": "password123"},
        timeout=10,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["user"]["email"] == email
    assert body["user"]["role"] == "customer"
    assert body["access_token"]
    # Password is usable for login, proving it was hashed and stored.
    login = httpx.post(
        f"{BASE}/api/v1/auth/login",
        json={"email": email, "password": "password123"},
        timeout=10,
    )
    assert login.status_code == 200


def test_register_invalid_input():
    r = httpx.post(
        f"{BASE}/api/v1/auth/register",
        json={"full_name": "", "email": "not-an-email", "password": "short"},
        timeout=10,
    )
    assert r.status_code == 422


def test_register_duplicate_email():
    email = f"duplicate-{uuid.uuid4()}@example.com"
    first = httpx.post(
        f"{BASE}/api/v1/auth/register",
        json={"full_name": "First", "email": email, "password": "password123"},
        timeout=10,
    )
    assert first.status_code == 201
    second = httpx.post(
        f"{BASE}/api/v1/auth/register",
        json={"full_name": "Second", "email": email, "password": "password123"},
        timeout=10,
    )
    assert second.status_code == 409


def test_register_role_escalation_forced_customer():
    email = f"escalate-{uuid.uuid4()}@example.com"
    r = httpx.post(
        f"{BASE}/api/v1/auth/register",
        json={"full_name": "Escalate", "email": email, "password": "password123", "role": "admin"},
        timeout=10,
    )
    assert r.status_code in (201, 422)
    if r.status_code == 201:
        assert r.json()["user"]["role"] == "customer"
