"""Broker connection helpers shared by workers, dispatcher and scheduler.

Provides:
- a robust connection/channel pair with publisher confirms and
  ``on_return_raises`` so unroutable mandatory publishes surface as errors;
- exponential-backoff reconnection on startup/transient failures;
- graceful shutdown support (callers close on SIGTERM/SIGINT).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aio_pika
from aio_pika.abc import AbstractChannel, AbstractRobustConnection

from app.core.config import settings

logger = logging.getLogger("quickbite.connection")


class BrokerUnavailable(RuntimeError):
    """Raised when the broker cannot be reached within the retry budget."""


async def connect_with_backoff(
    *,
    url: str | None = None,
    max_attempts: int = 12,
    base_delay: float = 0.5,
    max_delay: float = 10.0,
    **channel_kwargs: Any,
) -> tuple[AbstractRobustConnection, AbstractChannel]:
    """Connect and open a confirms-enabled channel with bounded backoff."""
    amqp_url = url or settings.amqp_url
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            connection = await aio_pika.connect_robust(amqp_url)
            channel = await connection.channel(
                publisher_confirms=True, on_return_raises=True, **channel_kwargs
            )
            logger.info("broker_connected", extra={"attempt": attempt})
            return connection, channel
        except Exception as exc:  # noqa: BLE001 - bounded retry loop
            last_error = exc
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            logger.warning(
                "broker_connect_failed",
                extra={"attempt": attempt, "delay_s": round(delay, 2), "error": str(exc)},
            )
            if attempt == max_attempts:
                break
            await asyncio.sleep(delay)
    raise BrokerUnavailable(f"cannot connect to broker at configured URL: {last_error}")


async def close_quietly(*resources: Any) -> None:
    for resource in resources:
        if resource is None:
            continue
        try:
            await resource.close()
        except Exception:  # noqa: BLE001 - shutdown path must not raise
            logger.debug("close_ignored_error", exc_info=True)
