"""FastAPI application factory."""

from __future__ import annotations

import logging
import sys
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

import fastapi
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.health import router as health_router
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import (
    configure_logging,
    set_correlation_id,
    set_request_id,
)
from app.db.session import dispose_engine

logger = logging.getLogger("quickbite.api")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assigns/propagates request ids and correlation ids on every request."""

    async def dispatch(self, request: Request, call_next):
        incoming_rid = request.headers.get("X-Request-ID")
        request_id = incoming_rid or uuid.uuid4().hex
        incoming_cid = request.headers.get("X-Correlation-ID")
        correlation_id = incoming_cid or request_id
        set_request_id(request_id)
        set_correlation_id(correlation_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Correlation-ID"] = correlation_id
        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings.validate_for_runtime()
    configure_logging(settings.log_level)
    logger.info(
        "api_starting",
        extra={
            "environment": settings.environment,
            "database": settings.database_url.rsplit("@", 1)[-1],
            "executable": sys.executable,
            "prefix": sys.prefix,
            "fastapi_version": fastapi.__version__,
            "demo_payment_mode": settings.demo_payment_mode,
            "demo_crash_mode": settings.demo_crash_mode,
        },
    )
    yield
    await dispose_engine()
    logger.info("api_stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="QuickBite API",
        version="2.0.0",
        description=(
            "QuickBite food delivery order processing API.\n\n"
            "* Money is integer minor units (INR 12.50 -> `1250`).\n"
            "* All list endpoints paginate with `page`/`page_size` "
            "(max 100) and return `{items, page, page_size, total}`.\n"
            "* `POST /api/v1/orders` requires an `Idempotency-Key` header.\n"
            "* Errors use `{code, message, details, request_id}`."
        ),
        lifespan=lifespan,
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        docs_url=f"{settings.api_v1_prefix}/docs",
        redoc_url=f"{settings.api_v1_prefix}/redoc",
    )

    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Idempotency-Key",
            "X-Request-ID",
            "X-Correlation-ID",
        ],
        # Flutter Web must be able to read the checkout Location header.
        expose_headers=["Location", "X-Request-ID", "X-Correlation-ID", "Idempotency-Replayed"],
    )

    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    static_dir = Path(__file__).resolve().parents[1] / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir), check_dir=False), name="static")

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {
            "service": settings.project_name,
            "docs": f"{settings.api_v1_prefix}/docs",
            "health": "/health/ready",
        }

    return app


app = create_app()
