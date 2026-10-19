"""Administrator read services (cross-customer, read-only)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PaginationParams
from app.models import (
    ORDER_STATUSES,
    AdminAuditLog,
    MenuItem,
    Order,
    OrderItem,
    ProcessedEvent,
    Restaurant,
    User,
)
from app.models.messaging import OutboxEvent, QuarantineRecord, RetryJob


async def list_all_orders(
    session: AsyncSession,
    pagination: PaginationParams,
    *,
    status: str | None = None,
    customer_email: str | None = None,
) -> tuple[list[dict], int]:
    base = select(Order)
    if status:
        base = base.where(Order.status == status)
    if customer_email:
        base = base.join(User, User.id == Order.customer_id).where(
            User.email == customer_email.lower()
        )

    total = (
        await session.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()

    stmt = base.order_by(Order.created_at.desc())
    rows = (
        await session.execute(
            stmt.offset(pagination.offset).limit(pagination.page_size)
        )
    ).scalars().all()

    order_ids = [o.id for o in rows]
    item_counts: dict = {}
    restaurant_names: dict = {}
    customer_emails: dict = {}
    if order_ids:
        count_rows = await session.execute(
            select(OrderItem.order_id, func.count())
            .where(OrderItem.order_id.in_(order_ids))
            .group_by(OrderItem.order_id)
        )
        item_counts = {oid: int(c) for oid, c in count_rows.all()}
        rest_rows = await session.execute(
            select(Restaurant.id, Restaurant.name).where(
                Restaurant.id.in_({o.restaurant_id for o in rows})
            )
        )
        restaurant_names = dict(rest_rows.all())
        user_rows = await session.execute(
            select(User.id, User.email).where(User.id.in_({o.customer_id for o in rows}))
        )
        customer_emails = dict(user_rows.all())

    items = []
    for order in rows:
        items.append(
            {
                "id": order.id,
                "customer_id": order.customer_id,
                "customer_email": customer_emails.get(order.customer_id),
                "restaurant_id": order.restaurant_id,
                "restaurant_name": restaurant_names.get(order.restaurant_id),
                "status": order.status,
                "version": order.version,
                "currency": order.currency,
                "total_amount_minor": order.total_amount_minor,
                "failure_code": order.failure_code,
                "failure_message": order.failure_message,
                "created_at": order.created_at,
                "updated_at": order.updated_at,
                "item_count": item_counts.get(order.id, 0),
            }
        )
    return items, int(total)


async def admin_summary(session: AsyncSession) -> dict:
    status_rows = await session.execute(
        select(Order.status, func.count()).group_by(Order.status)
    )
    counts = {status: int(count) for status, count in status_rows.all()}
    status_counts = [{"status": s, "count": counts.get(s, 0)} for s in ORDER_STATUSES]
    total_orders = sum(counts.values())

    pending_outbox = (
        await session.execute(
            select(func.count())
            .select_from(OutboxEvent)
            .where(OutboxEvent.status.in_(("PENDING", "SENDING")))
        )
    ).scalar_one()
    sent_recent = (
        await session.execute(
            select(func.count())
            .select_from(OutboxEvent)
            .where(OutboxEvent.status == "SENT")
        )
    ).scalar_one()
    retry_backlog = (
        await session.execute(
            select(func.count())
            .select_from(RetryJob)
            .where(RetryJob.status == "PENDING")
        )
    ).scalar_one()
    quarantine_count = (
        await session.execute(select(func.count()).select_from(QuarantineRecord))
    ).scalar_one()
    processed_count = (
        await session.execute(select(func.count()).select_from(ProcessedEvent))
    ).scalar_one()

    return {
        "total_orders": int(total_orders),
        "status_counts": status_counts,
        "pending_outbox": int(pending_outbox),
        "sent_outbox_recent": int(sent_recent),
        "retry_backlog": int(retry_backlog),
        "quarantine_count": int(quarantine_count),
        "processed_events": int(processed_count),
        "generated_at": datetime.now(timezone.utc),
    }


async def admin_analytics(session: AsyncSession, *, days: int = 30) -> dict:
    days = max(1, min(days, 90))
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    total_orders = (
        await session.execute(select(func.count()).select_from(Order))
    ).scalar_one()
    total_customers = (
        await session.execute(
            select(func.count()).select_from(User).where(User.role == "customer")
        )
    ).scalar_one()
    total_restaurants = (
        await session.execute(select(func.count()).select_from(Restaurant))
    ).scalar_one()
    total_menu_items = (
        await session.execute(select(func.count()).select_from(MenuItem))
    ).scalar_one()
    available_menu_items = (
        await session.execute(
            select(func.count()).select_from(MenuItem).where(
                MenuItem.is_available.is_(True),
                MenuItem.is_discontinued.is_(False),
            )
        )
    ).scalar_one()
    out_of_stock_menu_items = (
        await session.execute(
            select(func.count()).select_from(MenuItem).where(
                MenuItem.is_available.is_(False),
                MenuItem.is_discontinued.is_(False),
            )
        )
    ).scalar_one()
    discontinued_menu_items = (
        await session.execute(
            select(func.count()).select_from(MenuItem).where(MenuItem.is_discontinued.is_(True))
        )
    ).scalar_one()
    today_cutoff = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_orders = (
        await session.execute(
            select(func.count()).select_from(Order).where(Order.created_at >= today_cutoff)
        )
    ).scalar_one()

    status_rows = await session.execute(
        select(Order.status, func.count()).group_by(Order.status)
    )
    counts = {status: int(count) for status, count in status_rows.all()}
    status_counts = [{"status": s, "count": counts.get(s, 0)} for s in ORDER_STATUSES]

    activity_rows = await session.execute(
        select(func.date(Order.created_at).label("day"), func.count())
        .where(Order.created_at >= cutoff)
        .group_by("day")
        .order_by("day")
    )
    activity = [{"date": str(day), "count": int(count)} for day, count in activity_rows.all()]

    pending_outbox = (
        await session.execute(
            select(func.count())
            .select_from(OutboxEvent)
            .where(OutboxEvent.status.in_(("PENDING", "SENDING")))
        )
    ).scalar_one()
    retry_backlog = (
        await session.execute(
            select(func.count())
            .select_from(RetryJob)
            .where(RetryJob.status == "PENDING")
        )
    ).scalar_one()
    quarantine_count = (
        await session.execute(select(func.count()).select_from(QuarantineRecord))
    ).scalar_one()
    processed_count = (
        await session.execute(select(func.count()).select_from(ProcessedEvent))
    ).scalar_one()

    return {
        "total_orders": int(total_orders),
        "total_customers": int(total_customers),
        "total_restaurants": int(total_restaurants),
        "total_menu_items": int(total_menu_items),
        "available_menu_items": int(available_menu_items),
        "out_of_stock_menu_items": int(out_of_stock_menu_items),
        "discontinued_menu_items": int(discontinued_menu_items),
        "today_orders": int(today_orders),
        "status_counts": status_counts,
        "awaiting_processing": int(counts.get("PENDING", 0)),
        "paid_orders": int(counts.get("PAID", 0)),
        "confirmed_orders": int(counts.get("CONFIRMED", 0)),
        "driver_assigned_orders": int(counts.get("DRIVER_ASSIGNED", 0)),
        "failed_orders": int(counts.get("FAILED", 0)),
        "payment_failed_orders": int(counts.get("PAYMENT_FAILED", 0)),
        "quarantine_count": int(quarantine_count),
        "retry_backlog": int(retry_backlog),
        "pending_outbox": int(pending_outbox),
        "processed_events": int(processed_count),
        "activity": activity,
        "generated_at": datetime.now(timezone.utc),
    }


async def list_audit_logs(
    session: AsyncSession,
    pagination: PaginationParams,
    *,
    entity_type: str | None = None,
    action: str | None = None,
) -> tuple[list[dict], int]:
    base = select(AdminAuditLog)
    if entity_type:
        base = base.where(AdminAuditLog.entity_type == entity_type)
    if action:
        base = base.where(AdminAuditLog.action == action)
    total = (
        await session.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()
    rows = (
        await session.execute(
            base.order_by(AdminAuditLog.created_at.desc())
            .offset(pagination.offset)
            .limit(pagination.page_size)
        )
    ).scalars().all()
    items = [
        {
            "id": r.id,
            "admin_user_id": r.admin_user_id,
            "entity_type": r.entity_type,
            "entity_id": r.entity_id,
            "action": r.action,
            "previous_value": r.previous_value,
            "new_value": r.new_value,
            "created_at": r.created_at,
        }
        for r in rows
    ]
    return items, int(total)
