#!/usr/bin/env python3
"""Resolve the 361 frozen Limitless set/number locators through TCGdex.

This is a network-dependent step. It preserves the raw provider payload for
future auditing and does not perform mechanical merging.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from common import (
    DATA_DIR,
    GENERATED_DIR,
    REPORTS_DIR,
    card_category,
    card_name,
    normalize_for_match,
    parse_bool,
    read_csv,
    utc_now_iso,
    write_csv,
    write_json,
    write_jsonl,
)
from tcgdex_client import TCGdexClient, TCGdexError

SET_NAME_ALIASES: dict[str, list[str]] = {
    "SVP": ["SVP Black Star Promos", "Scarlet & Violet Black Star Promos"],
    "SVI": ["Scarlet & Violet"],
    "MEE": ["Mega Evolution Energy"],
}


def candidate_local_ids(set_code: str, number: str) -> list[str]:
    values: list[str] = [number]
    stripped = number.lstrip("0") or "0"
    if stripped not in values:
        values.append(stripped)
    if stripped.isdigit():
        for width in (2, 3, 4):
            padded = stripped.zfill(width)
            if padded not in values:
                values.append(padded)
    if set_code.endswith("P") or set_code in {"SVP", "MEP", "SWSHP", "XYP", "SMp"}:
        for prefix in (set_code, set_code.removesuffix("P")):
            candidate = f"{prefix}{stripped}"
            if candidate not in values:
                values.append(candidate)
    return values


def local_id_equivalent(a: str, b: str, set_code: str) -> bool:
    if a.casefold() == b.casefold():
        return True
    # For numeric and promo-style IDs, compare the trailing number.
    match_a = re.search(r"(\d+[A-Za-z]?)$", a)
    match_b = re.search(r"(\d+[A-Za-z]?)$", b)
    if not match_a or not match_b:
        return False
    tail_a = match_a.group(1).lstrip("0") or "0"
    tail_b = match_b.group(1).lstrip("0") or "0"
    return tail_a.casefold() == tail_b.casefold()


def resolve_set_ids(
    client: TCGdexClient, catalog: list[dict[str, str]]
) -> tuple[dict[str, str], dict[str, dict[str, Any]], list[str]]:
    available = client.list_sets()
    by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for brief in available:
        by_name[normalize_for_match(brief.get("name", ""))].append(brief)

    mapping: dict[str, str] = {}
    details: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for row in catalog:
        code = row["limitless_code"]
        explicit = row.get("tcgdex_set_id", "").strip()
        if explicit:
            set_id = explicit
        else:
            names = [row["full_name"], *SET_NAME_ALIASES.get(code, [])]
            matches: list[dict[str, Any]] = []
            for name in names:
                matches.extend(by_name.get(normalize_for_match(name), []))
            unique = {str(item.get("id")): item for item in matches if item.get("id")}
            if len(unique) != 1:
                errors.append(
                    f"Could not uniquely map {code} {row['full_name']!r}; matches={sorted(unique)}"
                )
                continue
            set_id = next(iter(unique))
        try:
            detail = client.get_set(set_id)
        except TCGdexError as exc:
            errors.append(f"Failed to fetch set {code}/{set_id}: {exc}")
            continue
        mapping[code] = set_id
        details[code] = detail
    return mapping, details, errors


def match_set_brief(
    set_detail: dict[str, Any], set_code: str, collector_number: str
) -> dict[str, Any] | None:
    cards = set_detail.get("cards") or []
    matches = []
    for brief in cards:
        if not isinstance(brief, dict):
            continue
        local_id = str(brief.get("localId") or brief.get("local_id") or "")
        if any(
            local_id_equivalent(local_id, candidate, set_code)
            for candidate in candidate_local_ids(set_code, collector_number)
        ):
            matches.append(brief)
    # Alternate-art entries may share trailing numbers in unusual promo sets;
    # require a unique card brief rather than silently choosing.
    unique = {str(item.get("id")): item for item in matches if item.get("id")}
    if len(unique) == 1:
        return next(iter(unique.values()))
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--candidates",
        type=Path,
        default=DATA_DIR / "card_source_locators_top50_361.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=GENERATED_DIR / "resolved_source_cards.jsonl",
    )
    parser.add_argument(
        "--unresolved",
        type=Path,
        default=REPORTS_DIR / "unresolved_source_locators.csv",
    )
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")
    args = parser.parse_args()

    candidate_rows = read_csv(args.candidates)
    catalog = read_csv(DATA_DIR / "set_catalog.csv")
    client = TCGdexClient(refresh=args.refresh)
    set_map, set_details, set_errors = resolve_set_ids(client, catalog)

    resolved: list[dict[str, Any]] = []
    unresolved: list[dict[str, str]] = []

    for index, row in enumerate(candidate_rows, 1):
        raw_locator = row["raw_locator"]
        set_code = row["set_code"]
        number = str(row["collector_number"])
        set_id = set_map.get(set_code)
        if not set_id:
            unresolved.append(
                {
                    "raw_locator": raw_locator,
                    "reason": "unmapped_set",
                    "details": "; ".join(set_errors),
                }
            )
            continue

        card: dict[str, Any] | None = None
        brief = match_set_brief(set_details[set_code], set_code, number)
        attempts: list[str] = []
        if brief and brief.get("id"):
            try:
                card = client.get_card(str(brief["id"]))
            except TCGdexError as exc:
                attempts.append(str(exc))

        if card is None:
            for local_id in candidate_local_ids(set_code, number):
                try:
                    card = client.get_set_card(set_id, local_id)
                    break
                except TCGdexError as exc:
                    attempts.append(str(exc))

        if card is None:
            unresolved.append(
                {
                    "raw_locator": raw_locator,
                    "reason": "card_not_found_or_ambiguous",
                    "details": " | ".join(attempts[-5:]),
                }
            )
            continue

        try:
            name = card_name(card)
            category = card_category(card)
        except Exception as exc:
            unresolved.append(
                {
                    "raw_locator": raw_locator,
                    "reason": "invalid_card_payload",
                    "details": str(exc),
                }
            )
            continue

        set_detail = set_details[set_code]
        release_date = set_detail.get("releaseDate") or set_detail.get("release_date")
        legal = card.get("legal") if isinstance(card.get("legal"), dict) else {}
        resolved.append(
            {
                "raw_locator": raw_locator,
                "set_code": set_code,
                "collector_number": number,
                "name": name,
                "category": category,
                "source_provider": "TCGdex",
                "source_url": f"https://api.tcgdex.net/v2/en/sets/{set_id}/{number}",
                "fetched_at": utc_now_iso(),
                "tcgdex_card_id": card.get("id"),
                "tcgdex_set_id": set_id,
                "release_date": release_date,
                "standard_legal": legal.get("standard"),
                "source_archetypes": [
                    item.strip() for item in row.get("archetypes", "").split("|") if item.strip()
                ],
                "source_archetype_ranks": [
                    int(item.strip())
                    for item in row.get("archetype_ranks", "").split("|")
                    if item.strip()
                ],
                "source_tags": row.get("anki_tags", "").split(),
                "source_top10": parse_bool(row.get("in_top10_raw_union")),
                "source_top50": True,
                "raw_payload": card,
            }
        )
        if index % 25 == 0:
            print(f"Resolved {index}/{len(candidate_rows)} source locators", file=sys.stderr)

    write_jsonl(args.output, resolved)
    write_csv(args.unresolved, unresolved, ["raw_locator", "reason", "details"])

    resolved_set_rows = []
    for row in catalog:
        code = row["limitless_code"]
        detail = set_details.get(code, {})
        counts = detail.get("cardCount") if isinstance(detail.get("cardCount"), dict) else {}
        resolved_set_rows.append(
            {
                **row,
                "tcgdex_set_id": set_map.get(code, row.get("tcgdex_set_id", "")),
                "release_date_iso": detail.get("releaseDate") or row.get("release_date_iso", ""),
                "printed_card_count": counts.get("official", ""),
                "total_card_count": counts.get("total", ""),
                "set_mark_asset_url": detail.get("symbol") or row.get("set_mark_asset_url", ""),
                "set_logo_asset_url": detail.get("logo") or row.get("set_logo_asset_url", ""),
            }
        )
    set_fields = list(resolved_set_rows[0]) if resolved_set_rows else []
    write_csv(GENERATED_DIR / "set_catalog_resolved.csv", resolved_set_rows, set_fields)

    summary = {
        "candidate_count": len(candidate_rows),
        "resolved_count": len(resolved),
        "unresolved_count": len(unresolved),
        "set_mapping_errors": set_errors,
        "output": str(args.output),
    }
    write_json(REPORTS_DIR / "resolution_summary.json", summary)
    print(json.dumps(summary, indent=2))

    if (unresolved or set_errors) and not args.continue_on_error:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
