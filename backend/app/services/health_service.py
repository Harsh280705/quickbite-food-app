"""Health and readiness probes with bounded dependency checks.

Semantics (documented in README and docs/ARCHITECTURE.md):

- ``/health/live``: process liveness only. Never depends on PostgreSQL or
  RabbitMQ. Always 200 while the event loop responds.
- ``/health/ready``: bounded dependency checks.
    * PostgreSQL is *required*: if the database is unreachable the API cannot
      authenticate users, accept orders or serve state -> 503.
    * RabbitMQ is *not* required for acceptance: orders are committed with a
      transactional outbox row first, so a broker outage only delays
      processing. Readiness reports ``degraded`` but stays 200. A *database*
      outage after an order is accepted is more severe: the order already
      exists (it is durable), but new checkouts and status reads fail -> 503.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from app.core.config import settings
from app.db.session import get_engine

logger = logging.getLogger("quickbite.health")


async def _check_database() -> dict[str, Any]:
    start = time.perf_counter()
    try:
        engine = get_engine()
        async with asyncio.timeout(settings.db_probe_timeout_seconds):
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "latency_ms": round((time.perf_counter() - start) * 1000, 2),
        }
    except Exception as exc:  # noqa: BLE001 - probe must never raise
        return {
            "status": "error",
            "latency_ms": round((time.perf_counter() - start) * 1000, 2),
            "detail": f"{type(exc).__name__}: {exc}"[:300],
        }


async def _check_broker() -> dict[str, Any]:
    """Probe the AMQP listener directly with a short connect/close cycle.

    The HTTP management API is intentionally not used here: its health paths
    are version dependent (``/api/health/checks/node`` is not exposed by every
    build and answers 404), which previously reported a healthy broker as
    degraded. AMQP reachability is the capability the outbox dispatcher and
    workers actually depend on.
    """
    import aio_pika

    start = time.perf_counter()
    connection = None
    try:
        async with asyncio.timeout(settings.amqp_probe_timeout_seconds):
            connection = await aio_pika.connect(settings.amqp_url, timeout=1.0)
        return {
            "status": "ok",
            "latency_ms": round((time.perf_counter() - start) * 1000, 2),
        }
    except Exception as exc:  # noqa: BLE001 - probe must never raise
        return {
            "status": "degraded",
            "latency_ms": round((time.perf_counter() - start) * 1000, 2),
            "detail": f"{type(exc).__name__}: {exc}"[:300],
        }
    finally:
        if connection is not None:
            try:
                await connection.close()
            except Exception:  # noqa: BLE001
                pass


async def live_payload() -> dict[str, Any]:
    return {
        "status": "live",
        "service": settings.project_name,
        "time": datetime.now(timezone.utc).isoformat(),
    }


async def ready_payload() -> tuple[dict[str, Any], int]:
    db_check, broker_check = await asyncio.gather(
        _check_database(), _check_broker()
    )
    # Bounded overall probe time: each sub-probe has its own timeout.
    required_ok = db_check["status"] == "ok"
    status = "ready" if required_ok else "unavailable"
    if required_ok and broker_check["status"] != "ok":
        status = "degraded"
    payload = {
        "status": status,
        "service": settings.project_name,
        "checks": {"database": db_check, "rabbitmq": broker_check},
        "time": datetime.now(timezone.utc).isoformat(),
    }
    return payload, (200 if required_ok else 503)
