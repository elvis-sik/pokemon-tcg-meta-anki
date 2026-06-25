#!/usr/bin/env python3
"""Validate the frozen top-50 metagame and representative-deck source snapshot."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

from common import DATA_DIR, REPORTS_DIR, parse_bool, read_csv, read_json, write_json
from decode_limitless_builder import decode_builder

EXPECTED = {
    "archetypes": 50,
    "deck_lines": 1305,
    "top10_raw_locators": 145,
    "top50_raw_locators": 361,
    "top10_combined_entries": 4194,
    "top50_named_combined_entries": 5688,
    "classified_entries_total": 5775,
}


def error(errors: list[str], message: str) -> None:
    errors.append(message)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true", default=True)
    parser.add_argument(
        "--report", type=Path, default=REPORTS_DIR / "source_validation.json"
    )
    args = parser.parse_args()

    errors: list[str] = []
    warnings: list[str] = []

    archetypes = read_csv(DATA_DIR / "archetypes_top50.csv")
    decks = read_json(DATA_DIR / "representative_decks.json")
    explicit_entries = read_csv(DATA_DIR / "representative_deck_entries.csv")
    full_candidates = read_csv(DATA_DIR / "card_source_locators_top50_361.csv")
    core_candidates = read_csv(DATA_DIR / "card_source_locators_top10_145.csv")
    membership = read_csv(DATA_DIR / "card_locator_archetype_membership.csv")

    if len(archetypes) != EXPECTED["archetypes"]:
        error(errors, f"Expected 50 archetypes; found {len(archetypes)}")
    if len(decks) != EXPECTED["archetypes"]:
        error(errors, f"Expected 50 representative decks; found {len(decks)}")

    ranks = sorted(int(row["rank"]) for row in archetypes)
    if ranks != list(range(1, 51)):
        error(errors, f"Archetype ranks are not exactly 1..50: {ranks}")

    archetype_names = [row["archetype"] for row in archetypes]
    if len(set(archetype_names)) != len(archetype_names):
        error(errors, "Duplicate archetype names in archetypes_top50.csv")

    combined_entries = sum(int(row["combined_entries"]) for row in archetypes)
    top10_entries = sum(
        int(row["combined_entries"]) for row in archetypes if int(row["rank"]) <= 10
    )
    if combined_entries != EXPECTED["top50_named_combined_entries"]:
        error(errors, f"Expected combined top-50 named entries 5688; found {combined_entries}")
    if top10_entries != EXPECTED["top10_combined_entries"]:
        error(errors, f"Expected top-10 entries 4194; found {top10_entries}")

    expected_share = combined_entries / EXPECTED["classified_entries_total"]
    actual_last_cumulative = float(archetypes[-1]["cumulative_field_share"])
    if not math.isclose(actual_last_cumulative, expected_share, rel_tol=0, abs_tol=1e-12):
        error(
            errors,
            f"Rank-50 cumulative share {actual_last_cumulative} != {expected_share}",
        )

    decoded_rows: list[dict[str, object]] = []
    per_deck_totals: dict[int, int] = {}
    for deck in decks:
        rank = int(deck["rank"])
        builder = deck.get("limitless_builder_encoding") or deck.get("builder")
        if not builder:
            error(errors, f"Rank {rank} has no builder encoding")
            continue
        try:
            decoded = list(decode_builder(builder))
        except Exception as exc:  # validation should report all failures
            error(errors, f"Could not decode rank {rank}: {exc}")
            continue
        total = sum(quantity for quantity, _, _ in decoded)
        per_deck_totals[rank] = total
        if total != 60:
            error(errors, f"Rank {rank} {deck['archetype']!r} totals {total}, not 60")
        frozen_cards = [
            (int(card["quantity"]), str(card["set_code"]), str(card["collector_number"]))
            for card in deck.get("cards", [])
        ]
        if decoded != frozen_cards:
            error(errors, f"Builder/card-array mismatch at rank {rank} ({deck['archetype']})")
        for quantity, set_code, number in decoded:
            decoded_rows.append(
                {
                    "rank": rank,
                    "archetype": deck["archetype"],
                    "quantity": quantity,
                    "set_code": set_code,
                    "collector_number": number,
                    "raw_locator": f"{set_code}-{number}",
                    "top10": rank <= 10,
                }
            )

    if len(decoded_rows) != EXPECTED["deck_lines"]:
        error(errors, f"Expected 1305 decoded deck lines; found {len(decoded_rows)}")
    if len(explicit_entries) != len(decoded_rows):
        error(
            errors,
            f"representative_deck_entries.csv has {len(explicit_entries)} rows; decoded {len(decoded_rows)}",
        )

    explicit_signature = Counter(
        (
            int(row["rank"]),
            row["archetype"],
            int(row["quantity"]),
            row["set_code"],
            str(row["collector_number"]),
        )
        for row in explicit_entries
    )
    decoded_signature = Counter(
        (
            int(row["rank"]),
            str(row["archetype"]),
            int(row["quantity"]),
            str(row["set_code"]),
            str(row["collector_number"]),
        )
        for row in decoded_rows
    )
    if explicit_signature != decoded_signature:
        error(errors, "Explicit representative-deck CSV differs from decoded builders")

    top50_set = {row["raw_locator"] for row in decoded_rows}
    top10_set = {row["raw_locator"] for row in decoded_rows if bool(row["top10"])}
    if len(top50_set) != EXPECTED["top50_raw_locators"]:
        error(errors, f"Expected 361 top-50 locators; found {len(top50_set)}")
    if len(top10_set) != EXPECTED["top10_raw_locators"]:
        error(errors, f"Expected 145 top-10 locators; found {len(top10_set)}")
    if not top10_set <= top50_set:
        error(errors, "Top-10 locator set is not a subset of top-50 locator set")

    file_full_set = {row["raw_locator"] for row in full_candidates}
    file_core_set = {row["raw_locator"] for row in core_candidates}
    if file_full_set != top50_set:
        error(errors, "card_source_locators_top50_361.csv does not equal decoded union")
    if file_core_set != top10_set:
        error(errors, "card_source_locators_top10_145.csv does not equal decoded top-10 union")

    membership_signature = Counter(
        (
            int(row["rank"]),
            row["archetype"],
            int(row["quantity"]),
            row["raw_locator"],
        )
        for row in membership
    )
    decoded_membership_signature = Counter(
        (
            int(row["rank"]),
            str(row["archetype"]),
            int(row["quantity"]),
            str(row["raw_locator"]),
        )
        for row in decoded_rows
    )
    if membership_signature != decoded_membership_signature:
        error(errors, "card_locator_archetype_membership.csv differs from decoded decks")

    # Validate tag propagation at the printing-locator layer.
    tags_by_locator: dict[str, set[str]] = defaultdict(set)
    for row in membership:
        tags_by_locator[row["raw_locator"]].add(row["archetype_tag"])
        tags_by_locator[row["raw_locator"]].add(row["meta_tag_top50"])
        if parse_bool(row["top10"]):
            tags_by_locator[row["raw_locator"]].add(row["meta_tag_top10"])
    for row in full_candidates:
        actual = set(row["anki_tags"].split())
        expected = tags_by_locator[row["raw_locator"]]
        if actual != expected:
            error(errors, f"Tag mismatch for {row['raw_locator']}")

    report = {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "observed": {
            "archetypes": len(archetypes),
            "representative_decks": len(decks),
            "deck_lines": len(decoded_rows),
            "top10_raw_locators": len(top10_set),
            "top50_raw_locators": len(top50_set),
            "top10_combined_entries": top10_entries,
            "top50_named_combined_entries": combined_entries,
            "top10_share_of_classified_pool": top10_entries
            / EXPECTED["classified_entries_total"],
            "top50_named_share_of_classified_pool": combined_entries
            / EXPECTED["classified_entries_total"],
            "all_decks_are_60_cards": all(value == 60 for value in per_deck_totals.values()),
        },
        "expected": EXPECTED,
    }
    write_json(args.report, report)

    if errors:
        print("Source validation FAILED", file=sys.stderr)
        for message in errors:
            print(f"- {message}", file=sys.stderr)
        print(f"Report: {args.report}", file=sys.stderr)
        raise SystemExit(1)

    print("Source validation passed")
    print(json.dumps(report["observed"], indent=2))
    print(f"Report: {args.report}")


if __name__ == "__main__":
    main()
