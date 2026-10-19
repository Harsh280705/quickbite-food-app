"""Shared FastAPI dependencies: DB session, authentication, pagination."""

from __future__ import annotations

from typing import Annotated, AsyncIterator

from fastapi import Depends, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.core.pagination import PaginationParams
from app.db.session import get_session
from app.models import User
from app.services import auth_service

bearer_scheme = HTTPBearer(auto_error=False, scheme_name="BearerAuth")

DbSession = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(
    session: DbSession,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
) -> User:
    if credentials is None or not credentials.credentials:
        raise AppError(401, "unauthorized", "Authentication required. Provide 'Authorization: Bearer <token>'.")
    if credentials.scheme.lower() != "bearer":
        raise AppError(401, "unauthorized", "Unsupported authorization scheme")
    return await auth_service.decode_and_load_user(session, credentials.credentials)


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_admin(user: CurrentUser) -> User:
    if user.role != "admin":
        raise AppError(403, "forbidden", "Administrator role is required for this endpoint")
    return user


AdminUser = Annotated[User, Depends(require_admin)]


def require_idempotency_key(request: Request) -> str:
    key = request.headers.get("Idempotency-Key")
    if not key:
        raise AppError(400, "missing_idempotency_key", "The 'Idempotency-Key' header is required for POST /api/v1/orders")
    return key


IdempotencyKey = Annotated[str, Depends(require_idempotency_key)]


def pagination_dep(
    page: Annotated[int, Query(ge=1, description="Page number (1-based)")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = settings.default_page_size,
) -> PaginationParams:
    if page_size > settings.max_page_size:
        raise AppError(422, "validation_error", f"page_size must be between 1 and {settings.max_page_size}")
    return PaginationParams(page=page, page_size=page_size)


Pagination = Annotated[PaginationParams, Depends(pagination_dep)]
