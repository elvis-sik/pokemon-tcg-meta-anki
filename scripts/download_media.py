#!/usr/bin/env python3
"""Download current display-card and set media into deterministic local files.

No images are shipped in the handoff. This network-dependent step is designed
for the coding agent's local environment and writes an auditable manifest.
"""

from __future__ import annotations

import argparse
import io
import json
import time
from pathlib import Path
from typing import Any, Iterable

import requests
from PIL import Image

from common import (
    GENERATED_DIR,
    MEDIA_DIR,
    REPORTS_DIR,
    stable_media_stem,
    read_csv,
    read_jsonl,
    utc_now_iso,
    write_csv,
    write_json,
)


def candidate_urls(base: str) -> list[str]:
    base = base.strip()
    if not base:
        return []
    lowered = base.casefold()
    if lowered.endswith((".png", ".jpg", ".jpeg", ".webp")):
        return [base]
    # TCGdex image fields are commonly asset bases rather than complete files.
    return [f"{base}/high.png", f"{base}/low.png", f"{base}.png", base]


def fetch_image(
    session: requests.Session,
    urls: Iterable[str],
    *,
    timeout: float,
    retries: int,
) -> tuple[Image.Image, str]:
    failures: list[str] = []
    url_list = list(urls)
    if not url_list:
        raise RuntimeError("missing source URL")
    for url in url_list:
        for attempt in range(retries):
            try:
                response = session.get(url, timeout=timeout)
                if response.status_code == 404:
                    failures.append(f"404 {url}")
                    break
                response.raise_for_status()
                image = Image.open(io.BytesIO(response.content))
                image.load()
                return image.convert("RGB"), response.url
            except (requests.RequestException, OSError) as exc:
                failures.append(f"{url}: {exc}")
                if attempt + 1 < retries:
                    time.sleep(min(8.0, 2**attempt))
    raise RuntimeError(" | ".join(failures[-12:]))


def save_png(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG", optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cards", type=Path, default=GENERATED_DIR / "mechanical_cards.jsonl"
    )
    parser.add_argument(
        "--sets", type=Path, default=GENERATED_DIR / "set_catalog_resolved.csv"
    )
    parser.add_argument(
        "--manifest", type=Path, default=GENERATED_DIR / "media_manifest.json"
    )
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--retries", type=int, default=4)
    args = parser.parse_args()

    cards = read_jsonl(args.cards)
    if not cards:
        raise SystemExit(f"No mechanical cards in {args.cards}")

    session = requests.Session()
    session.headers.update({"User-Agent": "ptcg-anki-handoff/2026-06-25"})
    manifest: dict[str, Any] = {
        "generated_at": utc_now_iso(),
        "cards": {},
        "sets": {},
    }
    failures: list[dict[str, str]] = []

    for index, card in enumerate(cards, 1):
        key = str(card["card_key"])
        stem = stable_media_stem(key)
        destination = MEDIA_DIR / f"{stem}_full.png"
        source_base = str((card.get("display_printing") or {}).get("image_url") or "")
        entry = {
            "card_key": key,
            "source_base_url": source_base,
            "resolved_source_url": "",
            "full_card_filename": destination.name,
            "artwork_filename": f"{stem}_art.png",
            "status": "pending",
        }
        try:
            if destination.exists() and not args.refresh:
                with Image.open(destination) as existing:
                    existing.verify()
                entry["status"] = "cached"
            else:
                image, resolved_url = fetch_image(
                    session,
                    candidate_urls(source_base),
                    timeout=args.timeout,
                    retries=args.retries,
                )
                save_png(image, destination)
                entry["resolved_source_url"] = resolved_url
                entry["status"] = "downloaded"
        except Exception as exc:
            entry["status"] = "failed"
            failures.append({"kind": "card", "key": key, "reason": str(exc)})
        manifest["cards"][key] = entry
        if index % 40 == 0:
            print(f"Processed card media {index}/{len(cards)}")

    if args.sets.exists():
        for row in read_csv(args.sets):
            code = row.get("limitless_code") or row.get("code") or row.get("tcgdex_set_id")
            if not code:
                continue
            set_entry: dict[str, Any] = {"code": code}
            for kind, column in (
                ("mark", "set_mark_asset_url"),
                ("logo", "set_logo_asset_url"),
            ):
                base = str(row.get(column) or "")
                filename = f"ptcg_set_{code.casefold()}_{kind}.png"
                destination = MEDIA_DIR / filename
                status = "missing_source"
                resolved_url = ""
                if base:
                    try:
                        if destination.exists() and not args.refresh:
                            with Image.open(destination) as existing:
                                existing.verify()
                            status = "cached"
                        else:
                            image, resolved_url = fetch_image(
                                session,
                                candidate_urls(base),
                                timeout=args.timeout,
                                retries=args.retries,
                            )
                            save_png(image, destination)
                            status = "downloaded"
                    except Exception as exc:
                        status = "failed"
                        failures.append(
                            {"kind": f"set_{kind}", "key": str(code), "reason": str(exc)}
                        )
                set_entry[f"{kind}_source_base_url"] = base
                set_entry[f"{kind}_resolved_source_url"] = resolved_url
                set_entry[f"{kind}_filename"] = filename if status in {"cached", "downloaded"} else ""
                set_entry[f"{kind}_status"] = status
            manifest["sets"][str(code)] = set_entry

    write_json(args.manifest, manifest)
    write_csv(REPORTS_DIR / "media_failures.csv", failures, ["kind", "key", "reason"])
    summary = {
        "card_count": len(cards),
        "card_media_ready": sum(
            1
            for entry in manifest["cards"].values()
            if entry["status"] in {"cached", "downloaded"}
        ),
        "set_count": len(manifest["sets"]),
        "failure_count": len(failures),
        "manifest": str(args.manifest),
    }
    write_json(REPORTS_DIR / "media_summary.json", summary)
    print(json.dumps(summary, indent=2))
    if failures and not args.continue_on_error:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
