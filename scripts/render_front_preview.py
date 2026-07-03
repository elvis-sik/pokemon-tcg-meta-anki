#!/usr/bin/env python3
"""Render selected front cards into a local HTML visual QA report."""

from __future__ import annotations

import argparse
import html
import re
from pathlib import Path
from typing import Any

from common import GENERATED_DIR, MEDIA_DIR, REPORTS_DIR, ROOT, TEMPLATES_DIR, read_json, read_jsonl


DEFAULT_KEYS = [
    "AZ's Tranquility · CRI 076",
    "Bug Catching Set · TWM 143",
    "Fighting Energy · BS 97",
    "Psychic Energy · BS 101",
    "Prism Energy · BLK 086",
    "Legacy Energy · TWM 167",
    "Beedrill ex · CRI 003",
    "Abra · MEG 054",
]


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def image_tag(filename: str) -> str:
    if not filename:
        return ""
    path = MEDIA_DIR / filename
    return f'<img src="{esc(path.as_uri())}" alt="">'


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cards", type=Path, default=GENERATED_DIR / "mechanical_cards.jsonl"
    )
    parser.add_argument(
        "--media", type=Path, default=GENERATED_DIR / "media_manifest.json"
    )
    parser.add_argument(
        "--output", type=Path, default=REPORTS_DIR / "front_preview.html"
    )
    parser.add_argument("--key", action="append", default=[])
    parser.add_argument("--category", action="append", default=[])
    parser.add_argument("--name-regex", default="")
    parser.add_argument("--max-cards", type=int, default=0)
    args = parser.parse_args()

    card_list = read_jsonl(args.cards)
    cards = {str(card["card_key"]): card for card in card_list}
    media = read_json(args.media)
    if args.key:
        keys = args.key
    elif args.category or args.name_regex:
        name_pattern = re.compile(args.name_regex) if args.name_regex else None
        categories = set(args.category)
        keys = [
            str(card["card_key"])
            for card in card_list
            if (not categories or str(card.get("category")) in categories)
            and (not name_pattern or name_pattern.search(str(card.get("name") or "")))
        ]
        if args.max_cards:
            keys = keys[: args.max_cards]
    else:
        keys = DEFAULT_KEYS
    css = (TEMPLATES_DIR / "styling.css").read_text(encoding="utf-8")

    cards_html: list[str] = []
    for key in keys:
        card = cards[key]
        entry = (media.get("cards") or {}).get(key, {})
        image = image_tag(str(entry.get("artwork_filename") or ""))
        label = card.get("display_label_override") or card.get("auto_display_label") or card["name"]
        category_class = f"ptcg-{str(card['category']).casefold()}-shell"
        cards_html.append(
            f"""
            <article class="preview-card">
              <div class="card">
                <div class="ptcg-shell ptcg-front-shell ptcg-card-shell {esc(category_class)}">
                  <header class="ptcg-card-header">
                    <div class="ptcg-label">{esc(label)}</div>
                  </header>
                  <div class="ptcg-art-stage">
                    <div class="ptcg-art">{image}</div>
                  </div>
                  <p class="preview-key">{esc(key)}</p>
                </div>
              </div>
            </article>
            """
        )

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PTCG front preview</title>
  <style>
{css}
    body.preview {{
      margin: 0;
      padding: 24px;
      background: #e5e7eb;
    }}

    .preview-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
      gap: 24px;
      align-items: start;
    }}

    .preview-card .card {{
      min-height: auto;
      padding: 18px;
      border-radius: 8px;
    }}

    .preview-card .ptcg-front-shell {{
      min-height: auto;
    }}

    .preview-card .ptcg-card-header {{
      margin: 0 0 14px;
    }}

    .preview-card .ptcg-label {{
      font-size: 2rem;
    }}

    .preview-card .ptcg-art-stage {{
      width: min(100%, 760px);
    }}

    .preview-card .ptcg-art img {{
      max-height: 440px;
    }}

    .preview-key {{
      margin: 10px 0 0;
      color: #475569;
      font-size: 12px;
      text-align: center;
    }}
  </style>
</head>
<body class="preview">
  <main class="preview-grid">
    {''.join(cards_html)}
  </main>
</body>
</html>
"""
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html_doc, encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
