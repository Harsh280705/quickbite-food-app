"""Administrator endpoints (role protected by the backend)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.v1.deps import AdminUser, DbSession, Pagination
from app.core.pagination import Page
from app.models import ORDER_STATUSES
from app.schemas.catalog import (
    MenuItemCreateIn,
    MenuItemOut,
    MenuItemUpdateIn,
    RestaurantOut,
    RestaurantUpdateIn,
)
from app.schemas.orders import (
    AdminAnalyticsOut,
    AdminAuditLogOut,
    AdminOrderOut,
    AdminSummaryOut,
)
from app.services import admin_service, restaurant_service

router = APIRouter(tags=["admin"])


@router.get("/admin/orders", response_model=Page[AdminOrderOut])
async def admin_list_orders(
    session: DbSession,
    admin: AdminUser,
    pagination: Pagination,
    status_filter: Annotated[
        str | None,
        Query(
            alias="status",
            description="Filter by status: " + ", ".join(ORDER_STATUSES),
        ),
    ] = None,
    customer_email: Annotated[str | None, Query(description="Filter by customer email")] = None,
) -> Page[AdminOrderOut]:
    if status_filter is not None and status_filter not in ORDER_STATUSES:
        from app.core.errors import AppError

        raise AppError(
            422,
            "validation_error",
            f"Unknown status '{status_filter}'",
            {"allowed": list(ORDER_STATUSES)},
        )
    items, total = await admin_service.list_all_orders(
        session,
        pagination,  # type: ignore[arg-type]
        status=status_filter,
        customer_email=customer_email,
    )
    return Page[AdminOrderOut](
        items=[AdminOrderOut(**i) for i in items],
        page=pagination.page,  # type: ignore[union-attr]
        page_size=pagination.page_size,  # type: ignore[union-attr]
        total=total,
    )


@router.get(
    "/admin/summary",
    response_model=AdminSummaryOut,
    summary="Aggregate status counts plus outbox/retry/quarantine backlog",
)
async def admin_summary_endpoint(
    session: DbSession, admin: AdminUser
) -> AdminSummaryOut:
    summary = await admin_service.admin_summary(session)
    return AdminSummaryOut(**summary)


@router.get(
    "/admin/analytics",
    response_model=AdminAnalyticsOut,
    summary="Administrator analytics from persisted records",
)
async def admin_analytics_endpoint(
    session: DbSession,
    admin: AdminUser,
    days: int = Query(30, ge=1, le=90),
) -> AdminAnalyticsOut:
    analytics = await admin_service.admin_analytics(session, days=days)
    return AdminAnalyticsOut(**analytics)


@router.get("/admin/restaurants", response_model=Page[RestaurantOut])
async def admin_list_restaurants(
    session: DbSession,
    admin: AdminUser,
    pagination: Pagination,
    search: Annotated[str | None, Query()] = None,
    cuisine: Annotated[str | None, Query()] = None,
    is_active: Annotated[bool | None, Query()] = None,
    accepts_orders: Annotated[bool | None, Query()] = None,
) -> Page[RestaurantOut]:
    items, total = await restaurant_service.list_restaurants_admin(
        session,
        pagination,
        search=search,
        cuisine=cuisine,
        is_active=is_active,
        accepts_orders=accepts_orders,
    )
    return Page[RestaurantOut](
        items=[RestaurantOut.model_validate(r) for r in items],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total,
    )


@router.patch("/admin/restaurants/{restaurant_id}", response_model=RestaurantOut)
async def admin_update_restaurant(
    restaurant_id: uuid.UUID,
    payload: RestaurantUpdateIn,
    session: DbSession,
    admin: AdminUser,
) -> RestaurantOut:
    restaurant = await restaurant_service.update_restaurant(
        session,
        restaurant_id,
        payload.model_dump(exclude_unset=True),
        admin_user_id=admin.id,
    )
    return RestaurantOut.model_validate(restaurant)


@router.get("/admin/menu-items", response_model=Page[MenuItemOut])
async def admin_list_menu_items(
    session: DbSession,
    admin: AdminUser,
    pagination: Pagination,
    search: Annotated[str | None, Query()] = None,
    restaurant_id: Annotated[uuid.UUID | None, Query()] = None,
    is_available: Annotated[bool | None, Query()] = None,
    is_discontinued: Annotated[bool | None, Query()] = None,
) -> Page[MenuItemOut]:
    items, total = await restaurant_service.list_menu_items_admin(
        session,
        pagination,
        search=search,
        restaurant_id=restaurant_id,
        is_available=is_available,
        is_discontinued=is_discontinued,
    )
    return Page[MenuItemOut](
        items=[MenuItemOut.model_validate(m) for m in items],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total,
    )


@router.post("/admin/menu-items", response_model=MenuItemOut, status_code=201)
async def admin_create_menu_item(
    payload: MenuItemCreateIn,
    session: DbSession,
    admin: AdminUser,
) -> MenuItemOut:
    item = await restaurant_service.create_menu_item(
        session,
        payload.model_dump(),
        admin_user_id=admin.id,
    )
    return MenuItemOut.model_validate(item)


@router.patch("/admin/menu-items/{menu_item_id}", response_model=MenuItemOut)
async def admin_update_menu_item(
    menu_item_id: uuid.UUID,
    payload: MenuItemUpdateIn,
    session: DbSession,
    admin: AdminUser,
) -> MenuItemOut:
    item = await restaurant_service.update_menu_item(
        session,
        menu_item_id,
        payload.model_dump(exclude_unset=True),
        admin_user_id=admin.id,
    )
    return MenuItemOut.model_validate(item)


@router.get("/admin/audit-logs", response_model=Page[AdminAuditLogOut])
async def admin_list_audit_logs(
    session: DbSession,
    admin: AdminUser,
    pagination: Pagination,
    entity_type: Annotated[str | None, Query()] = None,
    action: Annotated[str | None, Query()] = None,
) -> Page[AdminAuditLogOut]:
    items, total = await admin_service.list_audit_logs(
        session, pagination, entity_type=entity_type, action=action
    )
    return Page[AdminAuditLogOut](
        items=[AdminAuditLogOut(**i) for i in items],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total,
    )
