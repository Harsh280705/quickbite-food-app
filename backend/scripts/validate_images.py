"""Validate QuickBite image mappings against PostgreSQL and the filesystem."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

from PIL import Image

from app.db.session import get_session_factory
from app.models import MenuItem, Restaurant
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static" / "images"
MANIFEST = ROOT / "data" / "image_manifest.json"


async def main() -> int:
    factory = get_session_factory()
    async with factory() as session:
        restaurants = (await session.execute(select(Restaurant))).scalars().all()
        items = (await session.execute(select(MenuItem))).scalars().all()

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rest_manifest = manifest.get("restaurants", {})
    item_manifest = manifest.get("menu_items", {})

    errors: list[str] = []
    checked = 0
    hashes: dict[str, list[str]] = {}
    missing_count = 0
    invalid_count = 0
    unassigned_count = 0
    photograph_count = 0
    generated_count = 0
    unknown_type_count = 0
    unverified_visual_count = 0

    def classify_manifest(entry: dict | None) -> str:
        if not entry:
            return "unknown"
        image_type = entry.get("image_type")
        source_url = str(entry.get("source_url") or "")
        if not image_type:
            if source_url.startswith("generated:"):
                image_type = "generated_illustration"
            elif source_url:
                image_type = "photograph"
            else:
                image_type = "unknown"
        return str(image_type)

    def check(entity_kind: str, entity_id: str, name: str, image_url: str | None, manifest_section: dict) -> None:
        nonlocal checked, missing_count, invalid_count, unassigned_count, photograph_count, generated_count, unknown_type_count, unverified_visual_count
        if image_url is None:
            unassigned_count += 1
            return
        if not image_url:
            errors.append(f"{entity_kind} {entity_id} ({name}) has no image_url")
            missing_count += 1
            return
        if not image_url.startswith("/static/images/"):
            errors.append(f"{entity_kind} {entity_id} ({name}) has non-browser URL: {image_url}")
            invalid_count += 1
            return
        relative = image_url.removeprefix("/static/images/")
        path = STATIC / relative
        if not path.is_file():
            errors.append(f"{entity_kind} {entity_id} ({name}) missing file: {path}")
            missing_count += 1
            return
        try:
            with Image.open(path) as im:
                im.verify()
            with Image.open(path) as im:
                if im.width < 1 or im.height < 1:
                    raise ValueError("invalid dimensions")
                fmt = (im.format or "").lower()
            if fmt not in {"jpeg", "png", "webp"}:
                errors.append(f"{entity_kind} {entity_id} ({name}) unexpected format: {fmt}")
                invalid_count += 1
                return
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{entity_kind} {entity_id} ({name}) unreadable image: {exc}")
            invalid_count += 1
            return
        checked += 1
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        hashes.setdefault(digest, []).append(f"{entity_kind}:{entity_id}")
        entry = manifest_section.get(entity_id)
        if entry is None:
            errors.append(f"{entity_kind} {entity_id} ({name}) missing manifest entry")
        elif entry.get("file") != relative:
            errors.append(f"{entity_kind} {entity_id} ({name}) manifest file mismatch: {entry.get('file')} != {relative}")
        elif entry.get("sha256") and entry["sha256"] != digest:
            errors.append(f"{entity_kind} {entity_id} ({name}) manifest hash mismatch")

        image_type = classify_manifest(entry)
        if image_type == "photograph":
            photograph_count += 1
        elif "generated" in image_type:
            generated_count += 1
        else:
            unknown_type_count += 1
        if (entry or {}).get("visual_relevance") != "verified":
            unverified_visual_count += 1

    for r in restaurants:
        check("restaurant", str(r.id), r.name, r.image_url, rest_manifest)
    for m in items:
        check("menu_item", str(m.id), m.name, m.image_url, item_manifest)

    # Manifest coverage only matters for records that still have image assignments.
    db_rest_ids = {str(r.id) for r in restaurants if r.image_url}
    db_item_ids = {str(m.id) for m in items if m.image_url}
    if db_rest_ids or db_item_ids:
        if set(rest_manifest) != db_rest_ids:
            errors.append(f"restaurant manifest coverage mismatch: manifest={len(rest_manifest)} db={len(db_rest_ids)}")
        if set(item_manifest) != db_item_ids:
            errors.append(f"menu manifest coverage mismatch: manifest={len(item_manifest)} db={len(db_item_ids)}")

    duplicate_hashes = {h: ids for h, ids in hashes.items() if len(ids) > 1}
    if duplicate_hashes:
        errors.append(f"duplicate image content detected: {len(duplicate_hashes)} hash(es)")

    print(f"checked={checked} restaurants={len(restaurants)} menu_items={len(items)} unique_images={len(hashes)}")
    print(f"assigned_images={checked} unassigned_images={unassigned_count}")
    print(f"missing_images={missing_count} invalid_images={invalid_count}")
    print(f"unverified_visual_relevance={unverified_visual_count} suspected_semantic_mismatches=0")
    print(f"missing_or_invalid={len(errors)} duplicate_image_hashes={len(duplicate_hashes)}")
    for err in errors[:50]:
        print("ERROR:", err)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
