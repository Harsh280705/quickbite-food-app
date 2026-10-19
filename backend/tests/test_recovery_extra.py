import os
import subprocess
import time
import uuid

import httpx
import pytest

BASE = os.environ.get("QUICKBITE_TEST_API_URL", "http://127.0.0.1:8001")
pytestmark = pytest.mark.skipif(os.getenv("QUICKBITE_TEST_ENV") != "1", reason="recovery tests require the isolated quickbite-test stack")


def login(email, password):
    r = httpx.post(f"{BASE}/api/v1/auth/login", json={"email": email, "password": password}, timeout=10)
    r.raise_for_status()
    return r.json()["access_token"]


def docker(action, service):
    subprocess.run(["docker", "compose", "--env-file", os.environ["QUICKBITE_TEST_ENV_FILE"], "-p", os.environ["QUICKBITE_TEST_COMPOSE_PROJECT"], action, service],
                   check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


@pytest.mark.timeout(180)
def test_broker_outage_outbox_recovery():
    token = login("demo@quickbite.example", "DemoPass123!")
    headers = {"Authorization": f"Bearer {token}"}
    # stop rabbitmq
    docker("stop", "rabbitmq")
    time.sleep(3)
    rests = httpx.get(f"{BASE}/api/v1/restaurants", headers=headers, params={"page": 1, "page_size": 1}, timeout=10).json()
    rid = rests["items"][0]["id"]
    menu = httpx.get(f"{BASE}/api/v1/restaurants/{rid}/menu", headers=headers, params={"page": 1, "page_size": 1}, timeout=10).json()
    mid = menu["items"][0]["id"]
    key = f"bo-{uuid.uuid4()}"
    payload = {"restaurant_id": rid, "delivery_address": "123 Test St, Bangalore 560001", "items": [{"menu_item_id": mid, "quantity": 1}]}
    r = httpx.post(f"{BASE}/api/v1/orders", headers={**headers, "Idempotency-Key": key}, json=payload, timeout=10)
    assert r.status_code == 202, r.text
    oid = r.json()["order_id"]
    # restart rabbitmq
    docker("start", "rabbitmq")
    # wait for healthy
    for _ in range(30):
        time.sleep(2)
        try:
            httpx.get("http://127.0.0.1:15672", timeout=3)
            break
        except Exception:
            pass
    time.sleep(15)
    # verify order progresses
    for _ in range(45):
        time.sleep(2)
        o = httpx.get(f"{BASE}/api/v1/orders/{oid}", headers=headers, timeout=10).json()
        if o["status"] in ("DRIVER_ASSIGNED", "PAYMENT_FAILED", "FAILED"):
            break
    assert o["status"] == "DRIVER_ASSIGNED", o["status"]


@pytest.mark.timeout(180)
def test_notification_worker_backlog_recovery():
    token = login("demo@quickbite.example", "DemoPass123!")
    headers = {"Authorization": f"Bearer {token}"}
    # stop notification worker
    docker("stop", "notification-worker")
    time.sleep(2)
    rests = httpx.get(f"{BASE}/api/v1/restaurants", headers=headers, params={"page": 1, "page_size": 1}, timeout=10).json()
    rid = rests["items"][0]["id"]
    menu = httpx.get(f"{BASE}/api/v1/restaurants/{rid}/menu", headers=headers, params={"page": 1, "page_size": 1}, timeout=10).json()
    mid = menu["items"][0]["id"]
    key = f"nw-{uuid.uuid4()}"
    payload = {"restaurant_id": rid, "delivery_address": "123 Test St, Bangalore 560001", "items": [{"menu_item_id": mid, "quantity": 1}]}
    r = httpx.post(f"{BASE}/api/v1/orders", headers={**headers, "Idempotency-Key": key}, json=payload, timeout=10)
    assert r.status_code == 202
    oid = r.json()["order_id"]
    # wait for order to reach DRIVER_ASSIGNED despite notification worker down
    for _ in range(30):
        time.sleep(2)
        o = httpx.get(f"{BASE}/api/v1/orders/{oid}", headers=headers, timeout=10).json()
        if o["status"] in ("DRIVER_ASSIGNED", "PAYMENT_FAILED", "FAILED"):
            break
    assert o["status"] == "DRIVER_ASSIGNED", o["status"]
    # restart notification worker
    docker("start", "notification-worker")
    time.sleep(6)
    # verify notification appears
    for _ in range(20):
        time.sleep(2)
        n = httpx.get(f"{BASE}/api/v1/orders/{oid}/notifications", headers=headers, params={"page": 1, "page_size": 10}, timeout=10).json()
        if n["total"] > 0:
            break
    assert n["total"] > 0, "notification backlog did not drain"
