"""Read-only database state diagnostic (no writes, no secrets printed).

Usage (from backend/):  python -m scripts.db_status
Prints migration revision and per-table row counts so an interrupted run can
be diagnosed without touching data.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import text

TABLES = [
    "alembic_version",
    "users",
    "restaurants",
    "menu_items",
    "drivers",
    "orders",
    "order_items",
    "order_status_history",
    "simulated_payments",
    "driver_assignments",
    "notifications",
    "processed_events",
    "outbox_events",
    "retry_jobs",
    "quarantine_records",
    "checkout_idempotency_records",
]


async def main() -> None:
    from app.db.session import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        info = (
            await session.execute(
                text("select current_database(), current_user, now()")
            )
        ).one()
        print(f"database={info[0]} user={info[1]} server_time={info[2]}")

        version_cols = (
            await session.execute(
                text(
                    "select column_name from information_schema.columns "
                    "where table_name = 'alembic_version' order by ordinal_position"
                )
            )
        ).scalars().all()
        print(f"alembic_version columns: {list(version_cols)}")

        for column in version_cols:
            rows = (
                await session.execute(
                    text(f"select {column} from alembic_version")  # noqa: S608
                )
            ).scalars().all()
            print(f"alembic revision: {rows}")

        for table in TABLES[1:]:
            exists = (
                await session.execute(
                    text(
                        "select to_regclass(:t) is not null"
                    ),
                    {"t": table},
                )
            ).scalar()
            if not exists:
                print(f"{table}: MISSING")
                continue
            count = (
                await session.execute(text(f"select count(*) from {table}"))  # noqa: S608
            ).scalar_one()
            print(f"{table}: {count} rows")

        users = (
            await session.execute(
                text("select email, role, is_active from users order by email")
            )
        ).all()
        for email, role, active in users:
            print(f"user: {email} role={role} active={active}")


if __name__ == "__main__":
    asyncio.run(main())
