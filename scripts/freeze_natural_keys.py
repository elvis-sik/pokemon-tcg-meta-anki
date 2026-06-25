#!/usr/bin/env python3
"""Append audited mechanical fingerprints and natural keys to the registry.

Run only after reviewing the origin-printing report. Existing assignments are
never rewritten by this script.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from common import DATA_DIR, GENERATED_DIR, read_csv, read_jsonl, utc_now_iso, write_csv

FIELDS = [
    "mechanical_fingerprint",
    "mechanical_card_key",
    "origin_set_code",
    "origin_collector_number",
    "assigned_on",
    "source_note",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cards", type=Path, default=GENERATED_DIR / "mechanical_cards.jsonl"
    )
    parser.add_argument(
        "--registry", type=Path, default=DATA_DIR / "natural_key_registry.csv"
    )
    parser.add_argument("--source-note", default="audited local build")
    args = parser.parse_args()

    cards = read_jsonl(args.cards)
    existing = read_csv(args.registry) if args.registry.exists() else []
    by_fingerprint = {row.get("mechanical_fingerprint", ""): row for row in existing}
    added = 0
    for card in cards:
        fingerprint = str(card["mechanical_fingerprint"])
        if fingerprint in by_fingerprint:
            continue
        origin = card.get("origin_printing") or {}
        row = {
            "mechanical_fingerprint": fingerprint,
            "mechanical_card_key": card["card_key"],
            "origin_set_code": origin.get("set_code", ""),
            "origin_collector_number": origin.get("collector_number", ""),
            "assigned_on": utc_now_iso()[:10],
            "source_note": args.source_note,
        }
        existing.append(row)
        by_fingerprint[fingerprint] = row
        added += 1
    existing.sort(key=lambda row: row.get("mechanical_card_key", "").casefold())
    write_csv(args.registry, existing, FIELDS)
    print(f"Registry rows: {len(existing)}; added: {added}")


if __name__ == "__main__":
    main()
