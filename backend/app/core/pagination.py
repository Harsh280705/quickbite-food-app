"""Consistent pagination helpers for every list endpoint."""

from __future__ import annotations

from typing import Generic, Sequence, TypeVar

from fastapi import Query
from pydantic import BaseModel, Field

from app.core.config import settings

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Standard list envelope: items, page, page_size, total, has_more."""

    items: list[T]
    page: int
    page_size: int
    total: int = Field(ge=0)
    has_more: bool = False


class PaginationParams(BaseModel):
    page: int = 1
    page_size: int = settings.default_page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def pagination_params(
    page: int = Query(1, ge=1, description="1-based page number"),
    page_size: int = Query(
        settings.default_page_size,
        ge=1,
        le=settings.max_page_size,
        description=f"Items per page (max {settings.max_page_size})",
    ),
) -> PaginationParams:
    return PaginationParams(page=page, page_size=page_size)


def make_page(items: Sequence[T], pagination: PaginationParams, total: int) -> dict:
    return {
        "items": list(items),
        "page": pagination.page,
        "page_size": pagination.page_size,
        "total": total,
        "has_more": pagination.offset + len(items) < total,
    }
