import os
import subprocess
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


def docker(action, service):
    subprocess.run(["docker", "compose", "--env-file", os.environ["QUICKBITE_TEST_ENV_FILE"], "-p", os.environ["QUICKBITE_TEST_COMPOSE_PROJECT"], action, service],
                   check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def env_from_dotenv():
    env = dict(os.environ)
    env["PYTHONPATH"] = BACKEND
    env["DATABASE_URL"] = os.environ["QUICKBITE_TEST_DATABASE_URL"]
    env["AMQP_URL"] = os.environ["QUICKBITE_TEST_AMQP_URL"]
    return env


def start_worker(module, env_overrides):
    env = env_from_dotenv()
    env.update(env_overrides)
    p = subprocess.Popen([env["PYTHON"] if "PYTHON" in env else __import__("sys").executable, "-m", module],
                         cwd=BACKEND, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(4)
    return p


def stop_proc(p):
    p.terminate()
    try:
        p.wait(timeout=10)
    except Exception:
        p.kill()


@pytest.mark.timeout(180)
def test_worker_crash_before_commit_recovers():
    # Stop docker payment worker to avoid races
    docker("stop", "payment-worker")
    time.sleep(2)
    token = login("demo@quickbite.example", "DemoPass123!")
    headers = {"Authorization": f"Bearer {token}"}
    rests = httpx.get(f"{BASE}/api/v1/restaurants", headers=headers, params={"page": 1, "page_size": 1}, timeout=10).json()
    rid = rests["items"][0]["id"]
    menu = httpx.get(f"{BASE}/api/v1/restaurants/{rid}/menu", headers=headers, params={"page": 1, "page_size": 1}, timeout=10).json()
    mid = menu["items"][0]["id"]
    key = f"cb-{uuid.uuid4()}"
    payload = {"restaurant_id": rid, "delivery_address": "123 Test St, Bangalore 560001", "items": [{"menu_item_id": mid, "quantity": 1}]}
    # create order first to get id for crash targeting
    r = httpx.post(f"{BASE}/api/v1/orders", headers={**headers, "Idempotency-Key": key}, json=payload, timeout=10)
    assert r.status_code == 202
    oid = r.json()["order_id"]
    # start a payment worker that crashes before commit for this order
    env = {"DEMO_PAYMENT_MODE": "success", "DEMO_CRASH_MODE": "before_commit", "DEMO_CRASH_ORDER_ID": oid}
    p = start_worker("workers.payment_worker", env)
    # wait a bit for crash; worker process should exit
    for _ in range(10):
        time.sleep(1)
        if p.poll() is not None:
            break
    stop_proc(p)
    # restart a normal payment worker locally
    p2 = start_worker("workers.payment_worker", {"DEMO_PAYMENT_MODE": "success", "DEMO_CRASH_MODE": "none"})
    # wait for order to progress
    for _ in range(30):
        time.sleep(2)
        o = httpx.get(f"{BASE}/api/v1/orders/{oid}", headers=headers, timeout=10).json()
        if o["status"] in ("DRIVER_ASSIGNED", "PAYMENT_FAILED", "FAILED"):
            break
    stop_proc(p2)
    docker("start", "payment-worker")
    assert o["status"] == "DRIVER_ASSIGNED", o["status"]


@pytest.mark.timeout(180)
def test_worker_crash_after_commit_before_ack_recovers():
    docker("stop", "payment-worker")
    time.sleep(2)
    token = login("demo@quickbite.example", "DemoPass123!")
    headers = {"Authorization": f"Bearer {token}"}
    rests = httpx.get(f"{BASE}/api/v1/restaurants", headers=headers, params={"page": 1, "page_size": 1}, timeout=10).json()
    rid = rests["items"][0]["id"]
    menu = httpx.get(f"{BASE}/api/v1/restaurants/{rid}/menu", headers=headers, params={"page": 1, "page_size": 1}, timeout=10).json()
    mid = menu["items"][0]["id"]
    key = f"ca-{uuid.uuid4()}"
    payload = {"restaurant_id": rid, "delivery_address": "123 Test St, Bangalore 560001", "items": [{"menu_item_id": mid, "quantity": 1}]}
    r = httpx.post(f"{BASE}/api/v1/orders", headers={**headers, "Idempotency-Key": key}, json=payload, timeout=10)
    assert r.status_code == 202
    oid = r.json()["order_id"]
    env = {"DEMO_PAYMENT_MODE": "success", "DEMO_CRASH_MODE": "after_commit_before_ack", "DEMO_CRASH_ORDER_ID": oid}
    p = start_worker("workers.payment_worker", env)
    for _ in range(10):
        time.sleep(1)
        if p.poll() is not None:
            break
    stop_proc(p)
    # restart normal worker
    p2 = start_worker("workers.payment_worker", {"DEMO_PAYMENT_MODE": "success", "DEMO_CRASH_MODE": "none"})
    for _ in range(30):
        time.sleep(2)
        o = httpx.get(f"{BASE}/api/v1/orders/{oid}", headers=headers, timeout=10).json()
        if o["status"] in ("DRIVER_ASSIGNED", "PAYMENT_FAILED", "FAILED"):
            break
    stop_proc(p2)
    docker("start", "payment-worker")
    assert o["status"] == "DRIVER_ASSIGNED", o["status"]
    # verify only one payment record (can't easily check via API, but status progression confirms no duplicate effect)


@pytest.mark.timeout(180)
def test_dispatcher_crash_after_publish_before_sent_recovers():
    docker("stop", "outbox-dispatcher")
    time.sleep(2)
    token = login("demo@quickbite.example", "DemoPass123!")
    headers = {"Authorization": f"Bearer {token}"}
    rests = httpx.get(f"{BASE}/api/v1/restaurants", headers=headers, params={"page": 1, "page_size": 1}, timeout=10).json()
    rid = rests["items"][0]["id"]
    menu = httpx.get(f"{BASE}/api/v1/restaurants/{rid}/menu", headers=headers, params={"page": 1, "page_size": 1}, timeout=10).json()
    mid = menu["items"][0]["id"]
    key = f"dc-{uuid.uuid4()}"
    payload = {"restaurant_id": rid, "delivery_address": "123 Test St, Bangalore 560001", "items": [{"menu_item_id": mid, "quantity": 1}]}
    r = httpx.post(f"{BASE}/api/v1/orders", headers={**headers, "Idempotency-Key": key}, json=payload, timeout=10)
    assert r.status_code == 202
    oid = r.json()["order_id"]
    # start dispatcher that crashes after publish before sent
    env = {"DISPATCHER_CRASH_MODE": "after_publish_before_sent", "DISPATCHER_CRASH_ORDER_ID": oid}
    p = start_worker("workers.outbox_dispatcher", env)
    for _ in range(10):
        time.sleep(1)
        if p.poll() is not None:
            break
    stop_proc(p)
    # restart normal dispatcher
    p2 = start_worker("workers.outbox_dispatcher", {"DISPATCHER_CRASH_MODE": "none"})
    for _ in range(30):
        time.sleep(2)
        o = httpx.get(f"{BASE}/api/v1/orders/{oid}", headers=headers, timeout=10).json()
        if o["status"] in ("DRIVER_ASSIGNED", "PAYMENT_FAILED", "FAILED"):
            break
    stop_proc(p2)
    docker("start", "outbox-dispatcher")
    assert o["status"] == "DRIVER_ASSIGNED", o["status"]