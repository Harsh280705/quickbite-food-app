"""Outbox dispatcher — claims pending outbox events and publishes to RabbitMQ.

Responsibilities:
- Claim PENDING outbox events available_at <= now using SKIP LOCKED + lease
- Publish with publisher confirms + mandatory routing
- Mark SENT only after confirm + no unroutable return
- Handle crash window (published but not marked SENT) via idempotent consumers
- On publish failure: leave PENDING for retry
- Graceful shutdown
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys

import aio_pika
from aio_pika import ExchangeType
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.core.logging import configure_logging, log, set_correlation_id
from app.db.session import get_session_factory
from app.messaging.connection import BrokerUnavailable, close_quietly, connect_with_backoff
from app.messaging.publisher import PublishError, build_message, publish_message
from app.messaging.topology import (
    DEAD_EXCHANGE,
    DEAD_QUEUE,
    DEAD_ROUTING_KEY,
    ORDERS_EXCHANGE,
    declare_topology,
)
from app.models.messaging import OutboxEvent, QuarantineRecord

configure_logging(settings.log_level)
logger = logging.getLogger("quickbite.outbox_dispatcher")

DISPATCHER_NAME = "outbox_dispatcher"
CLAIM_BATCH = settings.outbox_batch_size
LEASE_SECONDS = settings.outbox_lease_seconds
POLL_INTERVAL = settings.outbox_poll_interval_ms / 1000.0


class OutboxDispatcher:
    def __init__(self):
        self._connection = None
        self._channel = None
        self._orders_exchange = None
        self._dead_exchange = None
        self._running = False
        self._shutdown_event = asyncio.Event()

    async def start(self):
        self._connection, self._channel = await connect_with_backoff(
            url=settings.amqp_url,
            max_attempts=12,
            base_delay=0.5,
            max_delay=10.0,
        )
        # Declare topology to get exchange references
        topology = await declare_topology(self._channel)
        self._orders_exchange = topology["orders_exchange"]
        self._dead_exchange = topology["dead_exchange"]
        self._running = True
        logger.info("outbox_dispatcher_started",
                    extra={"batch_size": CLAIM_BATCH, "lease_seconds": LEASE_SECONDS})
        while self._running:
            await self._dispatch_cycle()
            await asyncio.sleep(POLL_INTERVAL)
        logger.info("outbox_dispatcher_stopped")

    def request_shutdown(self):
        self._running = False
        self._shutdown_event.set()

    async def _dispatch_cycle(self):
        factory = get_session_factory()
        async with factory() as session:
            # Claim available events
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            stmt = (
                select(OutboxEvent)
                .where(
                    OutboxEvent.status == "PENDING",
                    OutboxEvent.available_at <= now,
                    (OutboxEvent.locked_until.is_(None)) | (OutboxEvent.locked_until <= now),
                )
                .order_by(OutboxEvent.created_at)
                .limit(CLAIM_BATCH)
                .with_for_update(skip_locked=True)
            )
            result = await session.execute(stmt)
            events = list(result.scalars().all())

            if not events:
                return

            # Update claimed events with lease
            lease_until = datetime.now(timezone.utc).replace(
                microsecond=0
            )  # simplified lease
            # Actually use proper lease:
            from datetime import timedelta
            lease_until = datetime.now(timezone.utc) + timedelta(seconds=LEASE_SECONDS)
            for ev in events:
                ev.status = "SENDING"
                ev.locked_until = lease_until
                ev.locked_by = DISPATCHER_NAME
                ev.attempts += 1
            await session.commit()

        # Publish outside transaction
        for ev in events:
            try:
                await self._publish_event(ev)
            except Exception as exc:
                log(logger, logging.ERROR, "publish_failed",
                    extra={"publication_id": str(ev.id), "event_id": str(ev.event_id),
                           "error": str(exc)})
                await self._mark_failed(ev, str(exc))

    async def _publish_event(self, ev: OutboxEvent):
        """Publish a single outbox event."""
        message = build_message(ev.payload)

        try:
            if ev.exchange:
                await publish_message(
                    self._channel,
                    exchange_name=ev.exchange,
                    routing_key=ev.routing_key,
                    message=message,
                )
            else:
                # Default exchange (direct to queue)
                await publish_message(
                    self._channel,
                    exchange_name="",
                    routing_key=ev.routing_key,
                    message=message,
                )
        except PublishError as exc:
            # Check if it was an unroutable return (mandatory + no queue)
            # The publish_message already raises for unroutable
            raise

        # Mark sent
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(OutboxEvent).where(OutboxEvent.id == ev.id)
            result = await session.execute(stmt)
            db_ev = result.scalar_one_or_none()
            if db_ev:
                db_ev.status = "SENT"
                db_ev.sent_at = datetime.now(timezone.utc)
                await session.commit()

        log(logger, logging.INFO, "outbox_event_published",
            extra={"publication_id": str(ev.id), "event_id": str(ev.event_id),
                   "exchange": ev.exchange or "<default>", "routing_key": ev.routing_key})

    async def _mark_failed(self, ev: OutboxEvent, error: str):
        """Mark event failed and reschedule for retry after a delay."""
        from datetime import datetime, timedelta, timezone
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(OutboxEvent).where(OutboxEvent.id == ev.id)
            result = await session.execute(stmt)
            db_ev = result.scalar_one_or_none()
            if db_ev:
                db_ev.attempts = (db_ev.attempts or 0) + 1
                db_ev.last_error = error[:512]
                if db_ev.attempts >= 5:
                    db_ev.status = "FAILED"
                else:
                    db_ev.status = "PENDING"
                    db_ev.available_at = datetime.now(timezone.utc) + timedelta(seconds=5)
                    db_ev.locked_until = None
                    db_ev.locked_by = None
                await session.commit()


async def main():
    dispatcher = OutboxDispatcher()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, dispatcher.request_shutdown)
        except (NotImplementedError, RuntimeError):
            signal.signal(sig, lambda s, f: dispatcher.request_shutdown())
    try:
        await dispatcher.start()
    except BrokerUnavailable as exc:
        log(logger, logging.CRITICAL, "broker_unavailable", extra={"error": str(exc)})
        sys.exit(1)
    except Exception as exc:
        log(logger, logging.CRITICAL, "dispatcher_fatal", extra={"error": str(exc)}, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    import signal
    from datetime import datetime, timezone, timedelta
    asyncio.run(main())

