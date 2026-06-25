#!/usr/bin/env python3
"""Create artwork-only recognition cues from downloaded full-card images.

Cropping is intentionally auditable. Defaults are layout heuristics; manual
fractions in data/art_crop_overrides.csv take precedence. The contact sheet is
a required human-review surface before package generation.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps

from common import DATA_DIR, GENERATED_DIR, MEDIA_DIR, REPORTS_DIR, read_csv, read_json, read_jsonl, write_csv, write_json

DEFAULT_PROFILES: dict[str, tuple[float, float, float, float]] = {
    "Pokemon": (0.075, 0.105, 0.850, 0.405),
    "Trainer": (0.075, 0.105, 0.850, 0.455),
    "Energy": (0.075, 0.105, 0.850, 0.455),
}


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def crop_box(
    image: Image.Image, profile: tuple[float, float, float, float]
) -> tuple[int, int, int, int]:
    x, y, width, height = profile
    x = clamp(x, 0.0, 0.99)
    y = clamp(y, 0.0, 0.99)
    width = clamp(width, 0.01, 1.0 - x)
    height = clamp(height, 0.01, 1.0 - y)
    left = round(image.width * x)
    top = round(image.height * y)
    right = round(image.width * (x + width))
    bottom = round(image.height * (y + height))
    return left, top, max(left + 1, right), max(top + 1, bottom)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cards", type=Path, default=GENERATED_DIR / "mechanical_cards.jsonl"
    )
    parser.add_argument(
        "--manifest", type=Path, default=GENERATED_DIR / "media_manifest.json"
    )
    parser.add_argument(
        "--overrides", type=Path, default=DATA_DIR / "art_crop_overrides.csv"
    )
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--thumb-width", type=int, default=180)
    args = parser.parse_args()

    cards = read_jsonl(args.cards)
    manifest = read_json(args.manifest)
    by_key = {str(card["card_key"]): card for card in cards}
    overrides: dict[str, tuple[float, float, float, float]] = {}
    for row in read_csv(args.overrides):
        if not row.get("card_key"):
            continue
        overrides[row["card_key"]] = tuple(
            float(row[name])
            for name in ("x_fraction", "y_fraction", "width_fraction", "height_fraction")
        )  # type: ignore[assignment]

    failures: list[dict[str, str]] = []
    audit: list[dict[str, Any]] = []
    thumbnails: list[tuple[str, Image.Image]] = []

    for key, entry in manifest.get("cards", {}).items():
        card = by_key.get(key)
        if not card:
            failures.append({"card_key": key, "reason": "not in mechanical card data"})
            continue
        full_name = str(entry.get("full_card_filename") or "")
        art_name = str(entry.get("artwork_filename") or "")
        if not full_name or not art_name:
            failures.append({"card_key": key, "reason": "media manifest missing filename"})
            continue
        full_path = MEDIA_DIR / full_name
        art_path = MEDIA_DIR / art_name
        profile = overrides.get(key) or DEFAULT_PROFILES.get(str(card.get("category")), DEFAULT_PROFILES["Pokemon"])
        profile_source = "manual" if key in overrides else f"default_{card.get('category')}"
        try:
            with Image.open(full_path) as source:
                source = source.convert("RGB")
                box = crop_box(source, profile)
                art = source.crop(box)
                art.save(art_path, format="PNG", optimize=True)
                thumb_height = round(args.thumb_width * art.height / art.width)
                thumb = ImageOps.fit(art, (args.thumb_width, thumb_height), method=Image.Resampling.LANCZOS)
                thumbnails.append((str(card.get("display_label") or key), thumb.copy()))
            entry["crop_profile"] = list(profile)
            entry["crop_profile_source"] = profile_source
            entry["crop_status"] = "created"
            audit.append(
                {
                    "card_key": key,
                    "category": card.get("category", ""),
                    "profile_source": profile_source,
                    "x_fraction": profile[0],
                    "y_fraction": profile[1],
                    "width_fraction": profile[2],
                    "height_fraction": profile[3],
                    "artwork_filename": art_name,
                }
            )
        except Exception as exc:
            entry["crop_status"] = "failed"
            failures.append({"card_key": key, "reason": str(exc)})

    # Contact sheet: compact, neutral validation artifact.
    if thumbnails:
        columns = 5
        label_height = 42
        cell_width = args.thumb_width + 18
        max_thumb_height = max(image.height for _, image in thumbnails)
        cell_height = max_thumb_height + label_height + 18
        rows = math.ceil(len(thumbnails) / columns)
        sheet = Image.new("RGB", (columns * cell_width, rows * cell_height), "white")
        draw = ImageDraw.Draw(sheet)
        font = ImageFont.load_default()
        for index, (label, image) in enumerate(thumbnails):
            row, column = divmod(index, columns)
            x = column * cell_width + 9
            y = row * cell_height + 9
            sheet.paste(image, (x, y))
            text = label if len(label) <= 27 else label[:26] + "…"
            draw.multiline_text((x, y + max_thumb_height + 4), text, font=font, fill="black", spacing=2)
        contact_path = REPORTS_DIR / "artwork_crop_contact_sheet.jpg"
        sheet.save(contact_path, format="JPEG", quality=88, optimize=True)

    write_json(args.manifest, manifest)
    write_csv(
        REPORTS_DIR / "artwork_crop_audit.csv",
        audit,
        [
            "card_key",
            "category",
            "profile_source",
            "x_fraction",
            "y_fraction",
            "width_fraction",
            "height_fraction",
            "artwork_filename",
        ],
    )
    write_csv(REPORTS_DIR / "artwork_crop_failures.csv", failures, ["card_key", "reason"])
    summary = {
        "card_count": len(cards),
        "crop_count": len(audit),
        "manual_override_count": sum(1 for row in audit if row["profile_source"] == "manual"),
        "failure_count": len(failures),
        "contact_sheet": str(REPORTS_DIR / "artwork_crop_contact_sheet.jpg"),
    }
    write_json(REPORTS_DIR / "artwork_crop_summary.json", summary)
    print(json.dumps(summary, indent=2))
    if failures and not args.continue_on_error:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
