#!/usr/bin/env python3
"""Discover all English printings sharing the study cards' exact names.

The result is used to find the earliest printing for the natural key, choose a
recent display image, and detect same-name mechanical ambiguity in Standard.
This is a network-dependent, cacheable step.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from common import (
    GENERATED_DIR,
    REPORTS_DIR,
    card_category,
    card_name,
    mechanical_fingerprint,
    normalize_name,
    read_jsonl,
    utc_now_iso,
    write_json,
    write_jsonl,
)
from tcgdex_client import TCGdexClient, TCGdexError


def set_id_from_card(card: dict[str, Any]) -> str | None:
    set_obj = card.get("set")
    if isinstance(set_obj, dict) and set_obj.get("id"):
        return str(set_obj["id"])
    card_id = str(card.get("id") or "")
    return card_id.rsplit("-", 1)[0] if "-" in card_id else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input", type=Path, default=GENERATED_DIR / "resolved_source_cards.jsonl"
    )
    parser.add_argument(
        "--output", type=Path, default=GENERATED_DIR / "printing_universe.jsonl"
    )
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--max-per-name", type=int, default=600)
    args = parser.parse_args()

    source = read_jsonl(args.input)
    if not source:
        raise SystemExit(f"No resolved cards in {args.input}; run resolve_cards_tcgdex.py")
    names = sorted({normalize_name(record["name"]) for record in source})
    client = TCGdexClient(refresh=args.refresh)

    set_cache: dict[str, dict[str, Any]] = {}
    records_by_id: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, str]] = []

    for index, name in enumerate(names, 1):
        try:
            briefs = client.find_cards_by_exact_name(name)
        except TCGdexError as exc:
            failures.append({"name": name, "card_id": "", "reason": str(exc)})
            continue
        # Providers occasionally perform case-sensitive exact matching. Enforce
        # exact normalized equality again locally.
        briefs = [brief for brief in briefs if normalize_name(brief.get("name")) == name]
        if len(briefs) > args.max_per_name:
            failures.append(
                {
                    "name": name,
                    "card_id": "",
                    "reason": f"{len(briefs)} matches exceeds --max-per-name",
                }
            )
            continue

        for brief in briefs:
            card_id = str(brief.get("id") or "")
            if not card_id or card_id in records_by_id:
                continue
            try:
                card = client.get_card(card_id)
                set_id = set_id_from_card(card)
                if set_id and set_id not in set_cache:
                    set_cache[set_id] = client.get_set(set_id)
                set_detail = set_cache.get(set_id or "", {})
                payload_name = card_name(card)
                if payload_name != name:
                    continue
                legal = card.get("legal") if isinstance(card.get("legal"), dict) else {}
                records_by_id[card_id] = {
                    "tcgdex_card_id": card_id,
                    "tcgdex_set_id": set_id,
                    "collector_number": str(card.get("localId") or ""),
                    "name": payload_name,
                    "category": card_category(card),
                    "release_date": set_detail.get("releaseDate")
                    or set_detail.get("release_date"),
                    "standard_legal": legal.get("standard"),
                    "regulation_mark": card.get("regulationMark"),
                    "image_url": card.get("image"),
                    "mechanical_fingerprint": mechanical_fingerprint(card),
                    "fetched_at": utc_now_iso(),
                    "raw_payload": card,
                    "set_payload": set_detail,
                }
            except Exception as exc:
                failures.append({"name": name, "card_id": card_id, "reason": str(exc)})
        if index % 25 == 0:
            print(f"Discovered printings for {index}/{len(names)} names", file=sys.stderr)

    records = sorted(
        records_by_id.values(),
        key=lambda row: (row["name"], row.get("release_date") or "", row["tcgdex_card_id"]),
    )
    write_jsonl(args.output, records)
    discovered_set_rows = []
    for set_id, detail in sorted(set_cache.items()):
        discovered_set_rows.append(
            {
                "tcgdex_set_id": set_id,
                "full_name": detail.get("name", ""),
                "release_date_iso": detail.get("releaseDate") or detail.get("release_date") or "",
                "set_mark_asset_url": detail.get("symbol", ""),
                "set_logo_asset_url": detail.get("logo", ""),
                "limitless_code": "",
                "mapping_status": "needs_override_if_used_as_origin",
            }
        )
    from common import write_csv
    write_csv(
        GENERATED_DIR / "discovered_set_catalog.csv",
        discovered_set_rows,
        [
            "tcgdex_set_id",
            "full_name",
            "release_date_iso",
            "set_mark_asset_url",
            "set_logo_asset_url",
            "limitless_code",
            "mapping_status",
        ],
    )
    summary = {
        "study_name_count": len(names),
        "printing_count": len(records),
        "failure_count": len(failures),
        "failures": failures,
    }
    write_json(REPORTS_DIR / "printing_discovery_summary.json", summary)
    print(json.dumps({k: v for k, v in summary.items() if k != "failures"}, indent=2))
    if failures and not args.continue_on_error:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
