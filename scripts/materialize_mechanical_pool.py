#!/usr/bin/env python3
"""Collapse resolved printings into mechanically distinct study notes."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from common import (
    DATA_DIR,
    GENERATED_DIR,
    REPORTS_DIR,
    mechanical_fingerprint,
    compute_display_label,
    natural_card_key,
    normalized_mechanics,
    parse_bool,
    parse_iso_date,
    read_csv,
    read_jsonl,
    release_sort_key,
    slugify,
    utc_now_iso,
    write_csv,
    write_json,
    write_jsonl,
)

CURRENT_STANDARD_MARKS = {"H", "I", "J"}
LIMITLESS_IMAGE_ASSET_ROOT = "https://limitlesstcg.nyc3.cdn.digitaloceanspaces.com/tpci"


def legal_in_current_standard(printing: dict[str, Any]) -> bool:
    if printing.get("standard_legal") is True:
        return True
    return str(printing.get("regulation_mark") or "") in CURRENT_STANDARD_MARKS


def regular_printing_score(printing: dict[str, Any]) -> int:
    payload = printing.get("raw_payload") or {}
    variants = payload.get("variants")
    if isinstance(variants, dict):
        if variants.get("normal") is True:
            return 3
        if variants.get("holo") is True:
            return 2
    # TCGdex's newer source format may use an array of variant objects.
    if isinstance(variants, list):
        kinds = {str(item.get("type", "")).casefold() for item in variants if isinstance(item, dict)}
        if "normal" in kinds:
            return 3
        if "holo" in kinds:
            return 2
    return 1


def set_code_from_payload(printing: dict[str, Any]) -> str:
    set_payload = printing.get("set_payload") if isinstance(printing.get("set_payload"), dict) else {}
    abbreviation = set_payload.get("abbreviation") if isinstance(set_payload, dict) else {}
    if isinstance(abbreviation, dict):
        code = str(abbreviation.get("official") or "").strip()
        if code:
            return code
    return str(set_payload.get("tcgOnline") or "").strip()


def limitless_card_image_url(set_code: str, collector_number: str) -> str:
    code = str(set_code or "").strip().upper()
    number = str(collector_number or "").strip()
    if not code or not number:
        return ""
    if not re.fullmatch(r"[A-Z0-9]+", code):
        return ""
    if re.fullmatch(r"\d+", number):
        number = number.zfill(3)
    else:
        number = number.upper()
    if not re.fullmatch(r"[A-Z0-9]+", number):
        return ""
    return f"{LIMITLESS_IMAGE_ASSET_ROOT}/{code}/{code}_{number}_R_EN.png"


def printing_locator(printing: dict[str, Any], set_id_to_code: dict[str, str]) -> tuple[str, str]:
    code = str(printing.get("set_code") or "")
    if not code:
        code = set_id_to_code.get(str(printing.get("tcgdex_set_id") or ""), "")
    if not code:
        code = set_code_from_payload(printing)
    number = str(
        printing.get("collector_number")
        or (printing.get("raw_payload") or {}).get("localId")
        or ""
    )
    return code, number


def image_url_for_printing(printing: dict[str, Any], set_id_to_code: dict[str, str]) -> str:
    code, number = printing_locator(printing, set_id_to_code)
    return str(
        printing.get("image_url")
        or (printing.get("raw_payload") or {}).get("image")
        or limitless_card_image_url(code, number)
    )


def apply_merge_overrides(
    source: list[dict[str, Any]], overrides: dict[str, str]
) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in source:
        fingerprint = mechanical_fingerprint(record["raw_payload"])
        key = overrides.get(record["raw_locator"]) or fingerprint
        groups[key].append({**record, "mechanical_fingerprint": fingerprint})
    return groups


def choose_origin(
    printings: list[dict[str, Any]], set_id_to_code: dict[str, str]
) -> tuple[dict[str, Any], bool]:
    origin = min(printings, key=release_sort_key)
    code, number = printing_locator(origin, set_id_to_code)
    return origin, bool(code and number)


def choose_display(
    printings: list[dict[str, Any]], set_id_to_code: dict[str, str]
) -> dict[str, Any]:
    legal = [item for item in printings if legal_in_current_standard(item)]
    candidates = legal or printings
    # Newest set, then regular-art preference within it, then lowest local ID.
    latest_date = max((parse_iso_date(item.get("release_date")) or date.min for item in candidates))
    latest = [
        item
        for item in candidates
        if (parse_iso_date(item.get("release_date")) or date.min) == latest_date
    ]
    latest.sort(
        key=lambda item: (
            -regular_printing_score(item),
            release_sort_key(item)[1],
            str(item.get("tcgdex_card_id") or ""),
        )
    )
    return latest[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--resolved", type=Path, default=GENERATED_DIR / "resolved_source_cards.jsonl"
    )
    parser.add_argument(
        "--printing-universe",
        type=Path,
        default=GENERATED_DIR / "printing_universe.jsonl",
    )
    parser.add_argument(
        "--output", type=Path, default=GENERATED_DIR / "mechanical_cards.jsonl"
    )
    parser.add_argument("--allow-provisional-keys", action="store_true")
    args = parser.parse_args()

    source = read_jsonl(args.resolved)
    if not source:
        raise SystemExit(f"No resolved source cards at {args.resolved}")
    universe = read_jsonl(args.printing_universe)

    merge_overrides = {
        row["raw_locator"]: row["mechanical_group_override"]
        for row in read_csv(DATA_DIR / "manual_mechanical_merge_overrides.csv")
        if row.get("raw_locator") and row.get("mechanical_group_override")
    }
    label_overrides_by_key = {
        row["mechanical_card_key"]: row["display_label_override"]
        for row in read_csv(DATA_DIR / "display_label_overrides.csv")
        if row.get("mechanical_card_key") and row.get("display_label_override")
    }
    role_overrides_by_key = {
        row["mechanical_card_key"]: row["competitive_role"]
        for row in read_csv(DATA_DIR / "competitive_role_overrides.csv")
        if row.get("mechanical_card_key") and row.get("competitive_role")
    }
    rulings_overrides_by_key = {
        row["mechanical_card_key"]: row["rulings_html"]
        for row in read_csv(DATA_DIR / "rulings_overrides.csv")
        if row.get("mechanical_card_key") and row.get("rulings_html")
    }
    registry_rows = read_csv(DATA_DIR / "natural_key_registry.csv")
    registry_by_fingerprint = {
        row.get("mechanical_fingerprint", ""): row["mechanical_card_key"]
        for row in registry_rows
        if row.get("mechanical_fingerprint") and row.get("mechanical_card_key")
    }

    set_id_to_code: dict[str, str] = {}
    resolved_catalog = GENERATED_DIR / "set_catalog_resolved.csv"
    if resolved_catalog.exists():
        for row in read_csv(resolved_catalog):
            if row.get("tcgdex_set_id") and row.get("limitless_code"):
                set_id_to_code[row["tcgdex_set_id"]] = row["limitless_code"]
    # Source records are authoritative for current Limitless set-code mappings.
    for record in source:
        if record.get("tcgdex_set_id") and record.get("set_code"):
            set_id_to_code[str(record["tcgdex_set_id"])] = str(record["set_code"])
    # Earlier English reprints may predate the current set catalog. Keep their
    # player-facing codes in a durable, auditable crosswalk.
    for row in read_csv(DATA_DIR / "set_code_overrides.csv"):
        if row.get("tcgdex_set_id") and row.get("limitless_code"):
            set_id_to_code[row["tcgdex_set_id"]] = row["limitless_code"]

    source_groups = apply_merge_overrides(source, merge_overrides)
    universe_by_fingerprint: dict[str, list[dict[str, Any]]] = defaultdict(list)
    fingerprints_by_name: dict[str, set[str]] = defaultdict(set)
    legal_fingerprints_by_name: dict[str, set[str]] = defaultdict(set)
    for printing in universe:
        inferred_code = set_code_from_payload(printing)
        if inferred_code and printing.get("tcgdex_set_id"):
            set_id_to_code.setdefault(str(printing["tcgdex_set_id"]), inferred_code)
        fingerprint = printing.get("mechanical_fingerprint")
        if not fingerprint:
            fingerprint = mechanical_fingerprint(printing["raw_payload"])
            printing["mechanical_fingerprint"] = fingerprint
        universe_by_fingerprint[fingerprint].append(printing)
        name = str(printing["name"])
        fingerprints_by_name[name].add(fingerprint)
        if legal_in_current_standard(printing):
            legal_fingerprints_by_name[name].add(fingerprint)

    mechanical_cards: list[dict[str, Any]] = []
    roster_rows: list[dict[str, Any]] = []
    membership_rows: list[dict[str, Any]] = []
    merge_rows: list[dict[str, Any]] = []
    provisional_keys: list[str] = []

    for group_key, records in source_groups.items():
        fingerprints = {record["mechanical_fingerprint"] for record in records}
        # A manual group may intentionally join provider fingerprints.
        representative = records[0]
        mechanics = normalized_mechanics(representative["raw_payload"])
        final_fingerprint = (
            next(iter(fingerprints))
            if len(fingerprints) == 1
            else __import__("hashlib").sha256(
                ("manual-merge:" + ":".join(sorted(fingerprints))).encode("utf-8")
            ).hexdigest()
        )
        name = mechanics["name"]
        category = mechanics["category"]

        all_printings: list[dict[str, Any]] = []
        seen_printing_ids: set[str] = set()
        for fingerprint in fingerprints:
            for printing in universe_by_fingerprint.get(fingerprint, []):
                pid = str(printing.get("tcgdex_card_id") or printing.get("raw_locator") or "")
                if pid not in seen_printing_ids:
                    all_printings.append(printing)
                    seen_printing_ids.add(pid)
        for record in records:
            pid = str(record.get("tcgdex_card_id") or record["raw_locator"])
            if pid not in seen_printing_ids:
                all_printings.append(
                    {
                        **record,
                        "regulation_mark": (record.get("raw_payload") or {}).get("regulationMark"),
                        "image_url": (record.get("raw_payload") or {}).get("image"),
                    }
                )
                seen_printing_ids.add(pid)

        origin, origin_has_player_code = choose_origin(all_printings, set_id_to_code)
        display = choose_display(all_printings, set_id_to_code)
        origin_code, origin_number = printing_locator(origin, set_id_to_code)
        display_code, display_number = printing_locator(display, set_id_to_code)

        registered_key = registry_by_fingerprint.get(final_fingerprint)
        if registered_key:
            card_key = registered_key
        elif origin_has_player_code:
            card_key = natural_card_key(name, origin_code, origin_number)
        else:
            fallback_code = str(origin.get("tcgdex_set_id") or origin.get("set_code") or "UNKNOWN")
            card_key = f"{name} · TCGDEX:{fallback_code} {origin_number or '?'}"
            provisional_keys.append(card_key)

        legal_name_count = len(legal_fingerprints_by_name.get(name, set()))
        if not universe:
            # Safe fallback: only shorten when the complete Standard ambiguity
            # universe has been supplied. Otherwise always qualify.
            legal_name_count = 0
        label_override = label_overrides_by_key.get(card_key, "")
        auto_label = compute_display_label(
            name=name,
            standard_mechanical_identity_count=legal_name_count,
            display_set_code=display_code,
            display_collector_number=display_number,
        )
        final_label = compute_display_label(
            name=name,
            standard_mechanical_identity_count=legal_name_count,
            display_set_code=display_code,
            display_collector_number=display_number,
            override=label_override,
        )

        archetypes = sorted(
            {archetype for record in records for archetype in record.get("source_archetypes", [])}
        )
        source_tags = sorted(
            {tag for record in records for tag in record.get("source_tags", []) if tag}
        )
        top10 = any(bool(record.get("source_top10")) for record in records)
        tags = set(source_tags)
        tags.add(f"ptcg::card_type::{category.casefold()}")
        rules_blob = " ".join(mechanics.get("rules") or []).casefold()
        name_blob = name.casefold()
        suffix_blob = str(mechanics.get("suffix") or "").casefold()
        if name_blob.endswith(" ex"):
            tags.add("ptcg::mechanic::ex")
        if "mega evolution" in name_blob or "mega evolution" in rules_blob:
            tags.add("ptcg::mechanic::mega_evolution_ex")
        if "tera" in rules_blob or suffix_blob == "tera":
            tags.add("ptcg::mechanic::tera")
        if "ace spec" in rules_blob:
            tags.add("ptcg::mechanic::ace_spec")
        tags.add("ptcg::meta::2026_06::top50")
        if top10:
            tags.add("ptcg::meta::2026_06::top10")

        mechanical = {
            "mechanical_fingerprint": final_fingerprint,
            "provider_fingerprints": sorted(fingerprints),
            "card_key": card_key,
            "name": name,
            "category": category,
            "normalized_mechanics": mechanics,
            "source_locators": sorted(record["raw_locator"] for record in records),
            "all_known_english_printings": [
                {
                    "tcgdex_card_id": item.get("tcgdex_card_id") or item.get("id"),
                    "tcgdex_set_id": item.get("tcgdex_set_id"),
                    "set_code": printing_locator(item, set_id_to_code)[0],
                    "collector_number": printing_locator(item, set_id_to_code)[1],
                    "release_date": item.get("release_date"),
                    "standard_legal": item.get("standard_legal"),
                    "regulation_mark": item.get("regulation_mark")
                    or (item.get("raw_payload") or {}).get("regulationMark"),
                    "image_url": image_url_for_printing(item, set_id_to_code),
                }
                for item in sorted(all_printings, key=release_sort_key)
            ],
            "origin_printing": {
                "tcgdex_card_id": origin.get("tcgdex_card_id"),
                "tcgdex_set_id": origin.get("tcgdex_set_id"),
                "set_code": origin_code,
                "collector_number": origin_number,
                "release_date": origin.get("release_date"),
                "mapping_complete": origin_has_player_code,
            },
            "display_printing": {
                "tcgdex_card_id": display.get("tcgdex_card_id"),
                "tcgdex_set_id": display.get("tcgdex_set_id"),
                "set_code": display_code,
                "collector_number": display_number,
                "release_date": display.get("release_date"),
                "image_url": image_url_for_printing(display, set_id_to_code),
            },
            "auto_display_label": auto_label,
            "display_label_override": label_override,
            "display_label": final_label,
            "standard_same_name_mechanical_identity_count": legal_name_count,
            "archetypes": archetypes,
            "tags": sorted(tags),
            "top10": top10,
            "top50": True,
            "competitive_role": role_overrides_by_key.get(card_key, ""),
            "rulings": rulings_overrides_by_key.get(card_key, ""),
            "generated_at": utc_now_iso(),
        }
        mechanical_cards.append(mechanical)

        roster_rows.append(
            {
                "card_key": card_key,
                "display_label": mechanical["display_label"],
                "name": name,
                "category": category,
                "top10_core": top10,
                "top50": True,
                "source_locator_count": len(records),
                "source_locators": " | ".join(mechanical["source_locators"]),
                "archetype_count": len(archetypes),
                "archetypes": " | ".join(archetypes),
                "anki_tags": " ".join(mechanical["tags"]),
            }
        )
        for archetype in archetypes:
            membership_rows.append(
                {
                    "card_key": card_key,
                    "name": name,
                    "archetype": archetype,
                    "archetype_tag": f"ptcg::archetype::{slugify(archetype)}",
                    "top10_core": top10,
                }
            )
        if len(records) > 1:
            merge_rows.append(
                {
                    "card_key": card_key,
                    "name": name,
                    "source_locator_count": len(records),
                    "source_locators": " | ".join(mechanical["source_locators"]),
                    "provider_fingerprint_count": len(fingerprints),
                    "manual_merge": len(fingerprints) > 1,
                }
            )

    mechanical_cards.sort(key=lambda row: row["card_key"].casefold())
    roster_rows.sort(key=lambda row: str(row["card_key"]).casefold())
    membership_rows.sort(key=lambda row: (str(row["archetype"]), str(row["card_key"])))
    write_jsonl(args.output, mechanical_cards)
    write_csv(
        GENERATED_DIR / "mechanical_card_roster.csv",
        roster_rows,
        [
            "card_key",
            "display_label",
            "name",
            "category",
            "top10_core",
            "top50",
            "source_locator_count",
            "source_locators",
            "archetype_count",
            "archetypes",
            "anki_tags",
        ],
    )
    write_csv(
        GENERATED_DIR / "mechanical_card_archetype_membership.csv",
        membership_rows,
        ["card_key", "name", "archetype", "archetype_tag", "top10_core"],
    )
    write_csv(
        REPORTS_DIR / "mechanical_merges.csv",
        merge_rows,
        [
            "card_key",
            "name",
            "source_locator_count",
            "source_locators",
            "provider_fingerprint_count",
            "manual_merge",
        ],
    )

    summary = {
        "source_locator_count": len(source),
        "mechanical_card_count": len(mechanical_cards),
        "top10_mechanical_card_count": sum(1 for row in mechanical_cards if row["top10"]),
        "top50_mechanical_card_count": len(mechanical_cards),
        "merge_group_count": len(merge_rows),
        "provisional_key_count": len(provisional_keys),
        "provisional_keys": provisional_keys,
        "printing_universe_supplied": bool(universe),
    }
    write_json(REPORTS_DIR / "mechanical_pool_summary.json", summary)
    print(json.dumps({k: v for k, v in summary.items() if k != "provisional_keys"}, indent=2))

    if provisional_keys and not args.allow_provisional_keys:
        raise SystemExit(
            "Player-facing origin codes are missing for one or more earliest printings. "
            "Populate natural_key_registry.csv or the set-code mapping, then rerun; "
            "use --allow-provisional-keys only for debugging."
        )


if __name__ == "__main__":
    main()
