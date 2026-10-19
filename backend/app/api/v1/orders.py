"""Customer order endpoints (ownership enforced at the backend)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.v1.deps import CurrentUser, DbSession, IdempotencyKey, Pagination
from app.core.pagination import Page, make_page
from app.schemas.orders import (
    CheckoutAccepted,
    HistoryEntryOut,
    NotificationOut,
    OrderCreate,
    OrderOut,
    OrderSummaryOut,
)
from app.services import order_service

router = APIRouter(tags=["orders"])


@router.post(
    "/orders",
    response_model=CheckoutAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Idempotent checkout (requires Idempotency-Key header)",
)
async def create_order(
    payload: OrderCreate,
    session: DbSession,
    user: CurrentUser,
    idempotency_key: IdempotencyKey,
    response: Response,
) -> CheckoutAccepted:
    accepted, _replayed = await order_service.create_order(
        session, customer=user, payload=payload, idempotency_key=idempotency_key
    )
    response.headers["Location"] = f"/api/v1/orders/{accepted.order_id}"
    response.headers["Idempotency-Replayed"] = "true" if _replayed else "false"
    return accepted


@router.get("/orders", response_model=Page[OrderSummaryOut])
async def list_orders(
    session: DbSession,
    user: CurrentUser,
    pagination: Pagination,
    status_filter: Annotated[
        str | None, Query(alias="status", description="Filter by order status")
    ] = None,
) -> Page[OrderSummaryOut]:
    items, total = await order_service.list_customer_orders(
        session,
        customer_id=user.id,
        pagination=pagination,  # type: ignore[arg-type]
        status=status_filter,
    )
    return Page[OrderSummaryOut](
        items=[OrderSummaryOut(**i) for i in items],
        page=pagination.page,  # type: ignore[union-attr]
        page_size=pagination.page_size,  # type: ignore[union-attr]
        total=total,
    )


@router.get("/orders/{order_id}", response_model=OrderOut)
async def get_order(
    order_id: uuid.UUID, session: DbSession, user: CurrentUser
) -> OrderOut:
    detail = await order_service.get_order_detail(
        session, order_id=order_id, customer_id=user.id,
        is_admin=user.role == "admin",
    )
    return OrderOut(**detail)


@router.get("/orders/{order_id}/history", response_model=Page[HistoryEntryOut])
async def get_order_history(
    order_id: uuid.UUID,
    session: DbSession,
    user: CurrentUser,
    pagination: Pagination,
) -> Page[HistoryEntryOut]:
    items, total = await order_service.list_order_history(
        session,
        order_id=order_id,
        customer_id=user.id,
        is_admin=user.role == "admin",
        pagination=pagination,  # type: ignore[arg-type]
    )
    return Page[HistoryEntryOut](
        items=[HistoryEntryOut(**i) for i in items],
        page=pagination.page,  # type: ignore[union-attr]
        page_size=pagination.page_size,  # type: ignore[union-attr]
        total=total,
    )


@router.get(
    "/orders/{order_id}/notifications", response_model=Page[NotificationOut]
)
async def get_order_notifications(
    order_id: uuid.UUID,
    session: DbSession,
    user: CurrentUser,
    pagination: Pagination,
) -> Page[NotificationOut]:
    items, total = await order_service.list_order_notifications(
        session,
        order_id=order_id,
        customer_id=user.id,
        is_admin=user.role == "admin",
        pagination=pagination,  # type: ignore[arg-type]
    )
    return Page[NotificationOut](
        items=[NotificationOut(**i) for i in items],
        page=pagination.page,  # type: ignore[union-attr]
        page_size=pagination.page_size,  # type: ignore[union-attr]
        total=total,
    )


@router.get("/notifications", response_model=Page[NotificationOut])
async def list_my_notifications(
    session: DbSession,
    user: CurrentUser,
    pagination: Pagination,
) -> Page[NotificationOut]:
    """Customer-wide notification feed (all orders)."""
    items, total = await order_service.list_customer_notifications(
        session, customer_id=user.id, pagination=pagination  # type: ignore[arg-type]
    )
    return Page[NotificationOut](
        items=[NotificationOut(**i) for i in items],
        page=pagination.page,  # type: ignore[union-attr]
        page_size=pagination.page_size,  # type: ignore[union-attr]
        total=total,
    )
