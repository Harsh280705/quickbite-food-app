"""Retry scheduler — polls retry_jobs and publishes scheduled retries.

Responsibilities:
- Poll retry_jobs with status PENDING and scheduled_at <= now
- Claim jobs using SKIP LOCKED
- For each due job, publish targeted outbox event (default exchange → consumer queue)
- Mark retry_job as PUBLISHED
- If attempt exhausted, mark EXHAUSTED (handled by workers on next processing)
- Graceful shutdown
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys

import aio_pika
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.core.logging import configure_logging, log
from app.db.session import get_session_factory
from app.messaging.connection import BrokerUnavailable, close_quietly, connect_with_backoff
from app.messaging.publisher import PublishError, build_message, publish_message
from app.messaging.topology import declare_topology
from app.models.messaging import RetryJob, OutboxEvent

configure_logging(settings.log_level)
logger = logging.getLogger("quickbite.retry_scheduler")

SCHEDULER_NAME = "retry_scheduler"
BATCH_SIZE = 50
POLL_INTERVAL = settings.scheduler_poll_interval_ms / 1000.0


class RetryScheduler:
    def __init__(self):
        self._connection = None
        self._channel = None
        self._running = False
        self._shutdown_event = asyncio.Event()

    async def start(self):
        self._connection, self._channel = await connect_with_backoff(
            url=settings.amqp_url,
            max_attempts=12,
            base_delay=0.5,
            max_delay=10.0,
        )
        await declare_topology(self._channel)
        self._running = True
        logger.info("retry_scheduler_started",
                    extra={"batch_size": BATCH_SIZE, "poll_interval_ms": settings.scheduler_poll_interval_ms})
        while self._running:
            await self._schedule_cycle()
            await asyncio.sleep(POLL_INTERVAL)
        logger.info("retry_scheduler_stopped")

    def request_shutdown(self):
        self._running = False
        self._shutdown_event.set()

    async def _schedule_cycle(self):
        factory = get_session_factory()
        async with factory() as session:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)

            # Claim due PENDING jobs
            stmt = (
                select(RetryJob)
                .where(
                    RetryJob.status == "PENDING",
                    RetryJob.scheduled_at <= now,
                )
                .order_by(RetryJob.scheduled_at)
                .limit(BATCH_SIZE)
                .with_for_update(skip_locked=True)
            )
            result = await session.execute(stmt)
            jobs = list(result.scalars().all())

            if not jobs:
                return

            for job in jobs:
                await self._publish_retry(job, session)

            await session.commit()

    async def _publish_retry(self, job: RetryJob, session):
        """Publish the retry to the target consumer's queue via default exchange."""
        # Determine target queue from consumer_name
        queue_map = {
            "payment_worker": "payment.queue",
            "restaurant_worker": "restaurant.queue",
            "delivery_worker": "delivery.queue",
            "notification_worker": "notification.queue",
        }
        target_queue = queue_map.get(job.consumer_name)
        if not target_queue:
            log(logger, logging.ERROR, "unknown_consumer_for_retry",
                extra={"consumer_name": job.consumer_name, "job_id": str(job.id)})
            job.status = "QUARANTINED"
            return

        message = build_message(job.payload)

        try:
            # Publish via default exchange directly to the queue
            await publish_message(
                self._channel,
                exchange_name="",  # default exchange
                routing_key=target_queue,
                message=message,
            )
            job.status = "PUBLISHED"
            from datetime import datetime, timezone
            job.published_at = datetime.now(timezone.utc)
            log(logger, logging.INFO, "retry_published",
                extra={"job_id": str(job.id), "consumer": job.consumer_name,
                       "queue": target_queue, "attempt": job.attempt,
                       "event_id": str(job.event_id)})
        except PublishError as exc:
            log(logger, logging.ERROR, "retry_publish_failed",
                extra={"job_id": str(job.id), "error": str(exc)})
            # Leave job as PENDING for next cycle
            job.status = "PENDING"


async def main():
    scheduler = RetryScheduler()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, scheduler.request_shutdown)
        except (NotImplementedError, RuntimeError):
            signal.signal(sig, lambda s, f: scheduler.request_shutdown())
    try:
        await scheduler.start()
    except BrokerUnavailable as exc:
        log(logger, logging.CRITICAL, "broker_unavailable", extra={"error": str(exc)})
        sys.exit(1)
    except Exception as exc:
        log(logger, logging.CRITICAL, "scheduler_fatal", extra={"error": str(exc)}, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    import signal
    asyncio.run(main())


