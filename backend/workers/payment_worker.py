"""Payment worker — consumes order.created, simulates payment, advances order state.

Responsibilities:
- Consume order.created from payment.queue
- Validate event envelope and schema
- Deduplicate via processed_events (consumer_name, event_id)
- Lock order row, verify current state is PENDING
- Simulate payment (configurable: success / fail_twice / always_fail)
- Transition PENDING → PAID or PENDING → PAYMENT_FAILED
- Persist SimulatedPayment, order status history, outbox events in one tx
- Acknowledge message only after successful commit
- On transient failure: persist retry job + scheduled outbox publication, then ACK
- On retry exhaustion: transition to PAYMENT_FAILED, emit order.payment.failed, quarantine
- Graceful shutdown: stop accepting new work, finish in-flight
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Optional

import aio_pika
from aio_pika import ExchangeType
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Ensure backend package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.core.logging import configure_logging, log, set_correlation_id
from app.db.session import get_session_factory
from app.domain.events import (
    EVENT_ORDER_CREATED,
    EVENT_ORDER_PAID,
    EVENT_ORDER_PAYMENT_FAILED,
    build_event,
    parse_event,
)
from app.domain.state_machine import apply_transition
from app.messaging.connection import BrokerUnavailable, close_quietly, connect_with_backoff
from app.messaging.publisher import PublishError, build_message, publish_message
from app.messaging.topology import (
    PAYMENT_QUEUE,
    ORDERS_EXCHANGE,
    declare_topology,
)
from app.models import Order, ProcessedEvent, SimulatedPayment
from app.models.messaging import OutboxEvent, QuarantineRecord, RetryJob

configure_logging(settings.log_level)
logger = logging.getLogger("quickbite.payment_worker")

CONSUMER_NAME = "payment_worker"
PREFETCH_COUNT = settings.worker_prefetch_count

# Demo crash modes
CRASH_NONE = "none"
CRASH_BEFORE_COMMIT = "before_commit"
CRASH_AFTER_COMMIT_BEFORE_ACK = "after_commit_before_ack"


class PaymentWorker:
    def __init__(self):
        self._connection: Optional[aio_pika.abc.AbstractRobustConnection] = None
        self._channel: Optional[aio_pika.abc.AbstractChannel] = None
        self._queue: Optional[aio_pika.abc.AbstractQueue] = None
        self._running = False
        self._shutdown_event = asyncio.Event()
        self._in_flight = 0

    async def start(self) -> None:
        """Connect, declare topology, start consuming."""
        self._connection, self._channel = await connect_with_backoff(
            url=settings.amqp_url,
            max_attempts=12,
            base_delay=0.5,
            max_delay=10.0,
        )
        self._channel.set_qos(prefetch_count=PREFETCH_COUNT)

        # Declare topology (idempotent)
        topology = await declare_topology(self._channel)
        self._queue = topology["queues"][PAYMENT_QUEUE]

        self._running = True
        logger.info("payment_worker_started", extra={"queue": PAYMENT_QUEUE})

        # Start consumer
        await self._queue.consume(self._on_message, no_ack=False)

        # Wait for shutdown signal
        await self._shutdown_event.wait()

        # Graceful drain
        logger.info("payment_worker_shutting_down", extra={"in_flight": self._in_flight})
        while self._in_flight > 0:
            await asyncio.sleep(0.5)
        await self.stop()

    async def stop(self) -> None:
        self._running = False
        await close_quietly(self._channel, self._connection)
        logger.info("payment_worker_stopped")

    def request_shutdown(self) -> None:
        self._shutdown_event.set()

    async def _on_message(self, message: aio_pika.abc.AbstractIncomingMessage) -> None:
        """Process a single message with full deduplication, transaction, and ACK semantics."""
        if not self._running:
            await message.reject(requeue=True)
            return

        self._in_flight += 1
        try:
            async with message.process(requeue=False):
                await self._process_message(message)
        finally:
            self._in_flight -= 1

    async def _process_message(self, message: aio_pika.abc.AbstractIncomingMessage) -> None:
        """Core message processing logic."""
        raw_body = message.body
        correlation_id = message.correlation_id or "-"
        set_correlation_id(correlation_id)

        # Parse and validate event
        try:
            import json
            payload = json.loads(raw_body.decode("utf-8"))
            event = parse_event(payload)
        except Exception as exc:
            log(logger, logging.ERROR, "malformed_message",
                extra={"error": str(exc), "correlation_id": correlation_id})
            await self._quarantine_malformed(raw_body, str(exc), correlation_id, message)
            return

        # Verify event type
        if event.event_type != EVENT_ORDER_CREATED:
            log(logger, logging.WARNING, "unexpected_event_type",
                extra={"expected": EVENT_ORDER_CREATED, "got": event.event_type,
                       "event_id": str(event.event_id)})
            # Not our event; could be misrouted. Reject without requeue to avoid loop.
            return

        # Idempotency: check if already processed
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
                    extra={"event_id": str(event.event_id), "consumer": CONSUMER_NAME})
                return  # ACK happens via message.process context manager

        # Process with database transaction
        await asyncio.sleep(settings.sim_payment_delay_ms / 1000.0)
        try:
            await self._handle_payment_event(event, message)
        except Exception as exc:
            log(logger, logging.ERROR, "payment_processing_failed",
                extra={"event_id": str(event.event_id), "error": str(exc)}, exc_info=True)
            raise  # message.process will reject (no requeue due to requeue=False)

    async def _handle_payment_event(
        self, event, message: aio_pika.abc.AbstractIncomingMessage
    ) -> None:
        """Handle a single order.created event with full transaction."""
        factory = get_session_factory()
        async with factory() as session:
            # Lock order row for update
            from app.domain.state_machine import get_order_for_update
            order = await get_order_for_update(session, event.order_id)
            if order is None:
                log(logger, logging.ERROR, "order_not_found",
                    extra={"order_id": str(event.order_id)})
                await self._quarantine_event(event, message, "ORDER_NOT_FOUND", "Order not found")
                return

            # Validate current state
            if order.status != "PENDING":
                log(logger, logging.WARNING, "order_not_pending",
                    extra={"order_id": str(order.id), "current_status": order.status})
                # Record as processed (no-op for stale events) and ACK
                await self._record_processed(session, event, order, "STALE_SKIPPED")
                return

            # Demo failure simulation
            fail_mode = settings.demo_payment_mode
            fail_count = settings.demo_payment_fail_count
            crash_mode = settings.demo_crash_mode
            crash_order = settings.demo_crash_order_id

            # Determine attempt number from retry_jobs
            attempt = await self._get_current_attempt(session, event.event_id)

            # Simulate payment outcome
            payment_succeeds = self._simulate_payment(fail_mode, fail_count, attempt)

            # Crash injection checkpoints
            if crash_mode == CRASH_BEFORE_COMMIT and str(order.id) == crash_order:
                log(logger, logging.CRITICAL, "crash_checkpoint_before_commit",
                    extra={"order_id": str(order.id)})
                os._exit(1)

            # Apply transition
            if payment_succeeds:
                new_version = await apply_transition(
                    session, order, "PAID",
                    actor=CONSUMER_NAME,
                    note="payment succeeded",
                )
                payment_status = "SUCCEEDED"
                next_event_type = EVENT_ORDER_PAID
            else:
                new_version = await apply_transition(
                    session, order, "PAYMENT_FAILED",
                    actor=CONSUMER_NAME,
                    note="payment failed",
                    failure_code="PAYMENT_DECLINED",
                    failure_message="Simulated payment failure",
                )
                payment_status = "FAILED"
                next_event_type = EVENT_ORDER_PAYMENT_FAILED

            # Create SimulatedPayment record
            provider_ref = f"sim_{uuid.uuid4().hex[:16]}"
            payment = SimulatedPayment(
                order_id=order.id,
                status=payment_status,
                amount_minor=order.total_amount_minor,
                currency=order.currency,
                provider_reference=provider_ref,
                attempt=attempt + 1,
            )
            session.add(payment)

            # Record processed event
            await self._record_processed(session, event, order, "APPLIED")

            # Emit next event via outbox
            next_event = build_event(
                event_type=next_event_type,
                order_id=order.id,
                order_version=new_version,
                data={"amount_minor": order.total_amount_minor, "currency": order.currency},
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

            # Crash after commit, before ACK
            if crash_mode == CRASH_AFTER_COMMIT_BEFORE_ACK and str(order.id) == crash_order:
                log(logger, logging.CRITICAL, "crash_checkpoint_after_commit_before_ack",
                    extra={"order_id": str(order.id)})
                os._exit(1)

            log(logger, logging.INFO, "payment_processed",
                extra={
                    "order_id": str(order.id),
                    "new_status": order.status,
                    "version": new_version,
                    "payment_status": payment_status,
                    "attempt": attempt + 1,
                })

    async def _record_processed(
        self, session: AsyncSession, event, order: Order, outcome: str
    ) -> None:
        session.add(
            ProcessedEvent(
                consumer_name=CONSUMER_NAME,
                event_id=event.event_id,
                event_type=event.event_type,
                order_id=order.id,
                outcome=outcome,
            )
        )

    async def _get_current_attempt(self, session: AsyncSession, event_id: uuid.UUID) -> int:
        """Get the current attempt number from retry_jobs (0 if first try)."""
        from app.models.messaging import RetryJob
        result = await session.execute(
            select(RetryJob.attempt).where(
                RetryJob.consumer_name == CONSUMER_NAME,
                RetryJob.event_id == event_id,
            ).order_by(RetryJob.attempt.desc())
        )
        max_attempt = result.scalar_one_or_none()
        return max_attempt if max_attempt is not None else 0

    def _simulate_payment(self, mode: str, fail_count: int, attempt: int) -> bool:
        """Determine payment outcome based on mode and attempt."""
        if mode == "success":
            return True
        if mode == "always_fail":
            return False
        if mode == "fail_twice":
            # attempt 0 = first try, attempt 1 = first retry, attempt 2 = second retry
            return attempt >= fail_count
        return True  # default safe

    async def _quarantine_event(
        self, event, message: aio_pika.abc.AbstractIncomingMessage,
        failure_code: str, failure_reason: str
    ) -> None:
        """Quarantine a failed event."""
        factory = get_session_factory()
        async with factory() as session:
            session.add(
                QuarantineRecord(
                    event_id=event.event_id,
                    event_type=event.event_type,
                    consumer_name=CONSUMER_NAME,
                    source_queue=PAYMENT_QUEUE,
                    order_id=event.order_id,
                    attempts=1,
                    failure_code=failure_code,
                    failure_reason=failure_reason,
                    original_event=event.to_dict(),
                )
            )
            await session.commit()

    async def _quarantine_malformed(
        self, raw_body: bytes, error: str, correlation_id: str,
        message: aio_pika.abc.AbstractIncomingMessage
    ) -> None:
        """Quarantine a malformed message without a valid order reference."""
        factory = get_session_factory()
        async with factory() as session:
            session.add(
                QuarantineRecord(
                    event_id=None,
                    event_type=None,
                    consumer_name=CONSUMER_NAME,
                    source_queue=PAYMENT_QUEUE,
                    order_id=None,
                    attempts=0,
                    failure_code="MALFORMED_MESSAGE",
                    failure_reason=error[:1024],
                    original_event={"raw_body": raw_body.decode("utf-8", errors="replace")[:2000]},
                )
            )
            await session.commit()


async def main() -> None:
    worker = PaymentWorker()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, worker.request_shutdown)
        except (NotImplementedError, RuntimeError):
            signal.signal(sig, lambda s, f: worker.request_shutdown())

    try:
        await worker.start()
    except BrokerUnavailable as exc:
        log(logger, logging.CRITICAL, "broker_unavailable", extra={"error": str(exc)})
        sys.exit(1)
    except Exception as exc:
        log(logger, logging.CRITICAL, "worker_fatal", extra={"error": str(exc)}, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
