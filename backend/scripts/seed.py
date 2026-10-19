"""Repeatable, idempotent seed command.

Run from the ``backend`` directory:

    python -m scripts.seed                # local venv
    python -m scripts.seed --reset-demo   # also deletes demo orders first

Seeds (safe to re-run; uses upserts keyed by stable identifiers):
- 50+ demo customer accounts + existing administrator accounts
- 20 restaurants with menus (prices in integer minor units)
- simulated drivers used by the delivery worker
- deterministic image_url mappings (files provided by download_images.py)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import uuid

from sqlalchemy import delete, select

from app.core.security import hash_password
from app.db.session import get_session_factory
from app.models import (
    CheckoutIdempotency,
    Driver,
    MenuItem,
    Notification,
    Order,
    OrderItem,
    OrderStatusHistory,
    ProcessedEvent,
    Restaurant,
    SimulatedPayment,
    User,
)
from app.models.messaging import OutboxEvent, QuarantineRecord, RetryJob

from scripts.catalog_expanded import RESTAURANTS as EXPANDED_RESTAURANTS, UNAVAILABLE_ITEMS as EXPANDED_UNAVAILABLE
from scripts.demo_catalog import RESTAURANTS, UNAVAILABLE_ITEMS
from scripts.image_paths import menu_image_relative, restaurant_image_relative, to_url

RESTAURANTS = list(RESTAURANTS) + list(EXPANDED_RESTAURANTS)
UNAVAILABLE_ITEMS = set(UNAVAILABLE_ITEMS) | set(EXPANDED_UNAVAILABLE)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("quickbite.seed")

CUSTOMER_PASSWORD = "DemoPass123!"
ADMIN_PASSWORD = "AdminPass123!"

FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan", "Krishna", "Ishaan",
    "Shaurya", "Atharv", "Advik", "Pranav", "Advaith", "Kabir", "Ritvik", "Anirudh", "Dhruv", "Kunal",
    "Ananya", "Diya", "Myra", "Sara", "Aadhya", "Ira", "Anika", "Navya", "Kiara", "Saanvi",
    "Pooja", "Neha", "Riya", "Meera", "Tanya", "Kavya", "Sneha", "Priya", "Shreya", "Nisha",
    "Rahul", "Rohit", "Amit", "Vikram", "Suresh", "Manish", "Nitin", "Deepak", "Varun", "Harsh",
]
LAST_NAMES = [
    "Sharma", "Verma", "Gupta", "Singh", "Patel", "Reddy", "Iyer", "Nair", "Joshi", "Kulkarni",
    "Mehta", "Shah", "Kapoor", "Malhotra", "Chopra", "Bansal", "Agarwal", "Saxena", "Mishra", "Pandey",
]


def _customer_specs() -> list[tuple[str, str, str]]:
    specs = [
        ("demo@quickbite.example", "Demo Customer"),
        ("alice@quickbite.example", "Alice Sharma"),
    ]
    idx = 1
    for fn in FIRST_NAMES:
        for ln in LAST_NAMES:
            if len(specs) >= 52:
                break
            specs.append((f"customer{idx:02d}@quickbite.example", f"{fn} {ln}"))
            idx += 1
        if len(specs) >= 52:
            break
    # Ensure at least 50 customers total (demo + alice + 48)
    return specs[:50]


USERS: list[tuple[str, str, str, str]] = []
for email, name in _customer_specs():
    USERS.append((email, name, "customer", CUSTOMER_PASSWORD))
USERS.append(("admin@quickbite.example", "QuickBite Admin", "admin", ADMIN_PASSWORD))
# Preserve a second admin if it exists; do not create duplicates beyond existing.
# (admin@quickbite.local is pre-existing and is left untouched.)

DRIVERS = [
    ("Ravi Kumar", "Bike - MH 01 AB 1234", "+91-9000000001"),
    ("Sneha Patil", "Scooter - MH 02 CD 5678", "+91-9000000002"),
    ("Arjun Mehta", "Bike - MH 03 EF 9012", "+91-9000000003"),
]


async def _upsert_user(session, email: str, name: str, role: str, password: str) -> None:
    existing = (
        await session.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()
    if existing is None:
        session.add(
            User(
                email=email,
                full_name=name,
                role=role,
                password_hash=hash_password(password),
                is_active=True,
            )
        )
        log.info("created user %s (%s)", email, role)
    else:
        existing.full_name = name
        existing.role = role
        existing.is_active = True
        log.info("user exists %s (%s)", email, role)


async def _upsert_restaurant(session, spec: dict) -> Restaurant:
    restaurant = (
        await session.execute(select(Restaurant).where(Restaurant.name == spec["name"]))
    ).scalar_one_or_none()
    if restaurant is None:
        restaurant = Restaurant(
            name=spec["name"],
            description=spec["description"],
            cuisine=spec["cuisine"],
            rating=spec["rating"],
            is_active=True,
        )
        session.add(restaurant)
        await session.flush()
        log.info("created restaurant %s", spec["name"])
    else:
        pass

    for item_name, description, price_minor in spec["menu"]:
        available = (spec["key"], item_name) not in UNAVAILABLE_ITEMS
        item = (
            await session.execute(
                select(MenuItem).where(
                    MenuItem.restaurant_id == restaurant.id, MenuItem.name == item_name
                )
            )
        ).scalar_one_or_none()
        desired_image = to_url(menu_image_relative(spec["name"], item_name))
        if item is None:
            session.add(
                MenuItem(
                    restaurant_id=restaurant.id,
                    name=item_name,
                    description=description,
                    price_minor=price_minor,
                    currency="INR",
                    is_available=available,
                )
            )
        else:
            pass
    return restaurant


async def reset_demo_data(session) -> None:
    """Remove demo orders and every dependent record (development only)."""
    customer_ids = (
        (await session.execute(select(User.id).where(User.role == "customer")))
        .scalars()
        .all()
    )
    order_ids = (
        (
            await session.execute(
                select(Order.id).where(Order.customer_id.in_(list(customer_ids)))
            )
        )
        .scalars()
        .all()
    )
    if not order_ids:
        log.info("reset: no demo orders to delete")
        return
    for model in (
        OrderItem,
        OrderStatusHistory,
        SimulatedPayment,
        Notification,
        CheckoutIdempotency,
    ):
        await session.execute(delete(model).where(model.order_id.in_(order_ids)))
    await session.execute(delete(Notification).where(Notification.order_id.in_(order_ids)))
    await session.execute(delete(OutboxEvent).where(OutboxEvent.order_id.in_(order_ids)))
    await session.execute(delete(RetryJob).where(RetryJob.order_id.in_(order_ids)))
    await session.execute(
        delete(QuarantineRecord).where(QuarantineRecord.order_id.in_(order_ids))
    )
    await session.execute(
        delete(ProcessedEvent).where(ProcessedEvent.order_id.in_(order_ids))
    )
    await session.execute(delete(Order).where(Order.id.in_(order_ids)))
    log.info("reset: deleted %d demo orders", len(order_ids))


async def seed(reset: bool = False) -> None:
    factory = get_session_factory()
    async with factory() as session:
        if reset:
            await reset_demo_data(session)
        for email, name, role, password in USERS:
            await _upsert_user(session, email, name, role, password)
        for spec in RESTAURANTS:
            await _upsert_restaurant(session, spec)
        for name, vehicle, phone in DRIVERS:
            driver = (
                await session.execute(select(Driver).where(Driver.name == name))
            ).scalar_one_or_none()
            if driver is None:
                session.add(Driver(name=name, vehicle=vehicle, phone=phone, is_active=True))
                log.info("created driver %s", name)
            else:
                driver.vehicle = vehicle
                driver.phone = phone
                driver.is_active = True

        # Verify image mappings for seed-managed catalog.
        restaurants = (await session.execute(select(Restaurant))).scalars().all()
        missing_images = [r.name for r in restaurants if not r.image_url]
        items = (await session.execute(select(MenuItem))).scalars().all()
        missing_item_images = [m.name for m in items if not m.image_url]
        if missing_images:
            log.warning("restaurants missing image_url: %s", missing_images)
        if missing_item_images:
            log.warning("menu items missing image_url: %d", len(missing_item_images))

        await session.commit()
    log.info("seed complete: %d users, %d restaurants, %d menu items",
             len(USERS), len(RESTAURANTS), sum(len(r["menu"]) for r in RESTAURANTS))


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed QuickBite development data")
    parser.add_argument(
        "--reset-demo",
        action="store_true",
        help="Delete existing demo orders (and dependent rows) before seeding",
    )
    args = parser.parse_args()
    asyncio.run(seed(reset=args.reset_demo))


if __name__ == "__main__":
    main()
