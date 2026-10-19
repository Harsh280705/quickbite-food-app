"""Health endpoints (mounted at the root, outside /api/v1)."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.schemas.common import LiveResponse, ReadyResponse
from app.services import health_service

router = APIRouter(tags=["health"])


@router.get("/health/live", response_model=LiveResponse, summary="Liveness probe")
async def live() -> LiveResponse:
    """Process liveness. Does NOT touch PostgreSQL or RabbitMQ."""
    payload = await health_service.live_payload()
    return LiveResponse(**payload)


@router.get(
    "/health/ready",
    response_model=ReadyResponse,
    summary="Readiness probe with bounded dependency checks",
)
async def ready() -> JSONResponse:
    """503 when the required database dependency is unavailable.

    RabbitMQ downtime alone reports ``degraded`` with HTTP 200 because
    checkout acceptance is decoupled from the broker by the transactional
    outbox.
    """
    payload, status_code = await health_service.ready_payload()
    return JSONResponse(status_code=status_code, content=payload)
