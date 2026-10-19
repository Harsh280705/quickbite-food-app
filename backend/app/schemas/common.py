"""Shared response/error schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str


class ErrorEnvelope(ErrorBody):
    """Top-level error shape returned by every failing endpoint."""


class HealthComponent(BaseModel):
    status: str
    latency_ms: float | None = None
    detail: str | None = None


class LiveResponse(BaseModel):
    status: str = "live"
    service: str
    time: str


class ReadyResponse(BaseModel):
    status: str
    service: str
    checks: dict[str, HealthComponent]
    time: str
