"""Order, history, notification and admin schemas.

Money is always integer minor units: INR 12.50 -> ``1250`` with
``currency = "INR"``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class OrderItemIn(BaseModel):
    menu_item_id: uuid.UUID
    quantity: int = Field(ge=1, le=20)


class OrderCreate(BaseModel):
    restaurant_id: uuid.UUID
    delivery_address: str = Field(min_length=1, max_length=300)
    items: list[OrderItemIn] = Field(min_length=1, max_length=20)


class CheckoutAccepted(BaseModel):
    """202 Accepted body; identical bytes are replayed for idempotent retries."""

    order_id: uuid.UUID
    status: str
    total_amount_minor: int
    currency: str
    version: int
    detail: str = "Order accepted for asynchronous processing."


class OrderItemOut(BaseModel):
    menu_item_id: uuid.UUID
    item_name: str
    unit_price_minor: int
    quantity: int
    line_total_minor: int

    model_config = {"from_attributes": True}


class OrderOut(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    restaurant_id: uuid.UUID
    restaurant_name: str | None = None
    delivery_address: str
    currency: str
    total_amount_minor: int
    status: str
    version: int
    failure_code: str | None = None
    failure_message: str | None = None
    driver_id: uuid.UUID | None = None
    driver_name: str | None = None
    driver_vehicle: str | None = None
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemOut] = Field(default_factory=list)


class OrderSummaryOut(BaseModel):
    """Compact projection used by list endpoints."""

    id: uuid.UUID
    restaurant_id: uuid.UUID
    restaurant_name: str | None = None
    status: str
    version: int
    currency: str
    total_amount_minor: int
    failure_code: str | None = None
    created_at: datetime
    updated_at: datetime
    item_count: int = 0

    model_config = {"from_attributes": True}


class HistoryEntryOut(BaseModel):
    id: uuid.UUID
    from_status: str | None
    to_status: str
    version: int
    actor: str
    note: str
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationOut(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID | None
    event_type: str
    title: str
    body: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminOrderOut(OrderSummaryOut):
    customer_email: str | None = None
    failure_message: str | None = None


class AdminAuditLogOut(BaseModel):
    id: uuid.UUID
    admin_user_id: uuid.UUID | None = None
    entity_type: str
    entity_id: str
    action: str
    previous_value: dict[str, Any] | None = None
    new_value: dict[str, Any] | None = None
    created_at: datetime


class StatusCount(BaseModel):
    status: str
    count: int


class AnalyticsActivityPoint(BaseModel):
    date: str
    count: int


class AdminAnalyticsOut(BaseModel):
    total_orders: int
    total_customers: int
    total_restaurants: int
    total_menu_items: int
    available_menu_items: int = 0
    out_of_stock_menu_items: int = 0
    discontinued_menu_items: int = 0
    today_orders: int = 0
    status_counts: list[StatusCount]
    awaiting_processing: int
    paid_orders: int
    confirmed_orders: int
    driver_assigned_orders: int
    failed_orders: int
    payment_failed_orders: int
    quarantine_count: int
    retry_backlog: int
    pending_outbox: int
    processed_events: int
    activity: list[AnalyticsActivityPoint]
    generated_at: datetime


class AdminSummaryOut(BaseModel):
    total_orders: int
    status_counts: list[StatusCount]
    pending_outbox: int
    sent_outbox_recent: int
    retry_backlog: int
    quarantine_count: int
    processed_events: int
    generated_at: datetime


class ReplayResult(BaseModel):
    """Optional admin quarantine inspection support."""

    quarantine_id: uuid.UUID
    consumer_name: str
    event_id: uuid.UUID | None
    failure_code: str
    quarantined_at: datetime
    original_event: dict[str, Any]
