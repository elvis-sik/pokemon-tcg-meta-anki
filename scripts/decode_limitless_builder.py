#!/usr/bin/env python3
"""Decode Limitless deck-builder strings into explicit set/number rows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterator

from common import DATA_DIR, GENERATED_DIR, read_json, write_csv


def base36(char: str) -> int:
    try:
        return int(char, 36)
    except ValueError as exc:
        raise ValueError(f"Invalid base-36 character {char!r}") from exc


def decode_builder(builder: str) -> Iterator[tuple[int, str, str]]:
    if not builder or builder[0] != "1":
        raise ValueError("Unsupported Limitless builder format: expected leading version '1'")
    index = 1
    while index < len(builder):
        if builder[index] != "0":
            raise ValueError(f"Malformed builder string at offset {index}: expected row marker '0'")
        if index + 3 >= len(builder):
            raise ValueError("Truncated builder row header")
        quantity = base36(builder[index + 1])
        set_length = base36(builder[index + 2])
        number_length = base36(builder[index + 3])
        cursor = index + 4
        set_code = builder[cursor : cursor + set_length]
        cursor += set_length
        collector_number = builder[cursor : cursor + number_length]
        cursor += number_length
        if len(set_code) != set_length or len(collector_number) != number_length:
            raise ValueError("Truncated builder row body")
        yield quantity, set_code, collector_number
        index = cursor


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=DATA_DIR / "representative_decks.json",
        help="Frozen representative-deck JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=GENERATED_DIR / "representative_deck_entries_decoded.csv",
    )
    args = parser.parse_args()

    decks = read_json(args.input)
    if isinstance(decks, dict):
        decks = decks.get("decks", [])
    rows = []
    for deck in decks:
        rank = int(deck["rank"])
        builder = deck.get("limitless_builder_encoding") or deck.get("builder")
        if not builder:
            raise ValueError(f"Deck rank {rank} has no builder encoding")
        for quantity, set_code, collector_number in decode_builder(builder):
            rows.append(
                {
                    "rank": rank,
                    "archetype": deck["archetype"],
                    "representative_player": deck.get("representative_player", ""),
                    "quantity": quantity,
                    "set_code": set_code,
                    "collector_number": collector_number,
                    "raw_locator": f"{set_code}-{collector_number}",
                    "top10": rank <= 10,
                }
            )

    write_csv(
        args.output,
        rows,
        [
            "rank",
            "archetype",
            "representative_player",
            "quantity",
            "set_code",
            "collector_number",
            "raw_locator",
            "top10",
        ],
    )
    print(f"Decoded {len(decks)} decks and {len(rows)} deck lines to {args.output}")


if __name__ == "__main__":
    main()
