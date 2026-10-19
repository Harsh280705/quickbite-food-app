"""Restaurant worker — consumes order.paid, simulates restaurant confirmation, advances order state.

Consumes order.paid from restaurant.queue.
Transitions PAID → CONFIRMED or PAID → FAILED.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import uuid
from datetime import datetime, timezone
from typing import Optional

import aio_pika
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.core.logging import configure_logging, log, set_correlation_id
from app.db.session import get_session_factory
from app.domain.events import (
    EVENT_ORDER_PAID,
    EVENT_ORDER_CONFIRMED,
    EVENT_ORDER_FAILED,
    build_event,
    parse_event,
)
from app.domain.state_machine import apply_transition
from app.messaging.connection import BrokerUnavailable, close_quietly, connect_with_backoff
from app.messaging.publisher import PublishError, build_message, publish_message
from app.messaging.topology import (
    RESTAURANT_QUEUE,
    ORDERS_EXCHANGE,
    declare_topology,
)
from app.models import Order, ProcessedEvent
from app.models.messaging import OutboxEvent, QuarantineRecord

configure_logging(settings.log_level)
logger = logging.getLogger("quickbite.restaurant_worker")

CONSUMER_NAME = "restaurant_worker"
PREFETCH_COUNT = settings.worker_prefetch_count


class RestaurantWorker:
    def __init__(self):
        self._connection = None
        self._channel = None
        self._queue = None
        self._running = False
        self._shutdown_event = asyncio.Event()
        self._in_flight = 0

    async def start(self):
        self._connection, self._channel = await connect_with_backoff(
            url=settings.amqp_url,
            max_attempts=12,
            base_delay=0.5,
            max_delay=10.0,
        )
        self._channel.set_qos(prefetch_count=PREFETCH_COUNT)
        topology = await declare_topology(self._channel)
        self._queue = topology["queues"][RESTAURANT_QUEUE]
        self._running = True
        logger.info("restaurant_worker_started", extra={"queue": RESTAURANT_QUEUE})
        await self._queue.consume(self._on_message, no_ack=False)
        await self._shutdown_event.wait()
        logger.info("restaurant_worker_shutting_down", extra={"in_flight": self._in_flight})
        while self._in_flight > 0:
            await asyncio.sleep(0.5)
        await self.stop()

    async def stop(self):
        self._running = False
        await close_quietly(self._channel, self._connection)
        logger.info("restaurant_worker_stopped")

    def request_shutdown(self):
        self._shutdown_event.set()

    async def _on_message(self, message):
        if not self._running:
            await message.reject(requeue=True)
            return
        self._in_flight += 1
        try:
            async with message.process(requeue=False):
                await self._process_message(message)
        finally:
            self._in_flight -= 1

    async def _process_message(self, message):
        raw_body = message.body
        correlation_id = message.correlation_id or "-"
        set_correlation_id(correlation_id)

        try:
            import json
            payload = json.loads(raw_body.decode("utf-8"))
            event = parse_event(payload)
        except Exception as exc:
            log(logger, logging.ERROR, "malformed_message",
                extra={"error": str(exc), "correlation_id": correlation_id})
            await self._quarantine_malformed(raw_body, str(exc), correlation_id)
            return

        if event.event_type != EVENT_ORDER_PAID:
            log(logger, logging.WARNING, "unexpected_event_type",
                extra={"expected": EVENT_ORDER_PAID, "got": event.event_type})
            return

        factory = get_session_factory()
        async with factory() as session:
            existing = await session.execute(
                select(ProcessedEvent).where(
                    ProcessedEvent.consumer_name == CONSUMER_NAME,
                    ProcessedEvent.event_id == event.event_id,
                )
            )
            if existing.scalar_one_or_none():
                log(logger, logging.INFO, "duplicate_event_acked",
                    extra={"event_id": str(event.event_id)})
                return

        await asyncio.sleep(settings.sim_restaurant_delay_ms / 1000.0)
        try:
            await self._handle_event(event)
        except Exception as exc:
            log(logger, logging.ERROR, "restaurant_processing_failed",
                extra={"event_id": str(event.event_id), "error": str(exc)}, exc_info=True)
            raise

    async def _handle_event(self, event):
        factory = get_session_factory()
        async with factory() as session:
            from app.domain.state_machine import get_order_for_update
            order = await get_order_for_update(session, event.order_id)
            if order is None:
                log(logger, logging.ERROR, "order_not_found",
                    extra={"order_id": str(event.order_id)})
                await self._quarantine_event(event, "ORDER_NOT_FOUND", "Order not found")
                return

            if order.status != "PAID":
                log(logger, logging.WARNING, "order_not_paid",
                    extra={"order_id": str(order.id), "current_status": order.status})
                await self._record_processed(session, event, order, "STALE_SKIPPED")
                return

            # Demo failure
            if settings.demo_restaurant_mode == "always_fail":
                new_version = await apply_transition(
                    session, order, "FAILED",
                    actor=CONSUMER_NAME,
                    note="restaurant declined",
                    failure_code="RESTAURANT_DECLINED",
                    failure_message="Simulated restaurant failure",
                )
                next_event_type = EVENT_ORDER_FAILED
            else:
                new_version = await apply_transition(
                    session, order, "CONFIRMED",
                    actor=CONSUMER_NAME,
                    note="restaurant confirmed",
                )
                next_event_type = EVENT_ORDER_CONFIRMED

            await self._record_processed(session, event, order, "APPLIED")

            next_event = build_event(
                event_type=next_event_type,
                order_id=order.id,
                order_version=new_version,
                data={"status": order.status},
                correlation_id=event.correlation_id,
                causation_id=event.event_id,
            )
            session.add(
                OutboxEvent(
                    event_id=next_event.event_id,
                    event_type=next_event.event_type,
                    order_id=next_event.order_id,
                    order_version=next_event.order_version,
                    exchange=ORDERS_EXCHANGE,
                    routing_key=next_event.event_type,
                    payload=next_event.to_dict(),
                    correlation_id=next_event.correlation_id,
                )
            )

            await session.commit()
            log(logger, logging.INFO, "restaurant_processed",
                extra={"order_id": str(order.id), "new_status": order.status,
                       "version": new_version})

    async def _record_processed(self, session, event, order, outcome):
        session.add(
            ProcessedEvent(
                consumer_name=CONSUMER_NAME,
                event_id=event.event_id,
                event_type=event.event_type,
                order_id=order.id,
                outcome=outcome,
            )
        )

    async def _quarantine_event(self, event, failure_code, failure_reason):
        factory = get_session_factory()
        async with factory() as session:
            session.add(
                QuarantineRecord(
                    event_id=event.event_id,
                    event_type=event.event_type,
                    consumer_name=CONSUMER_NAME,
                    source_queue=RESTAURANT_QUEUE,
                    order_id=event.order_id,
                    attempts=1,
                    failure_code=failure_code,
                    failure_reason=failure_reason,
                    original_event=event.to_dict(),
                )
            )
            await session.commit()

    async def _quarantine_malformed(self, raw_body, error, correlation_id):
        factory = get_session_factory()
        async with factory() as session:
            session.add(
                QuarantineRecord(
                    event_id=None,
                    event_type=None,
                    consumer_name=CONSUMER_NAME,
                    source_queue=RESTAURANT_QUEUE,
                    order_id=None,
                    attempts=0,
                    failure_code="MALFORMED_MESSAGE",
                    failure_reason=error[:1024],
                    original_event={"raw_body": raw_body.decode("utf-8", errors="replace")[:2000]},
                )
            )
            await session.commit()


async def main():
    worker = RestaurantWorker()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, worker.request_shutdown)
        except (NotImplementedError, RuntimeError):
            signal.signal(sig, lambda s, f: worker.request_shutdown())
    try:
        await worker.start()
    except Exception as exc:
        log(logger, logging.CRITICAL, "worker_fatal", extra={"error": str(exc)}, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    import signal
    asyncio.run(main())


