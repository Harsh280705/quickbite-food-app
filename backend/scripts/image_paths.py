"""Deterministic image path helpers shared by seed and download scripts."""

from __future__ import annotations

import re
import unicodedata


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "item"


def restaurant_image_relative(name: str) -> str:
    return f"restaurants/{slugify(name)}.jpg"


def menu_image_relative(restaurant_name: str, item_name: str) -> str:
    return f"menu/{slugify(restaurant_name)}_{slugify(item_name)}.jpg"


def to_url(relative: str) -> str:
    return f"/static/images/{relative}"
