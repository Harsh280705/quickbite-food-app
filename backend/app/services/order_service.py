"""Order domain services: checkout (idempotent) and ownership-scoped reads.

Checkout contract (assignment v2.0 section 9)
---------------------------------------------
``POST /api/v1/orders`` requires an ``Idempotency-Key`` header scoped to the
authenticated customer.  One PostgreSQL transaction persists:

1. the order,
2. its initial status-history row,
3. the idempotency record (request hash + stored acceptance response),
4. the initial ``order.created`` outbox event.

Nothing in this function talks to RabbitMQ or blocks on simulated payment
delay: acceptance ends when the transaction commits (HTTP 202).
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.core.pagination import PaginationParams
from app.domain.events import EVENT_ORDER_CREATED, build_event
from app.models import (
    CheckoutIdempotency,
    Driver,
    DriverAssignment,
    MenuItem,
    Notification,
    Order,
    OrderItem,
    OrderStatusHistory,
    Restaurant,
    User,
)
from app.models.messaging import OutboxEvent
from app.schemas.orders import CheckoutAccepted, OrderCreate

logger = logging.getLogger("quickbite.orders")


def canonical_request_hash(payload: OrderCreate) -> str:
    """Stable hash of the logical checkout request.

    Only client-meaningful fields participate (never prices or totals — the
    server always recomputes those from current menu data).
    """
    canonical = {
        "restaurant_id": str(payload.restaurant_id),
        "delivery_address": " ".join(payload.delivery_address.split()),
        "items": sorted(
            [
                {"menu_item_id": str(i.menu_item_id), "quantity": i.quantity}
                for i in payload.items
            ],
            key=lambda x: x["menu_item_id"],
        ),
    }
    raw = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def validate_delivery_address(address: str) -> str:
    cleaned = " ".join(address.split()).strip()
    if len(cleaned) < settings.min_delivery_address_length:
        raise AppError(
            422,
            "invalid_delivery_address",
            "Delivery address is too short",
            {
                "minimum_length": settings.min_delivery_address_length,
                "hint": "Provide a complete street address (house/flat, street, area, city).",
            },
        )
    if len(cleaned) > settings.max_delivery_address_length:
        raise AppError(
            422,
            "invalid_delivery_address",
            "Delivery address is too long",
            {"maximum_length": settings.max_delivery_address_length},
        )
    if any(ord(ch) < 32 for ch in cleaned):
        raise AppError(
            422,
            "invalid_delivery_address",
            "Delivery address contains invalid characters",
        )
    return cleaned


async def _load_idempotency_record(
    session: AsyncSession, customer_id: uuid.UUID, key: str
) -> CheckoutIdempotency | None:
    result = await session.execute(
        select(CheckoutIdempotency).where(
            CheckoutIdempotency.customer_id == customer_id,
            CheckoutIdempotency.idempotency_key == key,
        )
    )
    return result.scalar_one_or_none()


def _accepted_from_record(record: CheckoutIdempotency) -> CheckoutAccepted:
    body = dict(record.response_body)
    return CheckoutAccepted(
        order_id=body["order_id"],
        status=body["status"],
        total_amount_minor=body["total_amount_minor"],
        currency=body["currency"],
        version=body["version"],
        detail=body.get("detail", "Order accepted for asynchronous processing."),
    )


async def _validate_and_price(
    session: AsyncSession, payload: OrderCreate
) -> tuple[Restaurant, list[MenuItem], int, str]:
    """Validate the request against server-side catalog data and price it."""
    restaurant = await session.get(Restaurant, payload.restaurant_id)
    if restaurant is None:
        raise AppError(404, "restaurant_not_found", "Restaurant does not exist")
    if not restaurant.is_active:
        raise AppError(
            422, "restaurant_inactive", "This restaurant is not accepting orders"
        )
    if not getattr(restaurant, "accepts_orders", True):
        raise AppError(
            422, "restaurant_unavailable", "This restaurant is temporarily unavailable for new orders"
        )

    menu_ids = [i.menu_item_id for i in payload.items]
    if len(set(menu_ids)) != len(menu_ids):
        raise AppError(
            422,
            "duplicate_menu_item",
            "Each menu item may appear only once per order",
        )
    if len(menu_ids) > settings.max_distinct_order_items:
        raise AppError(
            422,
            "too_many_items",
            "Order exceeds the maximum number of distinct items",
            {"maximum": settings.max_distinct_order_items},
        )

    rows = await session.execute(select(MenuItem).where(MenuItem.id.in_(menu_ids)))
    items_by_id = {m.id: m for m in rows.scalars()}

    missing = [str(i) for i in menu_ids if i not in items_by_id]
    if missing:
        raise AppError(
            422,
            "unknown_menu_item",
            "One or more menu items do not exist",
            {"menu_item_ids": missing},
        )

    mixed = [
        str(mid)
        for mid, m in items_by_id.items()
        if m.restaurant_id != payload.restaurant_id
    ]
    if mixed:
        raise AppError(
            422,
            "mixed_restaurant_items",
            "An order cannot contain items from multiple restaurants",
            {"menu_item_ids": mixed},
        )

    unavailable = [
        str(mid)
        for mid, m in items_by_id.items()
        if (not m.is_available) or getattr(m, "is_discontinued", False)
    ]
    if unavailable:
        raise AppError(
            422,
            "item_not_available",
            "One or more menu items are currently unavailable",
            {"menu_item_ids": unavailable},
        )

    total = 0
    currency = "INR"
    for line in payload.items:
        menu_item = items_by_id[line.menu_item_id]
        if not (settings.min_item_quantity <= line.quantity <= settings.max_item_quantity):
            raise AppError(
                422,
                "invalid_quantity",
                "Quantity outside the allowed range",
                {
                    "minimum": settings.min_item_quantity,
                    "maximum": settings.max_item_quantity,
                },
            )
        if menu_item.price_minor <= 0:
            raise AppError(422, "item_price_invalid", "Menu item price is invalid")
        total += menu_item.price_minor * line.quantity
        currency = menu_item.currency

    if total <= 0:
        raise AppError(422, "empty_order", "Order total must be positive")
    return restaurant, [items_by_id[i] for i in menu_ids], total, currency


async def create_order(
    session: AsyncSession,
    *,
    customer: User,
    payload: OrderCreate,
    idempotency_key: str,
) -> tuple[CheckoutAccepted, bool]:
    """Idempotent checkout. Returns ``(accepted, replayed)``."""
    key = idempotency_key.strip()
    if not key or len(key) > 128:
        raise AppError(
            400,
            "invalid_idempotency_key",
            "Idempotency-Key must be 1-128 characters",
        )

    request_hash = canonical_request_hash(payload)

    existing = await _load_idempotency_record(session, customer.id, key)
    if existing is not None:
        if existing.request_hash != request_hash:
            raise AppError(
                409,
                "idempotency_key_conflict",
                "This Idempotency-Key was already used with a different request payload",
                {"idempotency_key": key},
            )
        logger.info(
            "checkout_idempotent_replay",
            extra={"order_id": str(existing.order_id), "customer_id": str(customer.id)},
        )
        return _accepted_from_record(existing), True

    delivery_address = validate_delivery_address(payload.delivery_address)
    restaurant, menu_items, total, currency = await _validate_and_price(
        session, payload
    )

    order = Order(
        customer_id=customer.id,
        restaurant_id=restaurant.id,
        delivery_address=delivery_address,
        currency=currency,
        total_amount_minor=total,
        status="PENDING",
        version=1,
    )
    session.add(order)
    await session.flush()  # assign order.id inside the transaction

    price_by_id = {m.id: m for m in menu_items}
    for line in payload.items:
        menu_item = price_by_id[line.menu_item_id]
        session.add(
            OrderItem(
                order_id=order.id,
                menu_item_id=menu_item.id,
                item_name=menu_item.name,
                unit_price_minor=menu_item.price_minor,
                quantity=line.quantity,
                line_total_minor=menu_item.price_minor * line.quantity,
            )
        )

    session.add(
        OrderStatusHistory(
            order_id=order.id,
            from_status=None,
            to_status="PENDING",
            version=1,
            actor="api",
            note="checkout accepted",
        )
    )

    response_body = CheckoutAccepted(
        order_id=order.id,
        status=order.status,
        total_amount_minor=order.total_amount_minor,
        currency=order.currency,
        version=order.version,
    ).model_dump(mode="json")

    session.add(
        CheckoutIdempotency(
            customer_id=customer.id,
            idempotency_key=key,
            request_hash=request_hash,
            order_id=order.id,
            response_status=202,
            response_body=response_body,
        )
    )

    # Initial domain event. correlation_id = order id so the whole causal chain
    # (created -> paid -> confirmed -> driver assigned) shares one trace id.
    event = build_event(
        event_type=EVENT_ORDER_CREATED,
        order_id=order.id,
        order_version=order.version,
        data={
            "amount_minor": order.total_amount_minor,
            "currency": order.currency,
            "status": order.status,
        },
        correlation_id=order.id,
        causation_id=None,
    )
    session.add(
        OutboxEvent(
            event_id=event.event_id,
            event_type=event.event_type,
            order_id=event.order_id,
            order_version=event.order_version,
            exchange="quickbite.orders",
            routing_key=event.event_type,
            payload=event.to_dict(),
            correlation_id=event.correlation_id,
        )
    )

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        # A concurrent identical submission won the unique-index race; its
        # transaction committed and ours rolled back completely (no partial
        # order/outbox rows). Replay the winner's stored response.
        winner = await _load_idempotency_record(session, customer.id, key)
        if winner is None:
            raise
        if winner.request_hash != request_hash:
            raise AppError(
                409,
                "idempotency_key_conflict",
                "This Idempotency-Key was already used with a different request payload",
                {"idempotency_key": key},
            )
        logger.info(
            "checkout_concurrent_replay",
            extra={"order_id": str(winner.order_id), "customer_id": str(customer.id)},
        )
        return _accepted_from_record(winner), True

    logger.info(
        "order_accepted",
        extra={
            "order_id": str(order.id),
            "customer_id": str(customer.id),
            "restaurant_id": str(restaurant.id),
            "total_amount_minor": order.total_amount_minor,
            "currency": order.currency,
        },
    )
    return CheckoutAccepted.model_validate(response_body), False


# --------------------------------------------------------------------------- #
# Ownership-scoped reads
# --------------------------------------------------------------------------- #
async def _get_owned_order(
    session: AsyncSession,
    *,
    order_id: uuid.UUID,
    customer_id: uuid.UUID,
    is_admin: bool = False,
) -> Order:
    order = await session.get(Order, order_id)
    # 404 both for unknown ids and for other customers' orders so order ids
    # cannot be probed.
    if order is None or (order.customer_id != customer_id and not is_admin):
        raise AppError(404, "order_not_found", "Order does not exist")
    return order


async def list_customer_orders(
    session: AsyncSession,
    *,
    customer_id: uuid.UUID,
    pagination: PaginationParams,
    status: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    base = select(Order).where(Order.customer_id == customer_id)
    if status:
        base = base.where(Order.status == status)
    total = (
        await session.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()

    stmt = base.options().order_by(Order.created_at.desc())
    rows = (
        await session.execute(
            stmt.offset(pagination.offset).limit(pagination.page_size)
        )
    ).scalars().all()

    order_ids = [o.id for o in rows]
    counts: dict[uuid.UUID, int] = {}
    names: dict[uuid.UUID, str] = {}
    if order_ids:
        count_rows = await session.execute(
            select(OrderItem.order_id, func.count())
            .where(OrderItem.order_id.in_(order_ids))
            .group_by(OrderItem.order_id)
        )
        counts = {oid: int(c) for oid, c in count_rows.all()}
        name_rows = await session.execute(
            select(Restaurant.id, Restaurant.name).where(
                Restaurant.id.in_({o.restaurant_id for o in rows})
            )
        )
        names = dict(name_rows.all())

    items = []
    for order in rows:
        items.append(
            {
                "id": order.id,
                "restaurant_id": order.restaurant_id,
                "restaurant_name": names.get(order.restaurant_id),
                "status": order.status,
                "version": order.version,
                "currency": order.currency,
                "total_amount_minor": order.total_amount_minor,
                "failure_code": order.failure_code,
                "created_at": order.created_at,
                "updated_at": order.updated_at,
                "item_count": counts.get(order.id, 0),
            }
        )
    return items, int(total)


async def get_order_detail(
    session: AsyncSession, *, order_id: uuid.UUID, customer_id: uuid.UUID,
    is_admin: bool = False,
) -> dict[str, Any]:
    order = await _get_owned_order(
        session, order_id=order_id, customer_id=customer_id, is_admin=is_admin
    )
    item_rows = (
        await session.execute(select(OrderItem).where(OrderItem.order_id == order.id))
    ).scalars().all()
    restaurant = await session.get(Restaurant, order.restaurant_id)
    driver_name = driver_vehicle = None
    if order.driver_id is not None:
        driver = await session.get(Driver, order.driver_id)
        if driver is not None:
            driver_name, driver_vehicle = driver.name, driver.vehicle
    return {
        "id": order.id,
        "customer_id": order.customer_id,
        "restaurant_id": order.restaurant_id,
        "restaurant_name": restaurant.name if restaurant else None,
        "delivery_address": order.delivery_address,
        "currency": order.currency,
        "total_amount_minor": order.total_amount_minor,
        "status": order.status,
        "version": order.version,
        "failure_code": order.failure_code,
        "failure_message": order.failure_message,
        "driver_id": order.driver_id,
        "driver_name": driver_name,
        "driver_vehicle": driver_vehicle,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
        "items": [
            {
                "menu_item_id": i.menu_item_id,
                "item_name": i.item_name,
                "unit_price_minor": i.unit_price_minor,
                "quantity": i.quantity,
                "line_total_minor": i.line_total_minor,
            }
            for i in sorted(item_rows, key=lambda x: x.item_name)
        ],
    }


async def list_order_history(
    session: AsyncSession,
    *,
    order_id: uuid.UUID,
    customer_id: uuid.UUID,
    is_admin: bool = False,
    pagination: PaginationParams,
) -> tuple[list[dict[str, Any]], int]:
    order = await _get_owned_order(
        session, order_id=order_id, customer_id=customer_id, is_admin=is_admin
    )
    base = select(OrderStatusHistory).where(OrderStatusHistory.order_id == order.id)
    total = (
        await session.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()
    rows = (
        await session.execute(
            base.order_by(OrderStatusHistory.version)
            .offset(pagination.offset)
            .limit(pagination.page_size)
        )
    ).scalars().all()
    items = [
        {
            "id": h.id,
            "from_status": h.from_status,
            "to_status": h.to_status,
            "version": h.version,
            "actor": h.actor,
            "note": h.note,
            "created_at": h.created_at,
        }
        for h in rows
    ]
    return items, int(total)


async def list_order_notifications(
    session: AsyncSession,
    *,
    order_id: uuid.UUID,
    customer_id: uuid.UUID,
    is_admin: bool = False,
    pagination: PaginationParams,
) -> tuple[list[dict[str, Any]], int]:
    order = await _get_owned_order(
        session, order_id=order_id, customer_id=customer_id, is_admin=is_admin
    )
    notification_customer_id = order.customer_id if is_admin else customer_id
    base = select(Notification).where(
        Notification.order_id == order.id,
        Notification.customer_id == notification_customer_id,
    )
    total = (
        await session.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()
    rows = (
        await session.execute(
            base.order_by(Notification.created_at.desc())
            .offset(pagination.offset)
            .limit(pagination.page_size)
        )
    ).scalars().all()
    items = [
        {
            "id": n.id,
            "order_id": n.order_id,
            "event_type": n.event_type,
            "title": n.title,
            "body": n.body,
            "status": n.status,
            "created_at": n.created_at,
        }
        for n in rows
    ]
    return items, int(total)


async def list_customer_notifications(
    session: AsyncSession,
    *,
    customer_id: uuid.UUID,
    pagination: PaginationParams,
) -> tuple[list[dict[str, Any]], int]:
    base = select(Notification).where(Notification.customer_id == customer_id)
    total = (
        await session.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()
    rows = (
        await session.execute(
            base.order_by(Notification.created_at.desc())
            .offset(pagination.offset)
            .limit(pagination.page_size)
        )
    ).scalars().all()
    items = [
        {
            "id": n.id,
            "order_id": n.order_id,
            "event_type": n.event_type,
            "title": n.title,
            "body": n.body,
            "status": n.status,
            "created_at": n.created_at,
        }
        for n in rows
    ]
    return items, int(total)
