"""Prepare reviewed generated assets, manifest, and transactional DB update SQL.

The script is deliberately idempotent. It copies only approved ID-keyed assets,
preserves the pre-existing manifest once, and creates SQL that updates only rows
whose image_url is still NULL. Run the SQL separately after inspecting counts.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CANDIDATES = DATA / "image_candidates"
STATIC = ROOT / "static" / "images"
SOURCE_MANIFEST = DATA / "generated_image_manifest.json"
TARGET_MANIFEST = DATA / "image_manifest.json"
BACKUP_MANIFEST = DATA / "image_manifest.pre_generated_backup.json"
SQL_OUT = DATA / "image_mapping_update.sql"
REPORT_OUT = ROOT.parent / "reports" / "image_audit" / "integration_checkpoint.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    source = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    entries = source.get("records", {})
    approved = {
        ident: entry
        for ident, entry in entries.items()
        if entry.get("approved_for_mapping") is True
    }
    if len(approved) != len(entries):
        raise SystemExit(f"refusing incomplete manifest: {len(approved)}/{len(entries)} approved")

    # Verify coverage against the captured live DB UUID inventory before copying.
    inventory_dir = DATA
    menu_rows = (inventory_dir / "catalog_db_snapshot.txt").read_text(encoding="utf-8-sig").splitlines()
    restaurant_rows = (inventory_dir / "restaurants_db_snapshot.txt").read_text(encoding="utf-8-sig").splitlines()
    menu_ids = {line.split("|", 1)[0] for line in menu_rows if "|" in line}
    restaurant_ids = {line.split("|", 1)[0] for line in restaurant_rows if "|" in line}
    approved_menu_ids = {ident for ident, entry in approved.items() if entry.get("record_type") == "menu_item"}
    approved_restaurant_ids = {ident for ident, entry in approved.items() if entry.get("record_type") == "restaurant"}
    if menu_ids != approved_menu_ids or restaurant_ids != approved_restaurant_ids:
        raise SystemExit(
            "ID coverage mismatch: "
            f"menu db={len(menu_ids)} approved={len(approved_menu_ids)} "
            f"missing={len(menu_ids - approved_menu_ids)} extra={len(approved_menu_ids - menu_ids)}; "
            f"restaurants db={len(restaurant_ids)} approved={len(approved_restaurant_ids)} "
            f"missing={len(restaurant_ids - approved_restaurant_ids)} extra={len(approved_restaurant_ids - restaurant_ids)}"
        )

    manifest = {"restaurants": {}, "menu_items": {}}
    menu_values: list[tuple[str, str]] = []
    restaurant_values: list[tuple[str, str]] = []
    copied = 0
    for ident, entry in sorted(approved.items()):
        kind = entry["record_type"]
        if kind not in {"restaurant", "menu_item"}:
            raise SystemExit(f"unsupported type for {ident}: {kind}")
        relative = entry["file"]
        candidate = CANDIDATES / relative
        destination = STATIC / relative
        if not candidate.is_file() or sha256(candidate) != entry.get("sha256"):
            raise SystemExit(f"missing or hash-mismatched candidate: {candidate}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and sha256(destination) != entry["sha256"]:
            raise SystemExit(f"refusing to overwrite different static asset: {destination}")
        if not destination.exists():
            shutil.copy2(candidate, destination)
            copied += 1

        image_url = entry["url"]
        manifest_entry = {
            "file": relative,
            "url": image_url,
            "source_url": "generated:openai-image-generation",
            "source_engine": "openai_image_generation",
            "license": entry.get("license", "Original AI-generated image"),
            "sha256": entry["sha256"],
            "image_type": "generated_photograph",
            "visual_relevance": "verified",
            "record_name": entry.get("record_name", ""),
        }
        section = "restaurants" if kind == "restaurant" else "menu_items"
        manifest[section][ident] = manifest_entry
        (restaurant_values if kind == "restaurant" else menu_values).append((ident, image_url))

    if not BACKUP_MANIFEST.exists() and TARGET_MANIFEST.exists():
        shutil.copy2(TARGET_MANIFEST, BACKUP_MANIFEST)
    TARGET_MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def values_sql(values: list[tuple[str, str]]) -> str:
        return ",\n".join(
            f"        ('{ident}'::uuid, '{url}')" for ident, url in values
        )

    expected_menu = len(menu_values)
    expected_restaurants = len(restaurant_values)
    sql = f"""-- Generated from visually approved, UUID-keyed image assets.
-- Updates only rows with NULL image_url and aborts unless all expected rows change.
BEGIN;
DO $$
DECLARE changed integer;
BEGIN
    UPDATE menu_items AS target
       SET image_url = source.image_url
      FROM (VALUES
{values_sql(menu_values)}
      ) AS source(id, image_url)
     WHERE target.id = source.id AND target.image_url IS NULL;
    GET DIAGNOSTICS changed = ROW_COUNT;
    IF changed <> {expected_menu} THEN
        RAISE EXCEPTION 'menu image mapping count mismatch: expected {expected_menu}, changed %', changed;
    END IF;

    UPDATE restaurants AS target
       SET image_url = source.image_url
      FROM (VALUES
{values_sql(restaurant_values)}
      ) AS source(id, image_url)
     WHERE target.id = source.id AND target.image_url IS NULL;
    GET DIAGNOSTICS changed = ROW_COUNT;
    IF changed <> {expected_restaurants} THEN
        RAISE EXCEPTION 'restaurant image mapping count mismatch: expected {expected_restaurants}, changed %', changed;
    END IF;
END $$;
COMMIT;
"""
    SQL_OUT.write_text(sql, encoding="utf-8")
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "catalog_records": len(approved),
                "menu_items": expected_menu,
                "restaurants": expected_restaurants,
                "copied_static_files": copied,
                "manifest": str(TARGET_MANIFEST),
                "manifest_backup": str(BACKUP_MANIFEST),
                "sql": str(SQL_OUT),
                "visually_approved": True,
                "unmapped_rejected_records": 0,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "approved": len(approved),
                "menu_items": expected_menu,
                "restaurants": expected_restaurants,
                "copied_static_files": copied,
                "sql": str(SQL_OUT),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
