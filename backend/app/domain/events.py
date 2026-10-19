"""Immutable domain event envelope: construction, validation, serialization.

Every event crossing RabbitMQ carries:

``event_id`` (UUID, stable across redeliveries), ``schema_version``,
``event_type``, ``order_id``, ``order_version``, ``occurred_at`` (UTC ISO-8601),
``correlation_id`` (root trace id, propagated to children), ``causation_id``
(the event that directly caused this one) and ``data`` (event specific payload).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

SCHEMA_VERSION = "1"
SUPPORTED_SCHEMA_VERSIONS = ("1",)

EVENT_ORDER_CREATED = "order.created"
EVENT_ORDER_PAID = "order.paid"
EVENT_ORDER_PAYMENT_FAILED = "order.payment.failed"
EVENT_ORDER_CONFIRMED = "order.confirmed"
EVENT_ORDER_DRIVER_ASSIGNED = "order.driver.assigned"
EVENT_ORDER_FAILED = "order.failed"

KNOWN_EVENT_TYPES = (
    EVENT_ORDER_CREATED,
    EVENT_ORDER_PAID,
    EVENT_ORDER_PAYMENT_FAILED,
    EVENT_ORDER_CONFIRMED,
    EVENT_ORDER_DRIVER_ASSIGNED,
    EVENT_ORDER_FAILED,
)


class InvalidEnvelope(ValueError):
    """Raised when a message body is malformed or unsupported."""


@dataclass(frozen=True)
class OrderEvent:
    event_id: uuid.UUID
    schema_version: str
    event_type: str
    order_id: uuid.UUID
    order_version: int
    occurred_at: datetime
    correlation_id: uuid.UUID
    causation_id: uuid.UUID | None
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": str(self.event_id),
            "schema_version": self.schema_version,
            "event_type": self.event_type,
            "order_id": str(self.order_id),
            "order_version": self.order_version,
            "occurred_at": self.occurred_at.astimezone(timezone.utc).isoformat(),
            "correlation_id": str(self.correlation_id),
            "causation_id": str(self.causation_id) if self.causation_id else None,
            "data": self.data,
        }


def build_event(
    *,
    event_type: str,
    order_id: uuid.UUID,
    order_version: int,
    data: dict[str, Any],
    correlation_id: uuid.UUID | None = None,
    causation_id: uuid.UUID | None = None,
    event_id: uuid.UUID | None = None,
) -> OrderEvent:
    """Create a new immutable event.

    Child events reuse the parent's ``correlation_id`` and record the parent's
    ``event_id`` as their ``causation_id``.
    """
    if event_type not in KNOWN_EVENT_TYPES:
        raise InvalidEnvelope(f"unsupported event_type: {event_type}")
    return OrderEvent(
        event_id=event_id or uuid.uuid4(),
        schema_version=SCHEMA_VERSION,
        event_type=event_type,
        order_id=order_id,
        order_version=order_version,
        occurred_at=datetime.now(timezone.utc),
        correlation_id=correlation_id or uuid.uuid4(),
        causation_id=causation_id,
        data=data,
    )


def parse_event(payload: Any) -> OrderEvent:
    """Validate a decoded JSON payload into an OrderEvent.

    Raises InvalidEnvelope for anything that must be quarantined rather than
    retried forever (bad JSON shape, unknown schema version, missing ids).
    """
    if not isinstance(payload, dict):
        raise InvalidEnvelope("event payload must be a JSON object")

    required = (
        "event_id",
        "schema_version",
        "event_type",
        "order_id",
        "order_version",
        "occurred_at",
        "correlation_id",
        "data",
    )
    missing = [k for k in required if k not in payload]
    if missing:
        raise InvalidEnvelope(f"missing required fields: {', '.join(missing)}")

    schema_version = str(payload["schema_version"])
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        raise InvalidEnvelope(f"unsupported schema_version: {schema_version}")

    if payload["event_type"] not in KNOWN_EVENT_TYPES:
        raise InvalidEnvelope(f"unsupported event_type: {payload['event_type']}")

    try:
        event_id = uuid.UUID(str(payload["event_id"]))
        order_id = uuid.UUID(str(payload["order_id"]))
        correlation_id = uuid.UUID(str(payload["correlation_id"]))
    except (ValueError, AttributeError) as exc:
        raise InvalidEnvelope(f"invalid uuid field: {exc}") from exc

    causation_raw = payload.get("causation_id")
    causation_id: uuid.UUID | None = None
    if causation_raw is not None:
        try:
            causation_id = uuid.UUID(str(causation_raw))
        except (ValueError, AttributeError) as exc:
            raise InvalidEnvelope(f"invalid causation_id: {exc}") from exc

    try:
        occurred_at = datetime.fromisoformat(str(payload["occurred_at"]))
    except ValueError as exc:
        raise InvalidEnvelope(f"invalid occurred_at: {exc}") from exc
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=timezone.utc)

    try:
        order_version = int(payload["order_version"])
    except (TypeError, ValueError) as exc:
        raise InvalidEnvelope("order_version must be an integer") from exc

    if not isinstance(payload["data"], dict):
        raise InvalidEnvelope("data must be an object")

    return OrderEvent(
        event_id=event_id,
        schema_version=schema_version,
        event_type=payload["event_type"],
        order_id=order_id,
        order_version=order_version,
        occurred_at=occurred_at,
        correlation_id=correlation_id,
        causation_id=causation_id,
        data=payload["data"],
    )
