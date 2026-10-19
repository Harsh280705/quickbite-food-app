"""Delivery worker — consumes order.confirmed, assigns a simulated driver, advances order state.

Consumes order.confirmed from delivery.queue.
Transitions CONFIRMED → DRIVER_ASSIGNED or CONFIRMED → FAILED.
Ensures only one driver assignment per order.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import uuid

import aio_pika
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.core.logging import configure_logging, log, set_correlation_id
from app.db.session import get_session_factory
from app.domain.events import (
    EVENT_ORDER_CONFIRMED,
    EVENT_ORDER_DRIVER_ASSIGNED,
    EVENT_ORDER_FAILED,
    build_event,
    parse_event,
)
from app.domain.state_machine import apply_transition
from app.messaging.connection import BrokerUnavailable, close_quietly, connect_with_backoff
from app.messaging.publisher import PublishError, build_message, publish_message
from app.messaging.topology import (
    DELIVERY_QUEUE,
    ORDERS_EXCHANGE,
    declare_topology,
)
from app.models import Order, ProcessedEvent, Driver, DriverAssignment
from app.models.messaging import OutboxEvent, QuarantineRecord

configure_logging(settings.log_level)
logger = logging.getLogger("quickbite.delivery_worker")

CONSUMER_NAME = "delivery_worker"
PREFETCH_COUNT = settings.worker_prefetch_count


class DeliveryWorker:
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
        self._queue = topology["queues"][DELIVERY_QUEUE]
        self._running = True
        logger.info("delivery_worker_started", extra={"queue": DELIVERY_QUEUE})
        await self._queue.consume(self._on_message, no_ack=False)
        await self._shutdown_event.wait()
        logger.info("delivery_worker_shutting_down", extra={"in_flight": self._in_flight})
        while self._in_flight > 0:
            await asyncio.sleep(0.5)
        await self.stop()

    async def stop(self):
        self._running = False
        await close_quietly(self._channel, self._connection)
        logger.info("delivery_worker_stopped")

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

        if event.event_type != EVENT_ORDER_CONFIRMED:
            log(logger, logging.WARNING, "unexpected_event_type",
                extra={"expected": EVENT_ORDER_CONFIRMED, "got": event.event_type})
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

        await asyncio.sleep(settings.sim_delivery_delay_ms / 1000.0)
        try:
            await self._handle_event(event)
        except Exception as exc:
            log(logger, logging.ERROR, "delivery_processing_failed",
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

            if order.status != "CONFIRMED":
                log(logger, logging.WARNING, "order_not_confirmed",
                    extra={"order_id": str(order.id), "current_status": order.status})
                await self._record_processed(session, event, order, "STALE_SKIPPED")
                return

            # Check if driver already assigned (idempotency)
            if order.driver_id is not None:
                log(logger, logging.INFO, "driver_already_assigned",
                    extra={"order_id": str(order.id), "driver_id": str(order.driver_id)})
                await self._record_processed(session, event, order, "STALE_SKIPPED")
                return

            # Pick an active driver (simple round-robin via attempt counter)
            drivers = await session.execute(
                select(Driver).where(Driver.is_active.is_(True))
            )
            driver_list = list(drivers.scalars())
            if not driver_list:
                log(logger, logging.ERROR, "no_active_drivers",
                    extra={"order_id": str(order.id)})
                await self._quarantine_event(event, "NO_DRIVERS", "No active drivers available")
                return

            # Use a simple selection: hash of order_id mod driver count
            driver = driver_list[uuid.uuid4().int % len(driver_list)]

            # Demo failure
            if settings.demo_delivery_mode == "always_fail":
                new_version = await apply_transition(
                    session, order, "FAILED",
                    actor=CONSUMER_NAME,
                    note="no driver available",
                    failure_code="NO_DRIVER",
                    failure_message="Simulated delivery failure",
                )
                next_event_type = EVENT_ORDER_FAILED
            else:
                new_version = await apply_transition(
                    session, order, "DRIVER_ASSIGNED",
                    actor=CONSUMER_NAME,
                    note="driver assigned",
                    driver_id=driver.id,
                )
                # Record driver assignment
                session.add(
                    DriverAssignment(
                        order_id=order.id,
                        driver_id=driver.id,
                        driver_name=driver.name,
                        vehicle=driver.vehicle,
                    )
                )
                next_event_type = EVENT_ORDER_DRIVER_ASSIGNED

            await self._record_processed(session, event, order, "APPLIED")

            next_event = build_event(
                event_type=next_event_type,
                order_id=order.id,
                order_version=new_version,
                data={"driver_id": str(driver.id), "driver_name": driver.name, "vehicle": driver.vehicle}
                if next_event_type == EVENT_ORDER_DRIVER_ASSIGNED
                else {"status": order.status},
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
            log(logger, logging.INFO, "delivery_processed",
                extra={"order_id": str(order.id), "new_status": order.status,
                       "version": new_version, "driver": driver.name if next_event_type == EVENT_ORDER_DRIVER_ASSIGNED else None})

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
                    source_queue=DELIVERY_QUEUE,
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
                    source_queue=DELIVERY_QUEUE,
                    order_id=None,
                    attempts=0,
                    failure_code="MALFORMED_MESSAGE",
                    failure_reason=error[:1024],
                    original_event={"raw_body": raw_body.decode("utf-8", errors="replace")[:2000]},
                )
            )
            await session.commit()


async def main():
    worker = DeliveryWorker()
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


