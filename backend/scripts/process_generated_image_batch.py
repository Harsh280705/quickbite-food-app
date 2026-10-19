"""Crop a visually reviewed 4x4 generated image sheet into ID-keyed candidates.

The source sheet and JSON sidecar are kept for resumability. Cropped assets are
written to data/image_candidates until the caller explicitly approves a batch.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "generated_image_manifest.json"
CANDIDATES = ROOT / "data" / "image_candidates"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def crop_tile(sheet: Image.Image, index: int) -> Image.Image:
    col, row = index % 4, index // 4
    left, right = round(col * sheet.width / 4), round((col + 1) * sheet.width / 4)
    top, bottom = round(row * sheet.height / 4), round((row + 1) * sheet.height / 4)
    gutter = max(3, min(sheet.width, sheet.height) // 180)
    tile = sheet.crop((left + gutter, top + gutter, right - gutter, bottom - gutter))
    return ImageOps.fit(tile.convert("RGB"), (640, 480), method=Image.Resampling.LANCZOS)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("batch_json", type=Path)
    parser.add_argument("--approve-visual-review", action="store_true")
    args = parser.parse_args()
    batch = json.loads(args.batch_json.read_text(encoding="utf-8"))
    records = batch["records"]
    if not 1 <= len(records) <= 16:
        raise SystemExit("batch must contain 1 to 16 records")
    sheet_path = Path(batch["sheet_path"])
    with Image.open(sheet_path) as opened:
        opened.verify()
    with Image.open(sheet_path) as opened:
        sheet = opened.convert("RGB")
        if sheet.width < 4 * 180 or sheet.height < 4 * 180:
            raise SystemExit(f"grid too small for four-by-four crop: {sheet.size}")

        manifest = {"version": 1, "records": {}}
        if MANIFEST.exists():
            manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        entries = manifest.setdefault("records", {})
        batch_id = batch["batch_id"]
        duplicate_hashes = {
            entry.get("sha256")
            for key, entry in entries.items()
            if key not in {str(record["id"]) for record in records}
        }
        outcomes = []
        for index, record in enumerate(records):
            kind = record["record_type"]
            ident = str(record["id"])
            if kind not in {"menu_item", "restaurant"}:
                raise SystemExit(f"unsupported record_type: {kind}")
            rel = f"{kind == 'restaurant' and 'restaurants' or 'menu'}/{ident}.jpg"
            dest = CANDIDATES / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            if ident in entries and entries[ident].get("sha256"):
                previous = CANDIDATES / entries[ident]["file"]
                if previous.is_file() and sha256(previous) == entries[ident]["sha256"]:
                    outcomes.append({"id": ident, "status": "already_processed"})
                    continue
            crop_tile(sheet, index).save(dest, "JPEG", quality=90, optimize=True)
            with Image.open(dest) as check:
                check.verify()
            digest = sha256(dest)
            duplicate = digest in duplicate_hashes
            duplicate_hashes.add(digest)
            entry = {
                "record_type": kind,
                "record_id": ident,
                "record_name": record["name"],
                "description": record.get("description", ""),
                "cuisine": record.get("cuisine", ""),
                "file": rel,
                "url": f"/static/images/{rel}",
                "sha256": digest,
                "generation_method": "OpenAI image generation; 4x4 sheet tile",
                "generation_batch": batch_id,
                "source_sheet": str(sheet_path),
                "license": "Original AI-generated image; no third-party source asset",
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "generated": True,
                "technically_valid": True,
                "license_checked": True,
                "visually_verified": bool(args.approve_visual_review),
                "approved_for_mapping": bool(args.approve_visual_review and not duplicate),
                "duplicate_hash": duplicate,
                "status": "approved_candidate" if args.approve_visual_review and not duplicate else "review_required",
            }
            entries[ident] = entry
            outcomes.append({"id": ident, "status": entry["status"], "sha256": digest})
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"batch_id": batch["batch_id"], "processed": len(outcomes), "outcomes": outcomes}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
