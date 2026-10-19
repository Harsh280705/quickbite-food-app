"""Messaging reliability entities: outbox, retry jobs, quarantine records."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.entities import utcnow


class OutboxEvent(Base):
    """Transactional outbox row.

    ``id`` is the *publication identity* (unique by primary key) while
    ``event_id`` identifies the domain event.  A domain event may legitimately
    have several publications: retries re-publish the same ``event_id`` and the
    crash window (published but not yet marked sent) can produce a duplicate
    publication.  Consumers deduplicate on ``event_id``.
    """

    __tablename__ = "outbox_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    order_version: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Target: either the domain topic exchange or a direct (default-exchange)
    # delivery to a single queue, used for targeted retries.
    exchange: Mapped[str] = mapped_column(String(128), nullable=False, default="quickbite.orders")
    routing_key: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    # Claim lease used by competing dispatchers (SKIP LOCKED + lease window).
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(512), nullable=True)
    correlation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','SENDING','SENT','FAILED')", name="ck_outbox_status"
        ),
        Index("ix_outbox_claim", "status", "available_at"),
        # A given (event_id, publication target) is only ever scheduled once by
        # the retry scheduler; prevents duplicate retry publications.
        Index("ix_outbox_event_target", "event_id", "exchange", "routing_key"),
    )


class RetryJob(Base):
    """Durable retry state for a failed consumer attempt."""

    __tablename__ = "retry_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    consumer_name: Mapped[str] = mapped_column(String(32), nullable=False)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_error: Mapped[str | None] = mapped_column(String(512), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        # One job per (consumer, event, attempt): duplicate failures never
        # create duplicate retry publications.
        UniqueConstraint("consumer_name", "event_id", "attempt", name="uq_retry_consumer_event_attempt"),
        CheckConstraint("attempt >= 1", name="ck_retry_attempt_positive"),
        CheckConstraint(
            "status IN ('PENDING','PUBLISHED','EXHAUSTED','QUARANTINED')",
            name="ck_retry_status",
        ),
        Index("ix_retry_due", "status", "scheduled_at"),
    )


class QuarantineRecord(Base):
    """Durable record of an event that exhausted retries or was malformed."""

    __tablename__ = "quarantine_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    event_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    consumer_name: Mapped[str] = mapped_column(String(32), nullable=False)
    source_queue: Mapped[str] = mapped_column(String(128), nullable=False)
    order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_code: Mapped[str] = mapped_column(String(64), nullable=False)
    failure_reason: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    original_event: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    quarantined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )

    __table_args__ = (
        # Same event is quarantined at most once per consumer.
        UniqueConstraint("consumer_name", "event_id", name="uq_quarantine_consumer_event"),
        Index("ix_quarantine_created", "quarantined_at"),
    )
