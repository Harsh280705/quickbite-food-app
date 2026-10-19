"""Restaurant catalog endpoints (public, paginated)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.v1.deps import CurrentUser, DbSession, Pagination
from app.core.pagination import Page
from app.schemas.catalog import MenuItemOut, RestaurantOut
from app.services import restaurant_service

router = APIRouter(tags=["restaurants"])


@router.get("/restaurants", response_model=Page[RestaurantOut])
async def list_restaurants(
    session: DbSession,
    user: CurrentUser,
    pagination: Pagination,
    include_inactive: bool = Query(
        False, description="Admin/debug only; defaults to active restaurants"
    ),
    search: Annotated[str | None, Query(description="Search restaurant name")] = None,
    cuisine: Annotated[str | None, Query(description="Filter by cuisine")] = None,
) -> Page[RestaurantOut]:
    restaurants, total = await restaurant_service.list_restaurants(
        session,
        pagination,
        include_inactive=include_inactive,
        search=search,
        cuisine=cuisine,
    )
    return Page[RestaurantOut](
        items=[RestaurantOut.model_validate(r) for r in restaurants],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total,
    )


@router.get(
    "/restaurants/{restaurant_id}/menu",
    response_model=Page[MenuItemOut],
)
async def list_menu(
    restaurant_id: uuid.UUID,
    session: DbSession,
    user: CurrentUser,
    pagination: Pagination,
    only_available: bool = Query(True, description="Hide out-of-stock items"),
    search: Annotated[str | None, Query(description="Search menu item name")] = None,
) -> Page[MenuItemOut]:
    items, total = await restaurant_service.list_menu_items(
        session,
        restaurant_id,
        pagination,
        only_available=only_available,
        search=search,
    )
    return Page[MenuItemOut](
        items=[MenuItemOut.model_validate(m) for m in items],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total,
    )
