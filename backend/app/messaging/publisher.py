"""Publishing helpers: AMQP message construction for domain events."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

import aio_pika
from aio_pika import DeliveryMode
from aio_pika.abc import AbstractChannel, AbstractMessage

from app.domain.events import OrderEvent

logger = logging.getLogger("quickbite.publisher")

CONTENT_TYPE = "application/json"


class PublishError(RuntimeError):
    """Raised when a publish is not confirmed or is returned as unroutable."""


def build_message(event: OrderEvent | dict[str, Any]) -> AbstractMessage:
    """Build a persistent JSON AMQP message.

    ``message_id`` always equals ``event_id`` so consumers can deduplicate
    even if the transport redelivers the body.
    """
    if isinstance(event, OrderEvent):
        payload = event.to_dict()
        event_id = str(event.event_id)
        event_type = event.event_type
        correlation_id = str(event.correlation_id)
    else:
        payload = event
        event_id = str(payload.get("event_id", uuid.uuid4()))
        event_type = str(payload.get("event_type", ""))
        correlation_id = str(payload.get("correlation_id", ""))

    return aio_pika.Message(
        body=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        content_type=CONTENT_TYPE,
        content_encoding="utf-8",
        delivery_mode=DeliveryMode.PERSISTENT,
        message_id=event_id,
        type=event_type,
        correlation_id=correlation_id,
        timestamp=None,
    )


async def get_default_exchange(channel: AbstractChannel) -> Any:
    """Return the broker's default (unnamed) exchange instance.

    Publishing with ``exchange_name=""`` routes directly to a queue named by
    the routing key — the mechanism used for targeted consumer retries.
    """
    return await channel.declare_exchange(
        "", aio_pika.ExchangeType.DIRECT, durable=True, passive=False
    )


async def publish_message(
    channel: AbstractChannel,
    *,
    exchange_name: str,
    routing_key: str,
    message: AbstractMessage,
    timeout: float = 5.0,
) -> None:
    """Publish with mandatory routing + publisher confirms.

    ``exchange_name=""`` targets the default exchange (direct-to-queue
    delivery, used for retries).

    Raises PublishError when the broker does not confirm or returns the
    message as unroutable (``on_return_raises=True`` channels convert returns
    into ``aiormq.exceptions.DeliveryError``).
    """
    if exchange_name:
        # ensure=False: the topology module declares exchanges at startup; this
        # avoids a passive check (and channel closure) on every publish.
        exchange = await channel.get_exchange(exchange_name, ensure=False)
    else:
        # Default exchange: routing key is the queue name (targeted retries).
        exchange = await get_default_exchange(channel)

    try:
        confirmation = await exchange.publish(
            message, routing_key=routing_key, mandatory=True, timeout=timeout
        )
    except Exception as exc:  # DeliveryError or channel/confirm failures
        raise PublishError(
            f"publish to {exchange_name or '<default>'}/{routing_key} failed: {exc}"
        ) from exc

    if confirmation is None:
        # Publisher confirms disabled — should never happen with our channels.
        raise PublishError("publisher confirms are not enabled on this channel")

    logger.debug(
        "message_published",
        extra={
            "exchange": exchange_name or "<default>",
            "routing_key": routing_key,
            "message_id": message.message_id,
        },
    )
