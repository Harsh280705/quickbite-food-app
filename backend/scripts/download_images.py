"""Download and validate real food photographs into backend/static/images.

Uses Bing image search for each restaurant/menu item. The previous Wikimedia
Commons path is unavailable from this environment, so search results are used
and their rights are recorded as unverified.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import io
import json
import re
import socket
import time
import urllib.parse
import urllib.request
from pathlib import Path

socket.setdefaulttimeout(5)

from PIL import Image

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
FAILED_PATH = ROOT / "data" / "failed_images.json"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
MAX_ATTEMPTS = 6


def fetch_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.read(5_000_000)


def bing_image_urls(query: str, limit: int = 20) -> list[str]:
    url = "https://www.bing.com/images/search?q=" + urllib.parse.quote_plus(query)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=5) as resp:
        html = resp.read().decode("utf-8", "replace")
    urls = re.findall(r'murl&quot;:&quot;(https?://.+?)&quot;', html)
    out = []
    seen = set()
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
        if len(out) >= limit:
            break
    return out


def domain_of(url: str) -> str:
    return urllib.parse.urlparse(url).netloc


def is_generated(entry: dict | None) -> bool:
    return bool(entry and str(entry.get("source_url", "")).startswith("generated:"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def process_image(data: bytes, dest: Path) -> None:
    with Image.open(io.BytesIO(data)) as im:
        if im.mode in ("P", "PA"):
            im = im.convert("RGBA")
        im = im.convert("RGB")
        w, h = im.size
        if w < 240 or h < 180:
            raise RuntimeError("image too small")
        target = 4 / 3
        if w / h > target:
            new_w = int(h * target)
            left = (w - new_w) // 2
            im = im.crop((left, 0, left + new_w, h))
        else:
            new_h = int(w / target)
            top = (h - new_h) // 2
            im = im.crop((0, top, w, top + new_h))
        im = im.resize((640, 480), Image.LANCZOS)
        dest.parent.mkdir(parents=True, exist_ok=True)
        im.save(dest, format="JPEG", quality=85, optimize=True)
    with Image.open(dest) as check:
        if check.format not in ("JPEG", "PNG"):
            raise RuntimeError("invalid saved image")
        if check.size[0] < 200 or check.size[1] < 200:
            raise RuntimeError("image too small")


def save_manifest(manifest: dict) -> None:
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--only", choices=["restaurants", "menu", "all"], default="all")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--count", type=int, default=25)
    parser.add_argument("--generated-only", action="store_true")
    args = parser.parse_args()

    STATIC_IMAGES.mkdir(parents=True, exist_ok=True)
    (ROOT / "data").mkdir(parents=True, exist_ok=True)

    existing = {}
    if MANIFEST_PATH.exists():
        try:
            existing = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        except Exception:
            existing = {}

    failed = {"restaurants": [], "menu_items": []}
    if FAILED_PATH.exists():
        try:
            failed = json.loads(FAILED_PATH.read_text(encoding="utf-8"))
        except Exception:
            failed = {"restaurants": [], "menu_items": []}
    failed_rest = set(failed.get("restaurants", []))
    failed_menu = set(failed.get("menu_items", []))

    factory = get_session_factory()
    async with factory() as session:
        restaurants = (await session.execute(select(Restaurant))).scalars().all()
        menu_items = (await session.execute(select(MenuItem))).scalars().all()
        rest_map = {r.id: r for r in restaurants}

    manifest = {
        "restaurants": dict(existing.get("restaurants", {})),
        "menu_items": dict(existing.get("menu_items", {})),
    }

    used_hashes = set()
    hash_counts = {}
    for path in STATIC_IMAGES.rglob("*"):
        if path.is_file():
            try:
                digest = sha256_file(path)
                used_hashes.add(digest)
                hash_counts[digest] = hash_counts.get(digest, 0) + 1
            except Exception:
                pass

    missing = []
    total_targets = 0
    done = 0

    def should_skip(dest: Path, key: str, section: dict, rel: str) -> bool:
        if args.force:
            return False
        if not dest.exists():
            return False
        entry = section.get(key)
        if not entry or is_generated(entry):
            return False
        if entry.get("file") != rel:
            return False
        try:
            if entry.get("sha256") and entry["sha256"] != sha256_file(dest):
                return False
            if hash_counts.get(sha256_file(dest), 0) > 1:
                return False
        except Exception:
            return False
        return True

    # Restaurants
    if args.only in ("restaurants", "all"):
        for r in restaurants:
            rel = restaurant_image_relative(r.name)
            dest = STATIC_IMAGES / rel
            key = str(r.id)
            total_targets += 1
            if key in failed_rest:
                done += 1
                if done % 50 == 0:
                    print(f"[{done}] skip failed restaurant {r.name}", flush=True)
                continue
            if should_skip(dest, key, manifest["restaurants"], rel):
                done += 1
                if done % 50 == 0:
                    print(f"[{done}] skip restaurant {r.name}", flush=True)
                continue
            queries = [
                f"{r.name} {r.cuisine} restaurant food",
                f"{r.cuisine} food restaurant",
            ]
            success = False
            for query in queries:
                if success:
                    break
                try:
                    candidates = bing_image_urls(query)
                except Exception as e:
                    print(f"restaurant {r.name} search failed: {e}")
                    continue
                for cand in candidates:
                    try:
                        data = fetch_bytes(cand)
                        process_image(data, dest)
                        sha = sha256_file(dest)
                        if sha in used_hashes:
                            # try another candidate
                            continue
                        used_hashes.add(sha)
                        manifest["restaurants"][key] = {
                            "file": rel,
                            "url": to_url(rel),
                            "source_url": cand,
                            "source_engine": "bing_image_search",
                            "license": "Unknown (web image search result; rights not verified)",
                            "attribution": domain_of(cand),
                            "sha256": sha,
                            "image_type": "photograph",
                            "visual_relevance": "search_query_match_unverified",
                        }
                        success = True
                        break
                    except Exception as e:
                        continue
        if not success:
            missing.append(("restaurant", r.name, str(r.id)))
            failed_rest.add(key)
            failed["restaurants"] = sorted(failed_rest)
            FAILED_PATH.write_text(json.dumps(failed, indent=2, ensure_ascii=False), encoding="utf-8")
        done += 1
        print(f"[{done}] restaurant {r.name}: {'ok' if success else 'MISSING'}", flush=True)
        save_manifest(manifest)
        time.sleep(0.02)

    # Menu items
    if args.only in ("menu", "all"):
        if args.generated_only:
            generated_items = [
                m for m in menu_items
                if (not (STATIC_IMAGES / menu_image_relative(
                    (rest_map.get(m.restaurant_id).name if rest_map.get(m.restaurant_id) else "restaurant"),
                    m.name,
                )).exists())
                or is_generated(manifest["menu_items"].get(str(m.id)))
            ]
            selected_items = generated_items[args.start:]
            if args.count is not None:
                selected_items = selected_items[:args.count]
        else:
            selected_items = menu_items[args.start:]
            if args.count is not None:
                selected_items = selected_items[:args.count]
        for m in selected_items:
            rest = rest_map.get(m.restaurant_id)
            rname = rest.name if rest else "restaurant"
            rel = menu_image_relative(rname, m.name)
            dest = STATIC_IMAGES / rel
            key = str(m.id)
            total_targets += 1
            if key in failed_menu:
                done += 1
                if done % 50 == 0:
                    print(f"[{done}] skip failed menu {m.name}", flush=True)
                continue
            if should_skip(dest, key, manifest["menu_items"], rel):
                done += 1
                if done % 50 == 0:
                    print(f"[{done}] skip menu {m.name}", flush=True)
                continue
            queries = [m.name, f"{m.name} food dish"]
            success = False
            for query in queries:
                if success:
                    break
                try:
                    candidates = bing_image_urls(query)
                except Exception as e:
                    print(f"menu {m.name} search failed: {e}")
                    continue
                for cand in candidates:
                    try:
                        data = fetch_bytes(cand)
                        process_image(data, dest)
                        sha = sha256_file(dest)
                        if sha in used_hashes:
                            print(f"  duplicate hash for {m.name}: {sha}", flush=True)
                            continue
                        used_hashes.add(sha)
                        manifest["menu_items"][key] = {
                            "file": rel,
                            "url": to_url(rel),
                            "source_url": cand,
                            "source_engine": "bing_image_search",
                            "license": "Unknown (web image search result; rights not verified)",
                            "attribution": domain_of(cand),
                            "sha256": sha,
                            "image_type": "photograph",
                            "visual_relevance": "search_query_match_unverified",
                        }
                        success = True
                        break
                    except Exception:
                        continue
            if not success:
                missing.append(("menu_item", m.name, str(m.id)))
                failed_menu.add(key)
                failed["menu_items"] = sorted(failed_menu)
                FAILED_PATH.write_text(json.dumps(failed, indent=2, ensure_ascii=False), encoding="utf-8")
            done += 1
            if done % 1 == 0:
                print(f"[{done}] menu {m.name}: {'ok' if success else 'MISSING'}", flush=True)
            save_manifest(manifest)
            time.sleep(0.02)

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"manifest written: {MANIFEST_PATH}")
    print(f"missing: {len(missing)}")
    if missing:
        print("MISSING ASSETS:")
        for kind, name, ident in missing[:100]:
            print(f"  {kind}: {name} ({ident})")


if __name__ == "__main__":
    asyncio.run(main())


