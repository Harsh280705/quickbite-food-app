"""Order state machine: the single authority for status transitions.

Baseline transitions (assignment v2.0):

    PENDING       -> PAID | PAYMENT_FAILED
    PAID          -> CONFIRMED | FAILED
    CONFIRMED     -> DRIVER_ASSIGNED | FAILED

``DRIVER_ASSIGNED``, ``PAYMENT_FAILED`` and ``FAILED`` are terminal.
Backward transitions and silent version regressions are impossible because
every accepted transition bumps ``orders.version`` by exactly one and appends
an immutable history row with the same version (unique per order).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ORDER_STATUSES, TERMINAL_STATUSES, Order, OrderStatusHistory
from app.models.entities import utcnow

if TYPE_CHECKING:  # pragma: no cover
    from uuid import UUID

logger = logging.getLogger("quickbite.state_machine")

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "PENDING": frozenset({"PAID", "PAYMENT_FAILED"}),
    "PAID": frozenset({"CONFIRMED", "FAILED"}),
    "CONFIRMED": frozenset({"DRIVER_ASSIGNED", "FAILED"}),
    "DRIVER_ASSIGNED": frozenset(),
    "PAYMENT_FAILED": frozenset(),
    "FAILED": frozenset(),
}

# status -> first event version (order.version of that status row)
BASE_VERSION = 1


class InvalidTransition(Exception):
    """Raised when a requested transition is not allowed from the current state."""

    def __init__(self, current: str, target: str) -> None:
        super().__init__(f"transition {current} -> {target} is not allowed")
        self.current = current
        self.target = target


def is_terminal(status: str) -> bool:
    return status in TERMINAL_STATUSES


def can_transition(current: str, target: str) -> bool:
    if current not in ALLOWED_TRANSITIONS:
        raise ValueError(f"unknown current status: {current}")
    if target not in ORDER_STATUSES:
        raise ValueError(f"unknown target status: {target}")
    return target in ALLOWED_TRANSITIONS[current]


def assert_transition(current: str, target: str) -> None:
    if not can_transition(current, target):
        raise InvalidTransition(current, target)


async def get_order_for_update(
    session: AsyncSession, order_id: "UUID | str"
) -> Order | None:
    """Load an order with a row lock so concurrent workers serialize here."""
    stmt = select(Order).where(Order.id == order_id).with_for_update()
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def apply_transition(
    session: AsyncSession,
    order: Order,
    target: str,
    *,
    actor: str,
    note: str = "",
    failure_code: str | None = None,
    failure_message: str | None = None,
    driver_id: "UUID | None" = None,
) -> int:
    """Validate and apply a transition atomically with its history row.

    The caller owns the transaction: commit happens outside this function so
    side effects (payments, assignments, outbox rows) commit together.
    Returns the new order version.
    """
    current = order.status
    if current == target:
        # Idempotent no-op only for exact re-application; callers should avoid
        # this path by checking processed events first.
        raise InvalidTransition(current, target)
    assert_transition(current, target)

    new_version = order.version + 1
    order.status = target
    order.version = new_version
    order.updated_at = utcnow()
    if failure_code is not None:
        order.failure_code = failure_code
    if failure_message is not None:
        order.failure_message = failure_message
    if driver_id is not None:
        order.driver_id = driver_id

    session.add(
        OrderStatusHistory(
            order_id=order.id,
            from_status=current,
            to_status=target,
            version=new_version,
            actor=actor,
            note=note[:255],
        )
    )
    logger.info(
        "order_transition",
        extra={
            "order_id": str(order.id),
            "from_status": current,
            "to_status": target,
            "order_version": new_version,
            "actor": actor,
        },
    )
    return new_version
