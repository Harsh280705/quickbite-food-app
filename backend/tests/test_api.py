import uuid
import os
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

BASE = os.getenv("QUICKBITE_TEST_API_URL", "http://127.0.0.1:8000")
pytestmark = pytest.mark.skipif(
    os.getenv("QUICKBITE_TEST_ENV") != "1",
    reason="API tests create records; start the isolated quickbite-test stack and set QUICKBITE_TEST_ENV=1",
)


def login(email, password):
    r = httpx.post(f"{BASE}/api/v1/auth/login", json={"email": email, "password": password}, timeout=10)
    return r


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def customer_token():
    r = login("demo@quickbite.example", "DemoPass123!")
    assert r.status_code == 200
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_token():
    r = login("admin@quickbite.example", "AdminPass123!")
    assert r.status_code == 200
    return r.json()["access_token"]


def test_health():
    r = httpx.get(f"{BASE}/health/live", timeout=5)
    assert r.status_code == 200
    r2 = httpx.get(f"{BASE}/health/ready", timeout=5)
    assert r2.status_code == 200


def test_login_invalid():
    r = login("demo@quickbite.example", "wrong")
    assert r.status_code in (401, 400, 422)


def test_unauth_me():
    r = httpx.get(f"{BASE}/api/v1/me", timeout=5)
    assert r.status_code == 401


def test_customer_cannot_admin(customer_token):
    r = httpx.get(f"{BASE}/api/v1/admin/orders", headers=auth_headers(customer_token), timeout=5)
    assert r.status_code == 403


def test_restaurants_paginated(customer_token):
    r = httpx.get(f"{BASE}/api/v1/restaurants", headers=auth_headers(customer_token),
                  params={"page": 1, "page_size": 2}, timeout=5)
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) >= {"items", "page", "page_size", "total"}
    assert body["page"] == 1
    assert body["page_size"] == 2


def test_max_page_size(customer_token):
    r = httpx.get(f"{BASE}/api/v1/restaurants", headers=auth_headers(customer_token),
                  params={"page": 1, "page_size": 101}, timeout=5)
    assert r.status_code == 422


def test_catalog_requires_authentication():
    assert httpx.get(f"{BASE}/api/v1/restaurants", timeout=5).status_code == 401


def test_checkout_idempotency_replay(customer_token):
    # get a restaurant + menu item
    rests = httpx.get(f"{BASE}/api/v1/restaurants", headers=auth_headers(customer_token),
                      params={"page": 1, "page_size": 1}, timeout=5).json()
    rid = rests["items"][0]["id"]
    menu = httpx.get(f"{BASE}/api/v1/restaurants/{rid}/menu", headers=auth_headers(customer_token),
                    params={"page": 1, "page_size": 1}, timeout=5).json()
    mid = menu["items"][0]["id"]
    key = f"test-idem-{uuid.uuid4()}"
    payload = {"restaurant_id": rid, "delivery_address": "123 Test St, Bangalore 560001", "items": [{"menu_item_id": mid, "quantity": 1}]}
    r1 = httpx.post(f"{BASE}/api/v1/orders", headers={**auth_headers(customer_token), "Idempotency-Key": key},
                    json=payload, timeout=10)
    assert r1.status_code == 202
    oid1 = r1.json()["order_id"]
    loc1 = r1.headers.get("location")
    r2 = httpx.post(f"{BASE}/api/v1/orders", headers={**auth_headers(customer_token), "Idempotency-Key": key},
                    json=payload, timeout=10)
    assert r2.status_code == 202
    assert r2.json()["order_id"] == oid1
    assert r2.headers.get("location") == loc1


def test_checkout_idempotency_conflict(customer_token):
    rests = httpx.get(f"{BASE}/api/v1/restaurants", headers=auth_headers(customer_token),
                      params={"page": 1, "page_size": 1}, timeout=5).json()
    rid = rests["items"][0]["id"]
    menu = httpx.get(f"{BASE}/api/v1/restaurants/{rid}/menu", headers=auth_headers(customer_token),
                    params={"page": 1, "page_size": 1}, timeout=5).json()
    mid = menu["items"][0]["id"]
    key = f"test-conflict-{uuid.uuid4()}"
    payload = {"restaurant_id": rid, "delivery_address": "123 Test St, Bangalore 560001", "items": [{"menu_item_id": mid, "quantity": 1}]}
    r1 = httpx.post(f"{BASE}/api/v1/orders", headers={**auth_headers(customer_token), "Idempotency-Key": key},
                    json=payload, timeout=10)
    assert r1.status_code == 202
    payload2 = {"restaurant_id": rid, "delivery_address": "999 Other St, Bangalore 560001", "items": [{"menu_item_id": mid, "quantity": 2}]}
    r2 = httpx.post(f"{BASE}/api/v1/orders", headers={**auth_headers(customer_token), "Idempotency-Key": key},
                    json=payload2, timeout=10)
    assert r2.status_code == 409


def test_concurrent_identical_checkout_creates_one_order(customer_token):
    rests = httpx.get(
        f"{BASE}/api/v1/restaurants", headers=auth_headers(customer_token),
        params={"page": 1, "page_size": 1}, timeout=5,
    ).json()
    restaurant_id = rests["items"][0]["id"]
    menu = httpx.get(
        f"{BASE}/api/v1/restaurants/{restaurant_id}/menu",
        headers=auth_headers(customer_token), params={"page": 1, "page_size": 1}, timeout=5,
    ).json()
    menu_item_id = menu["items"][0]["id"]
    key = f"concurrent-{uuid.uuid4()}"
    payload = {
        "restaurant_id": restaurant_id,
        "delivery_address": "123 Test St, Bangalore 560001",
        "items": [{"menu_item_id": menu_item_id, "quantity": 1}],
    }

    def submit():
        return httpx.post(
            f"{BASE}/api/v1/orders",
            headers={**auth_headers(customer_token), "Idempotency-Key": key},
            json=payload,
            timeout=15,
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(pool.map(lambda _: submit(), range(8)))
    assert all(response.status_code == 202 for response in responses)
    assert len({response.json()["order_id"] for response in responses}) == 1


def test_mixed_restaurant_rejected(customer_token):
    rests = httpx.get(f"{BASE}/api/v1/restaurants", headers=auth_headers(customer_token),
                      params={"page": 1, "page_size": 2}, timeout=5).json()
    if len(rests["items"]) < 2:
        pytest.skip("need 2 restaurants")
    r1 = rests["items"][0]["id"]
    r2 = rests["items"][1]["id"]
    m1 = httpx.get(f"{BASE}/api/v1/restaurants/{r1}/menu", headers=auth_headers(customer_token),
                   params={"page": 1, "page_size": 1}, timeout=5).json()["items"][0]["id"]
    m2 = httpx.get(f"{BASE}/api/v1/restaurants/{r2}/menu", headers=auth_headers(customer_token),
                   params={"page": 1, "page_size": 1}, timeout=5).json()["items"][0]["id"]
    key = f"test-mixed-{uuid.uuid4()}"
    payload = {"restaurant_id": r1, "delivery_address": "123 Test St, Bangalore 560001",
               "items": [{"menu_item_id": m1, "quantity": 1}, {"menu_item_id": m2, "quantity": 1}]}
    r = httpx.post(f"{BASE}/api/v1/orders", headers={**auth_headers(customer_token), "Idempotency-Key": key},
                   json=payload, timeout=10)
    assert r.status_code == 422


def test_customer_cannot_read_another_customers_order_and_admin_can(customer_token, admin_token):
    alice = login("alice@quickbite.example", "DemoPass123!")
    assert alice.status_code == 200
    alice_token = alice.json()["access_token"]
    rests = httpx.get(
        f"{BASE}/api/v1/restaurants", headers=auth_headers(alice_token),
        params={"page": 1, "page_size": 1}, timeout=5,
    ).json()
    restaurant_id = rests["items"][0]["id"]
    menu = httpx.get(
        f"{BASE}/api/v1/restaurants/{restaurant_id}/menu",
        headers=auth_headers(alice_token), params={"page": 1, "page_size": 1}, timeout=5,
    ).json()
    payload = {
        "restaurant_id": restaurant_id,
        "delivery_address": "123 Test St, Bangalore 560001",
        "items": [{"menu_item_id": menu["items"][0]["id"], "quantity": 1}],
    }
    accepted = httpx.post(
        f"{BASE}/api/v1/orders",
        headers={**auth_headers(alice_token), "Idempotency-Key": f"owner-{uuid.uuid4()}"},
        json=payload, timeout=10,
    )
    assert accepted.status_code == 202
    order_id = accepted.json()["order_id"]

    denied = httpx.get(
        f"{BASE}/api/v1/orders/{order_id}", headers=auth_headers(customer_token), timeout=5
    )
    assert denied.status_code == 404
    admin_read = httpx.get(
        f"{BASE}/api/v1/orders/{order_id}", headers=auth_headers(admin_token), timeout=5
    )
    assert admin_read.status_code == 200
