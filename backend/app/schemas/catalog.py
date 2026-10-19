"""Restaurant and menu schemas."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class RestaurantOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    cuisine: str
    rating: int
    is_active: bool
    accepts_orders: bool = True
    image_url: str | None = None

    model_config = {"from_attributes": True}


class MenuItemOut(BaseModel):
    id: uuid.UUID
    restaurant_id: uuid.UUID
    name: str
    description: str
    price_minor: int
    currency: str
    is_available: bool
    is_discontinued: bool = False
    image_url: str | None = None

    model_config = {"from_attributes": True}


class RestaurantUpdateIn(BaseModel):
    name: str | None = None
    description: str | None = None
    cuisine: str | None = None
    rating: int | None = Field(default=None, ge=0, le=500)
    is_active: bool | None = None
    accepts_orders: bool | None = None
    image_url: str | None = None


class MenuItemCreateIn(BaseModel):
    restaurant_id: uuid.UUID
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)
    price_minor: int = Field(gt=0, le=10000000)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    is_available: bool = True
    is_discontinued: bool = False
    image_url: str | None = None


class MenuItemUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    price_minor: int | None = Field(default=None, gt=0, le=10000000)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    is_available: bool | None = None
    is_discontinued: bool | None = None
    image_url: str | None = None
