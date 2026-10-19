import os
import subprocess
import sys
import time
import uuid

import httpx
import pytest

BASE = os.environ.get("QUICKBITE_TEST_API_URL", "http://127.0.0.1:8001")
pytestmark = pytest.mark.skipif(os.getenv("QUICKBITE_TEST_ENV") != "1", reason="recovery tests require the isolated quickbite-test stack")
BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def login(email, password):
    r = httpx.post(f"{BASE}/api/v1/auth/login", json={"email": email, "password": password}, timeout=10)
    r.raise_for_status()
    return r.json()["access_token"]


def start_payment_worker(mode):
    env = dict(os.environ)
    env["DEMO_PAYMENT_MODE"] = mode
    env["PYTHONPATH"] = BACKEND
    env["DATABASE_URL"] = os.environ["QUICKBITE_TEST_DATABASE_URL"]
    env["AMQP_URL"] = os.environ["QUICKBITE_TEST_AMQP_URL"]
    p = subprocess.Popen(
        [sys.executable, "-m", "workers.payment_worker"],
        cwd=BACKEND,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(4)
    return p


def stop_proc(p):
    p.terminate()
    try:
        p.wait(timeout=10)
    except subprocess.TimeoutExpired:
        p.kill()


@pytest.mark.timeout(120)
def test_always_fail_payment_quarantines():
    # Stop the docker success payment worker to avoid races, then run an always_fail one.
    subprocess.run(["docker", "compose", "--env-file", os.environ["QUICKBITE_TEST_ENV_FILE"], "-p", os.environ["QUICKBITE_TEST_COMPOSE_PROJECT"], "stop", "payment-worker"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    token = login("demo@quickbite.example", "DemoPass123!")
    headers = {"Authorization": f"Bearer {token}"}
    rests = httpx.get(f"{BASE}/api/v1/restaurants", headers=headers, params={"page": 1, "page_size": 1}, timeout=10).json()
    rid = rests["items"][0]["id"]
    menu = httpx.get(f"{BASE}/api/v1/restaurants/{rid}/menu", headers=headers, params={"page": 1, "page_size": 1}, timeout=10).json()
    mid = menu["items"][0]["id"]
    key = f"af-{uuid.uuid4()}"
    payload = {"restaurant_id": rid, "delivery_address": "123 Test St, Bangalore 560001", "items": [{"menu_item_id": mid, "quantity": 1}]}
    # Start always_fail worker
    p = start_payment_worker("always_fail")
    try:
        r = httpx.post(f"{BASE}/api/v1/orders", headers={**headers, "Idempotency-Key": key}, json=payload, timeout=10)
        assert r.status_code == 202
        oid = r.json()["order_id"]
        # wait for terminal
        for _ in range(30):
            time.sleep(2)
            o = httpx.get(f"{BASE}/api/v1/orders/{oid}", headers=headers, timeout=10).json()
            if o["status"] in ("PAYMENT_FAILED", "FAILED", "DRIVER_ASSIGNED"):
                break
        assert o["status"] == "PAYMENT_FAILED", o["status"]
    finally:
        stop_proc(p)
        subprocess.run(["docker", "compose", "--env-file", os.environ["QUICKBITE_TEST_ENV_FILE"], "-p", os.environ["QUICKBITE_TEST_COMPOSE_PROJECT"], "start", "payment-worker"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
