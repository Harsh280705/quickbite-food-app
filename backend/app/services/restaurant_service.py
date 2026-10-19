"""Restaurant and menu read services (paginated, server-authoritative prices)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.pagination import PaginationParams
from app.models import AdminAuditLog, MenuItem, Restaurant


async def list_restaurants(
    session: AsyncSession,
    pagination: PaginationParams,
    *,
    include_inactive: bool = False,
    search: str | None = None,
    cuisine: str | None = None,
) -> tuple[list[Restaurant], int]:
    base = select(Restaurant)
    if not include_inactive:
        base = base.where(
            Restaurant.is_active.is_(True),
            Restaurant.accepts_orders.is_(True),
        )
    if search:
        base = base.where(Restaurant.name.ilike(f"%{search}%"))
    if cuisine:
        base = base.where(Restaurant.cuisine == cuisine)
    total = (
        await session.execute(
            select(func.count()).select_from(base.subquery())
        )
    ).scalar_one()
    rows = await session.execute(
        base.order_by(Restaurant.name, Restaurant.id).offset(pagination.offset).limit(pagination.page_size)
    )
    return list(rows.scalars()), int(total)


async def get_restaurant(session: AsyncSession, restaurant_id) -> Restaurant:
    restaurant = await session.get(Restaurant, restaurant_id)
    if restaurant is None:
        raise AppError(404, "restaurant_not_found", "Restaurant does not exist")
    return restaurant


async def list_menu_items(
    session: AsyncSession,
    restaurant_id,
    pagination: PaginationParams,
    *,
    only_available: bool = False,
    search: str | None = None,
) -> tuple[list[MenuItem], int]:
    restaurant = await get_restaurant(session, restaurant_id)
    base = select(MenuItem).where(MenuItem.restaurant_id == restaurant.id)
    if only_available:
        base = base.where(
            MenuItem.is_available.is_(True),
            MenuItem.is_discontinued.is_(False),
        )
    if search:
        base = base.where(MenuItem.name.ilike(f"%{search}%"))
    total = (
        await session.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()
    rows = await session.execute(
        base.order_by(MenuItem.name, MenuItem.id).offset(pagination.offset).limit(pagination.page_size)
    )
    return list(rows.scalars()), int(total)


# ---------------------------------------------------------------------------
# Admin management helpers
# ---------------------------------------------------------------------------


async def list_restaurants_admin(
    session: AsyncSession,
    pagination: PaginationParams,
    *,
    search: str | None = None,
    cuisine: str | None = None,
    is_active: bool | None = None,
    accepts_orders: bool | None = None,
) -> tuple[list[Restaurant], int]:
    base = select(Restaurant)
    if search:
        base = base.where(Restaurant.name.ilike(f"%{search}%"))
    if cuisine:
        base = base.where(Restaurant.cuisine == cuisine)
    if is_active is not None:
        base = base.where(Restaurant.is_active.is_(is_active))
    if accepts_orders is not None:
        base = base.where(Restaurant.accepts_orders.is_(accepts_orders))
    total = (
        await session.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()
    rows = await session.execute(
        base.order_by(Restaurant.name).offset(pagination.offset).limit(pagination.page_size)
    )
    return list(rows.scalars()), int(total)


async def update_restaurant(
    session: AsyncSession,
    restaurant_id: uuid.UUID,
    payload: dict[str, Any],
    admin_user_id: uuid.UUID | None = None,
) -> Restaurant:
    restaurant = await get_restaurant(session, restaurant_id)
    fields = ("name", "description", "cuisine", "rating", "is_active", "accepts_orders", "image_url")
    previous: dict[str, Any] = {}
    new: dict[str, Any] = {}
    changed = False
    for field in fields:
        if field in payload and payload[field] is not None:
            value = payload[field]
            if field == "image_url" and value is not None and not str(value).startswith("/static/images/"):
                raise AppError(422, "invalid_image_url", "image_url must use the local static image path")
            if getattr(restaurant, field) != value:
                previous[field] = getattr(restaurant, field)
                new[field] = value
                setattr(restaurant, field, value)
                changed = True
    if changed:
        session.add(
            AdminAuditLog(
                admin_user_id=admin_user_id,
                entity_type="restaurant",
                entity_id=str(restaurant.id),
                action="update",
                previous_value=previous,
                new_value=new,
            )
        )
        await session.commit()
        await session.refresh(restaurant)
    return restaurant


async def list_menu_items_admin(
    session: AsyncSession,
    pagination: PaginationParams,
    *,
    search: str | None = None,
    restaurant_id: uuid.UUID | None = None,
    is_available: bool | None = None,
    is_discontinued: bool | None = None,
) -> tuple[list[MenuItem], int]:
    base = select(MenuItem)
    if restaurant_id is not None:
        base = base.where(MenuItem.restaurant_id == restaurant_id)
    if search:
        base = base.where(MenuItem.name.ilike(f"%{search}%"))
    if is_available is not None:
        base = base.where(MenuItem.is_available.is_(is_available))
    if is_discontinued is not None:
        base = base.where(MenuItem.is_discontinued.is_(is_discontinued))
    total = (
        await session.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()
    rows = await session.execute(
        base.order_by(MenuItem.name).offset(pagination.offset).limit(pagination.page_size)
    )
    return list(rows.scalars()), int(total)


async def get_menu_item(session: AsyncSession, menu_item_id: uuid.UUID) -> MenuItem:
    item = await session.get(MenuItem, menu_item_id)
    if item is None:
        raise AppError(404, "menu_item_not_found", "Menu item does not exist")
    return item


async def create_menu_item(
    session: AsyncSession,
    payload: dict[str, Any],
    admin_user_id: uuid.UUID | None = None,
) -> MenuItem:
    from app.models import Restaurant

    restaurant = await session.get(Restaurant, payload["restaurant_id"])
    if restaurant is None:
        raise AppError(404, "restaurant_not_found", "Restaurant does not exist")
    image_url = payload.get("image_url")
    if image_url is not None and not str(image_url).startswith("/static/images/"):
        raise AppError(422, "invalid_image_url", "image_url must use the local static image path")
    if payload["price_minor"] <= 0:
        raise AppError(422, "invalid_price", "Price must be positive")
    item = MenuItem(
        restaurant_id=payload["restaurant_id"],
        name=payload["name"],
        description=payload.get("description", ""),
        price_minor=payload["price_minor"],
        currency=payload.get("currency", "INR"),
        is_available=payload.get("is_available", True),
        is_discontinued=payload.get("is_discontinued", False),
        image_url=image_url,
    )
    session.add(item)
    await session.flush()
    session.add(
        AdminAuditLog(
            admin_user_id=admin_user_id,
            entity_type="menu_item",
            entity_id=str(item.id),
            action="create",
            previous_value=None,
            new_value={
                "name": item.name,
                "price_minor": item.price_minor,
                "is_available": item.is_available,
                "is_discontinued": item.is_discontinued,
            },
        )
    )
    await session.commit()
    await session.refresh(item)
    return item


async def update_menu_item(
    session: AsyncSession,
    menu_item_id: uuid.UUID,
    payload: dict[str, Any],
    admin_user_id: uuid.UUID | None = None,
) -> MenuItem:
    item = await get_menu_item(session, menu_item_id)
    fields = ("name", "description", "price_minor", "currency", "is_available", "is_discontinued", "image_url", "restaurant_id")
    previous: dict[str, Any] = {}
    new: dict[str, Any] = {}
    changed = False
    for field in fields:
        if field in payload and payload[field] is not None:
            value = payload[field]
            if field == "price_minor" and (not isinstance(value, int) or value <= 0 or value > 10000000):
                raise AppError(422, "invalid_price", "Price must be a positive integer within limits")
            if field == "image_url" and value is not None and not str(value).startswith("/static/images/"):
                raise AppError(422, "invalid_image_url", "image_url must use the local static image path")
            if field == "restaurant_id":
                from app.models import Restaurant

                restaurant = await session.get(Restaurant, value)
                if restaurant is None:
                    raise AppError(404, "restaurant_not_found", "Restaurant does not exist")
            if getattr(item, field) != value:
                previous[field] = getattr(item, field)
                new[field] = value
                setattr(item, field, value)
                changed = True
    if changed:
        session.add(
            AdminAuditLog(
                admin_user_id=admin_user_id,
                entity_type="menu_item",
                entity_id=str(item.id),
                action="update",
                previous_value=previous,
                new_value=new,
            )
        )
        await session.commit()
        await session.refresh(item)
    return item
