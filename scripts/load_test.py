"""Repeatable QuickBite checkout load test with machine and queue observations.

This script creates customer/order data. It requires an explicit confirmation
that the target API is an isolated test stack and never deletes test data.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import platform
import statistics
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit

import httpx
from dotenv import load_dotenv

BASE = "http://127.0.0.1:8000"
LOAD_EMAIL = "loadtest@quickbite.example"
LOAD_PASSWORD = "LoadTest123!"
TERMINAL = {"DRIVER_ASSIGNED", "PAYMENT_FAILED", "FAILED"}


async def ensure_user(client: httpx.AsyncClient, base_url: str) -> str:
    payload = {"full_name": "Load Test Customer", "email": LOAD_EMAIL, "password": LOAD_PASSWORD}
    response = await client.post(f"{base_url}/api/v1/auth/register", json=payload, timeout=10)
    if response.status_code not in (201, 409):
        response.raise_for_status()
    response = await client.post(
        f"{base_url}/api/v1/auth/login",
        json={"email": LOAD_EMAIL, "password": LOAD_PASSWORD},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def machine_resources() -> dict[str, object]:
    memory_bytes = None
    try:
        import psutil  # optional on the load-test host

        memory_bytes = int(psutil.virtual_memory().total)
    except ImportError:
        pass
    return {
        "hostname": platform.node(),
        "platform": platform.platform(),
        "processor": platform.processor() or None,
        "logical_cpu_count": os.cpu_count(),
        "memory_bytes": memory_bytes,
        "python": platform.python_version(),
    }


async def queue_snapshot(client: httpx.AsyncClient) -> dict[str, object]:
    amqp = urlsplit(os.getenv("AMQP_URL", "amqp://guest:guest@127.0.0.1:5672/"))
    management_url = os.getenv(
        "RABBITMQ_MANAGEMENT_URL",
        f"http://127.0.0.1:{os.getenv('RABBITMQ_MANAGEMENT_PORT', '15672')}",
    ).rstrip("/")
    auth = (unquote(amqp.username or "guest"), unquote(amqp.password or "guest"))
    try:
        response = await client.get(
            f"{management_url}/api/queues/%2F", auth=auth, timeout=3
        )
        response.raise_for_status()
        queues = [
            {
                "name": q.get("name"),
                "ready": int(q.get("messages_ready", 0)),
                "unacknowledged": int(q.get("messages_unacknowledged", 0)),
                "consumers": int(q.get("consumers", 0)),
            }
            for q in response.json()
            if str(q.get("name", "")).endswith(".queue")
        ]
        return {"available": True, "queues": queues}
    except (httpx.HTTPError, ValueError) as exc:
        return {"available": False, "error": type(exc).__name__}


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--orders", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--payment-workers", type=int, required=True)
    parser.add_argument("--base-url", type=str, default=None)
    parser.add_argument("--env-file", type=Path, default=None, help="isolated stack env file (for example .env.test)")
    parser.add_argument("--out", type=str, default=None)
    parser.add_argument(
        "--confirm-isolated-stack",
        action="store_true",
        help="required because this test creates orders and a load-test account",
    )
    args = parser.parse_args()
    if args.env_file is not None:
        load_dotenv(args.env_file, override=False)
    else:
        load_dotenv()
    if not args.confirm_isolated_stack:
        parser.error("use only on an isolated stack and pass --confirm-isolated-stack")
    if args.orders < 100:
        parser.error("--orders must be at least 100 for the assignment exercise")
    if args.concurrency < 1 or args.payment_workers < 1:
        parser.error("concurrency and payment-workers must be positive")

    modes = {
        "payment": os.getenv("DEMO_PAYMENT_MODE", "success"),
        "restaurant": os.getenv("DEMO_RESTAURANT_MODE", "success"),
        "delivery": os.getenv("DEMO_DELIVERY_MODE", "success"),
        "notification": os.getenv("DEMO_NOTIFICATION_MODE", "success"),
    }
    if any(mode != "success" for mode in modes.values()):
        parser.error("set all DEMO_*_MODE values to success for a comparable run")

    base_url = (args.base_url or os.getenv("LOAD_TEST_API_BASE_URL", BASE)).rstrip("/")
    async with httpx.AsyncClient() as client:
        token = await ensure_user(client, base_url)
        headers = {"Authorization": f"Bearer {token}"}
        restaurants = await client.get(
            f"{base_url}/api/v1/restaurants", headers=headers,
            params={"page": 1, "page_size": 1}, timeout=10,
        )
        restaurants.raise_for_status()
        restaurant_id = restaurants.json()["items"][0]["id"]
        menu = await client.get(
            f"{base_url}/api/v1/restaurants/{restaurant_id}/menu", headers=headers,
            params={"page": 1, "page_size": 1}, timeout=10,
        )
        menu.raise_for_status()
        menu_item_id = menu.json()["items"][0]["id"]

        semaphore = asyncio.Semaphore(args.concurrency)
        latencies: list[float] = []
        order_ids: list[str] = []
        errors: list[str] = []
        queue_samples: list[dict[str, object]] = []
        stop_sampling = asyncio.Event()

        async def sample_queues() -> None:
            while not stop_sampling.is_set():
                queue_samples.append(await queue_snapshot(client))
                try:
                    await asyncio.wait_for(stop_sampling.wait(), timeout=1)
                except asyncio.TimeoutError:
                    pass

        async def submit() -> None:
            async with semaphore:
                key = f"load-{uuid.uuid4()}"
                payload = {
                    "restaurant_id": restaurant_id,
                    "delivery_address": "Load Test Address, Bangalore 560001",
                    "items": [{"menu_item_id": menu_item_id, "quantity": 1}],
                }
                started = time.perf_counter()
                try:
                    response = await client.post(
                        f"{base_url}/api/v1/orders",
                        headers={**headers, "Idempotency-Key": key},
                        json=payload,
                        timeout=30,
                    )
                    elapsed_ms = (time.perf_counter() - started) * 1000
                    response.raise_for_status()
                    order_ids.append(response.json()["order_id"])
                    latencies.append(elapsed_ms)
                except Exception as exc:  # keep all submission outcomes in the report
                    errors.append(type(exc).__name__)

        async def read_status(order_id: str) -> str | None:
            try:
                response = await client.get(
                    f"{base_url}/api/v1/orders/{order_id}", headers=headers, timeout=10
                )
                response.raise_for_status()
                return response.json()["status"]
            except httpx.HTTPError:
                return None

        sampler = asyncio.create_task(sample_queues())
        start = time.perf_counter()
        await asyncio.gather(*(submit() for _ in range(args.orders)))
        acceptance_elapsed = time.perf_counter() - start
        pending = set(order_ids)
        completion_deadline = time.perf_counter() + 300
        while pending and time.perf_counter() < completion_deadline:
            batch = list(pending)[:50]
            statuses = await asyncio.gather(*(read_status(oid) for oid in batch))
            for oid, status in zip(batch, statuses):
                if status in TERMINAL:
                    pending.discard(oid)
            if pending:
                await asyncio.sleep(1)
        total_elapsed = time.perf_counter() - start
        statuses = await asyncio.gather(*(read_status(oid) for oid in order_ids))
        status_counts: dict[str, int] = {}
        for status in statuses:
            label = status or "ERROR"
            status_counts[label] = status_counts.get(label, 0) + 1
        stop_sampling.set()
        await sampler
        queue_samples.append(await queue_snapshot(client))

    sorted_latencies = sorted(latencies)

    def percentile(percent: int) -> float:
        if not sorted_latencies:
            return 0.0
        rank = max(0, math.ceil(len(sorted_latencies) * percent / 100) - 1)
        return sorted_latencies[min(rank, len(sorted_latencies) - 1)]

    available = [sample for sample in queue_samples if sample.get("available")]
    queues = [queue for sample in available for queue in sample.get("queues", [])]
    output = Path(args.out) if args.out else Path("logs") / (
        f"load_{args.payment_workers}workers_"
        f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    )
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing load result: {output}")

    result = {
        "orders_requested": args.orders,
        "orders_accepted": len(order_ids),
        "submission_errors": len(errors),
        "submission_error_types": errors,
        "concurrency": args.concurrency,
        "payment_workers_configured": args.payment_workers,
        "payment_workers_observed_max": max((q["consumers"] for q in queues if q["name"] == "payment.queue"), default=None),
        "acceptance_elapsed_seconds": round(acceptance_elapsed, 3),
        "total_processing_elapsed_seconds": round(total_elapsed, 3),
        "orders_per_second": round(len(order_ids) / total_elapsed, 2) if total_elapsed else 0,
        "api_p50_ms": round(percentile(50), 2),
        "api_p95_ms": round(percentile(95), 2),
        "api_p99_ms": round(percentile(99), 2),
        "remaining_unprocessed": len(pending),
        "status_counts": status_counts,
        "machine_resources": machine_resources(),
        "simulation_modes": modes,
        "stage_delays_ms": {
            stage: int(os.getenv(f"SIM_{stage.upper()}_DELAY_MS", default))
            for stage, default in (
                ("payment", "250"), ("restaurant", "200"),
                ("delivery", "200"), ("notification", "50"),
            )
        },
        "queue_observations": {
            "sample_count": len(queue_samples),
            "available_sample_count": len(available),
            "max_ready_observed": max((int(q["ready"]) for q in queues), default=None),
            "max_unacknowledged_observed": max((int(q["unacknowledged"]) for q in queues), default=None),
            "samples": queue_samples,
        },
        "base_url": base_url,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps({**result, "result_file": str(output)}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())