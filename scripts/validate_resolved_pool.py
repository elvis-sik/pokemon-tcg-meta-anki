#!/usr/bin/env python3
"""Validate the mechanically collapsed card roster before media/Anki build."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from common import DATA_DIR, GENERATED_DIR, REPORTS_DIR, read_csv, read_jsonl, write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input", type=Path, default=GENERATED_DIR / "mechanical_cards.jsonl"
    )
    parser.add_argument(
        "--report", type=Path, default=REPORTS_DIR / "resolved_pool_validation.json"
    )
    parser.add_argument("--allow-provisional-keys", action="store_true")
    parser.add_argument("--allow-missing-printing-universe", action="store_true")
    args = parser.parse_args()

    cards = read_jsonl(args.input)
    errors: list[str] = []
    warnings: list[str] = []
    if not cards:
        errors.append(f"No cards in {args.input}")

    keys = [str(card.get("card_key") or "") for card in cards]
    fingerprints = [str(card.get("mechanical_fingerprint") or "") for card in cards]
    duplicate_keys = [key for key, count in Counter(keys).items() if key and count > 1]
    duplicate_fingerprints = [
        key for key, count in Counter(fingerprints).items() if key and count > 1
    ]
    if duplicate_keys:
        errors.append(f"Duplicate CardKey values: {duplicate_keys[:20]}")
    if duplicate_fingerprints:
        warnings.append(
            "Duplicate final fingerprints remain; this can be intentional after manual grouping: "
            + ", ".join(duplicate_fingerprints[:20])
        )

    all_source_locators: set[str] = set()
    top10_source_locators: set[str] = set()
    provisional: list[str] = []
    ambiguous_without_qualifier: list[str] = []
    excessive_attacks: list[str] = []
    excessive_abilities: list[str] = []
    missing_archetype_tags: list[str] = []
    missing_images: list[str] = []

    for card in cards:
        key = str(card.get("card_key") or "")
        if not key:
            errors.append("A mechanical card has an empty CardKey")
            continue
        if "TCGDEX:" in key:
            provisional.append(key)
        source_locators = set(card.get("source_locators") or [])
        all_source_locators |= source_locators
        if card.get("top10"):
            top10_source_locators |= source_locators
        tags = set(card.get("tags") or [])
        if "ptcg::meta::2026_06::top50" not in tags:
            errors.append(f"{key}: missing top50 tag")
        if card.get("top10") and "ptcg::meta::2026_06::top10" not in tags:
            errors.append(f"{key}: top10 boolean set but top10 tag missing")
        for archetype in card.get("archetypes") or []:
            normalized = re.sub(r"[^a-z0-9]+", "_", archetype.casefold()).strip("_")
            if f"ptcg::archetype::{normalized}" not in tags:
                missing_archetype_tags.append(f"{key} -> {archetype}")

        mechanics = card.get("normalized_mechanics") or {}
        attacks = mechanics.get("attacks") or []
        abilities = mechanics.get("abilities") or []
        if len(attacks) > 4:
            excessive_attacks.append(f"{key}: {len(attacks)}")
        if len(abilities) > 3:
            excessive_abilities.append(f"{key}: {len(abilities)}")

        same_name_count = card.get("standard_same_name_mechanical_identity_count")
        label = str(card.get("display_label") or "")
        if isinstance(same_name_count, int) and same_name_count > 1 and " · " not in label:
            ambiguous_without_qualifier.append(key)
        display = card.get("display_printing") or {}
        if not display.get("image_url"):
            missing_images.append(key)

    expected_full = {
        row["raw_locator"]
        for row in read_csv(DATA_DIR / "card_source_locators_top50_361.csv")
    }
    expected_core = {
        row["raw_locator"]
        for row in read_csv(DATA_DIR / "card_source_locators_top10_145.csv")
    }
    if all_source_locators != expected_full:
        missing = sorted(expected_full - all_source_locators)
        extra = sorted(all_source_locators - expected_full)
        errors.append(f"Source-locator union mismatch; missing={missing[:20]} extra={extra[:20]}")
    if top10_source_locators != expected_core:
        missing = sorted(expected_core - top10_source_locators)
        extra = sorted(top10_source_locators - expected_core)
        errors.append(f"Top10 source-locator propagation mismatch; missing={missing[:20]} extra={extra[:20]}")
    if provisional and not args.allow_provisional_keys:
        errors.append(f"{len(provisional)} provisional TCGDEX CardKeys remain")
    if ambiguous_without_qualifier:
        errors.append(
            "Ambiguous same-name cards with an unqualified display label: "
            + ", ".join(ambiguous_without_qualifier[:20])
        )
    if excessive_attacks:
        errors.append("More than four attacks: " + ", ".join(excessive_attacks))
    if excessive_abilities:
        errors.append("More than three abilities: " + ", ".join(excessive_abilities))
    if missing_archetype_tags:
        errors.append("Missing archetype tags: " + ", ".join(missing_archetype_tags[:20]))
    if missing_images:
        warnings.append(f"{len(missing_images)} cards lack a display image URL")

    if cards and all(
        card.get("standard_same_name_mechanical_identity_count", 0) == 0 for card in cards
    ) and not args.allow_missing_printing_universe:
        errors.append(
            "No Standard ambiguity counts were populated; run discover_printings_tcgdex.py first"
        )

    report: dict[str, Any] = {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "counts": {
            "mechanical_cards": len(cards),
            "top10_mechanical_cards": sum(1 for card in cards if card.get("top10")),
            "top50_source_locators_covered": len(all_source_locators),
            "top10_source_locators_covered": len(top10_source_locators),
            "provisional_keys": len(provisional),
            "missing_display_images": len(missing_images),
        },
    }
    write_json(args.report, report)
    if errors:
        print("Resolved-pool validation FAILED", file=sys.stderr)
        for item in errors:
            print(f"- {item}", file=sys.stderr)
        raise SystemExit(1)
    print("Resolved-pool validation passed")
    print(json.dumps(report["counts"], indent=2))


if __name__ == "__main__":
    main()
