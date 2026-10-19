"""Notification worker — consumes order.#, persists customer notifications.

Consumes order.# from notification.queue (multi-segment events).
Persists Notification records with customer_id, order_id, event_type, title, body.
Enforces uniqueness per (customer_id, event_id).
Never changes order business status.
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
from app.domain.events import parse_event
from app.messaging.connection import BrokerUnavailable, close_quietly, connect_with_backoff
from app.messaging.topology import (
    NOTIFICATION_QUEUE,
    declare_topology,
)
from app.models import Order, ProcessedEvent, Notification
from app.models.messaging import QuarantineRecord

configure_logging(settings.log_level)
logger = logging.getLogger("quickbite.notification_worker")

CONSUMER_NAME = "notification_worker"
PREFETCH_COUNT = settings.worker_prefetch_count

# Demo failure mode
DEMO_NOTIFICATION_MODE = settings.demo_notification_mode


NOTIFICATION_TEMPLATES = {
    "order.created": ("Order Received", "Your order has been received and is being processed."),
    "order.paid": ("Payment Successful", "Your payment was successful. The restaurant is preparing your order."),
    "order.payment.failed": ("Payment Failed", "We couldn't process your payment. Please try again."),
    "order.confirmed": ("Order Confirmed", "The restaurant has confirmed your order."),
    "order.driver.assigned": ("Driver Assigned", "A driver has been assigned to deliver your order."),
    "order.failed": ("Order Failed", "Your order could not be completed. Please contact support."),
}


class NotificationWorker:
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
        self._queue = topology["queues"][NOTIFICATION_QUEUE]
        self._running = True
        logger.info("notification_worker_started", extra={"queue": NOTIFICATION_QUEUE})
        await self._queue.consume(self._on_message, no_ack=False)
        await self._shutdown_event.wait()
        logger.info("notification_worker_shutting_down", extra={"in_flight": self._in_flight})
        while self._in_flight > 0:
            await asyncio.sleep(0.5)
        await self.stop()

    async def stop(self):
        self._running = False
        await close_quietly(self._channel, self._connection)
        logger.info("notification_worker_stopped")

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

        if not event.event_type.startswith("order."):
            log(logger, logging.WARNING, "ignored_event_type",
                extra={"event_type": event.event_type})
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

        await asyncio.sleep(settings.sim_notification_delay_ms / 1000.0)
        try:
            await self._handle_event(event)
        except Exception as exc:
            log(logger, logging.ERROR, "notification_processing_failed",
                extra={"event_id": str(event.event_id), "error": str(exc)}, exc_info=True)
            # Notification failure must NOT change order status
            # Quarantine the event but don't modify business state
            await self._quarantine_event(event, "NOTIFICATION_FAILED", str(exc))
            # Still ACK to avoid infinite retry (per spec: notification failures quarantined)
            return

    async def _handle_event(self, event):
        factory = get_session_factory()
        async with factory() as session:
            # Get order to find customer
            from app.domain.state_machine import get_order_for_update
            order = await get_order_for_update(session, event.order_id)
            if order is None:
                log(logger, logging.WARNING, "order_not_found_for_notification",
                    extra={"order_id": str(event.order_id)})
                await self._record_processed(session, event, None, "ORDER_NOT_FOUND")
                return

            # Get notification template
            title, body = NOTIFICATION_TEMPLATES.get(
                event.event_type,
                ("Order Update", f"Your order status changed to {event.event_type}.")
            )

            # Demo: simulate notification failure
            if DEMO_NOTIFICATION_MODE == "always_fail":
                raise RuntimeError("Simulated notification failure")

            # Persist notification (unique constraint on customer_id + event_id)
            notification = Notification(
                customer_id=order.customer_id,
                order_id=order.id,
                event_id=event.event_id,
                event_type=event.event_type,
                title=title,
                body=body,
                status="DELIVERED",
            )
            session.add(notification)

            await self._record_processed(session, event, order, "APPLIED")
            await session.commit()

            log(logger, logging.INFO, "notification_sent",
                extra={"customer_id": str(order.customer_id), "order_id": str(order.id),
                       "event_type": event.event_type, "event_id": str(event.event_id)})

    async def _record_processed(self, session, event, order, outcome):
        session.add(
            ProcessedEvent(
                consumer_name=CONSUMER_NAME,
                event_id=event.event_id,
                event_type=event.event_type,
                order_id=order.id if order else None,
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
                    source_queue=NOTIFICATION_QUEUE,
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
                    source_queue=NOTIFICATION_QUEUE,
                    order_id=None,
                    attempts=0,
                    failure_code="MALFORMED_MESSAGE",
                    failure_reason=error[:1024],
                    original_event={"raw_body": raw_body.decode("utf-8", errors="replace")[:2000]},
                )
            )
            await session.commit()


async def main():
    worker = NotificationWorker()
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


