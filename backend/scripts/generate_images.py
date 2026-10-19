"""Generate validated, unique original illustration assets for every catalog entity.

Used when reliable bulk photo downloads are unavailable. Creates one JPEG per
restaurant/menu item under backend/static/images and writes image_manifest.json.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.db.session import get_session_factory
from app.models import MenuItem, Restaurant
from sqlalchemy import select

from scripts.image_paths import (
    menu_image_relative,
    restaurant_image_relative,
    to_url,
)

ROOT = Path(__file__).resolve().parents[1]
STATIC_IMAGES = ROOT / "static" / "images"
MANIFEST_PATH = ROOT / "data" / "image_manifest.json"

PALETTE = [
    (239, 125, 79),
    (76, 163, 126),
    (91, 134, 229),
    (181, 101, 167),
    (224, 168, 62),
    (95, 180, 196),
    (201, 98, 98),
    (120, 132, 168),
]


def color_for(name: str) -> tuple[int, int, int]:
    h = int(hashlib.sha256(name.encode()).hexdigest(), 16)
    return PALETTE[h % len(PALETTE)]


def make_image(title: str, subtitle: str, dest: Path, seed: str = "") -> None:
    w, h = 640, 480
    base = color_for(title + "|" + seed)
    img = Image.new("RGB", (w, h), base)
    draw = ImageDraw.Draw(img)
    # plate circle
    cx, cy = w // 2, h // 2 - 20
    r = 150
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(250, 248, 242), outline=(220, 215, 205), width=4)
    # simple utensil lines
    draw.line((cx - 60, cy - 40, cx + 60, cy + 40), fill=base, width=8)
    draw.line((cx - 60, cy + 40, cx + 60, cy - 40), fill=base, width=8)
    # unique marker
    marker = int(hashlib.sha256((title + "|" + seed).encode()).hexdigest(), 16)
    marker_color = (marker % 200 + 40, (marker // 200) % 200 + 40, (marker // 40000) % 200 + 40)
    draw.rectangle((24, 24, 96, 96), fill=marker_color, outline=(255, 255, 255), width=2)
    # text
    try:
        font_title = ImageFont.truetype("arial.ttf", 28)
        font_sub = ImageFont.truetype("arial.ttf", 16)
    except Exception:
        font_title = ImageFont.load_default()
        font_sub = ImageFont.load_default()
    # title wrapped
    words = title.split()
    lines = []
    cur = ""
    for word in words:
        test = (cur + " " + word).strip()
        if len(test) > 22:
            if cur:
                lines.append(cur)
            cur = word
        else:
            cur = test
    if cur:
        lines.append(cur)
    y = h - 150
    for line in lines[:3]:
        bbox = draw.textbbox((0, 0), line, font=font_title)
        tw = bbox[2] - bbox[0]
        draw.text(((w - tw) // 2, y), line, fill=(255, 255, 255), font=font_title)
        y += 34
    if subtitle:
        bbox = draw.textbbox((0, 0), subtitle[:40], font=font_sub)
        tw = bbox[2] - bbox[0]
        draw.text(((w - tw) // 2, y + 6), subtitle[:40], fill=(255, 255, 255), font=font_sub)
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest, format="JPEG", quality=88, optimize=True)


async def main() -> None:
    STATIC_IMAGES.mkdir(parents=True, exist_ok=True)
    (ROOT / "data").mkdir(parents=True, exist_ok=True)

    factory = get_session_factory()
    async with factory() as session:
        restaurants = (await session.execute(select(Restaurant))).scalars().all()
        menu_items = (await session.execute(select(MenuItem))).scalars().all()
        rest_map = {r.id: r for r in restaurants}

    manifest = {"restaurants": {}, "menu_items": {}}

    for r in restaurants:
        rel = restaurant_image_relative(r.name)
        dest = STATIC_IMAGES / rel
        make_image(r.name, r.cuisine, dest, seed=str(r.id))
        manifest["restaurants"][str(r.id)] = {
            "file": rel,
            "url": to_url(rel),
            "source_url": "generated:original_illustration",
            "license": "CC0-1.0 (original work created for demo)",
            "attribution": "QuickBite demo image generator",
            "sha256": hashlib.sha256(dest.read_bytes()).hexdigest(),
        }

    for m in menu_items:
        rest = rest_map.get(m.restaurant_id)
        rname = rest.name if rest else "restaurant"
        rel = menu_image_relative(rname, m.name)
        dest = STATIC_IMAGES / rel
        make_image(m.name, (rest.cuisine if rest else ""), dest, seed=str(m.id))
        manifest["menu_items"][str(m.id)] = {
            "file": rel,
            "url": to_url(rel),
            "source_url": "generated:original_illustration",
            "license": "CC0-1.0 (original work created for demo)",
            "attribution": "QuickBite demo image generator",
            "sha256": hashlib.sha256(dest.read_bytes()).hexdigest(),
        }

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"generated {len(restaurants)} restaurant + {len(menu_items)} menu images")
    print(f"manifest: {MANIFEST_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
