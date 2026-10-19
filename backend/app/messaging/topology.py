"""RabbitMQ topology declaration.

All declarations are idempotent (passive-safe re-declaration of identical
parameters) so workers, dispatchers and schedulers can each declare the
topology they need at startup.

Exchanges
    quickbite.orders : durable topic exchange for domain events
    quickbite.dead    : durable direct exchange for quarantined envelopes

Queues (durable, non-exclusive, non-auto-delete)
    payment.queue       <- order.created
    restaurant.queue    <- order.paid
    delivery.queue      <- order.confirmed
    notification.queue  <- order.#      (multi-segment aware)
    orders.dead-letter.queue <- "failed"
"""

from __future__ import annotations

import logging
from typing import Awaitable, Callable

import aio_pika
from aio_pika import ExchangeType

from app.domain.events import (
    EVENT_ORDER_CONFIRMED,
    EVENT_ORDER_CREATED,
    EVENT_ORDER_PAID,
)

logger = logging.getLogger("quickbite.topology")

ORDERS_EXCHANGE = "quickbite.orders"
DEAD_EXCHANGE = "quickbite.dead"
DEAD_QUEUE = "orders.dead-letter.queue"
DEAD_ROUTING_KEY = "failed"

PAYMENT_QUEUE = "payment.queue"
RESTAURANT_QUEUE = "restaurant.queue"
DELIVERY_QUEUE = "delivery.queue"
NOTIFICATION_QUEUE = "notification.queue"

BINDINGS: tuple[tuple[str, str], ...] = (
    (PAYMENT_QUEUE, EVENT_ORDER_CREATED),
    (RESTAURANT_QUEUE, EVENT_ORDER_PAID),
    (DELIVERY_QUEUE, EVENT_ORDER_CONFIRMED),
    (NOTIFICATION_QUEUE, "order.#"),
)

MESSAGE_TTL_MS = 1000 * 60 * 60 * 6  # queue-level cap: 6 hours


async def declare_topology(channel: aio_pika.abc.Channel) -> dict:
    """Declare exchanges, queues and bindings. Safe to call repeatedly."""
    orders_exchange = await channel.declare_exchange(
        ORDERS_EXCHANGE, ExchangeType.TOPIC, durable=True, passive=False
    )
    dead_exchange = await channel.declare_exchange(
        DEAD_EXCHANGE, ExchangeType.DIRECT, durable=True, passive=False
    )

    queues = {}
    for queue_name, _ in BINDINGS:
        queue = await channel.declare_queue(
            queue_name,
            durable=True,
            exclusive=False,
            auto_delete=False,
            arguments={"x-message-ttl": MESSAGE_TTL_MS},
        )
        await queue.bind(orders_exchange, routing_key=_)
        queues[queue_name] = queue

    dead_queue = await channel.declare_queue(
        DEAD_QUEUE, durable=True, exclusive=False, auto_delete=False
    )
    await dead_queue.bind(dead_exchange, routing_key=DEAD_ROUTING_KEY)
    queues[DEAD_QUEUE] = dead_queue

    logger.info(
        "topology_declared",
        extra={
            "queues": sorted(queues),
            "exchanges": [ORDERS_EXCHANGE, DEAD_EXCHANGE],
        },
    )
    return {
        "orders_exchange": orders_exchange,
        "dead_exchange": dead_exchange,
        "queues": queues,
    }


async def ensure_topology(
    channel_factory: Callable[[], Awaitable[aio_pika.abc.Channel]],
) -> None:
    channel = await channel_factory()
    await declare_topology(channel)
