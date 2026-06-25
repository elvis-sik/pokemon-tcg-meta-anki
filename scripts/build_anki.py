#!/usr/bin/env python3
"""Compile normalized card/set records and local media into one Anki package."""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from typing import Any

import genanki

from common import GENERATED_DIR, MEDIA_DIR, REPORTS_DIR, ROOT, TEMPLATES_DIR, read_csv, read_json, read_jsonl, write_json

MODEL_IDS = {
    "PTCG Pokemon": 1876501001,
    "PTCG Trainer": 1876501002,
    "PTCG Energy": 1876501003,
    "PTCG Set": 1876501004,
}
DECK_IDS = {
    "Pokémon TCG::Cards": 1876501101,
    "Pokémon TCG::Sets": 1876501102,
}


class StableNote(genanki.Note):
    @property
    def guid(self) -> str:
        return genanki.guid_for(self.fields[0])


def e(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=False)


def multiline(values: list[Any]) -> str:
    return "<br>".join(e(item) for item in values if str(item).strip())


def image_field(filename: str) -> str:
    return f'<img src="{html.escape(filename, quote=True)}">' if filename else ""


def energy_cost(cost: list[Any]) -> str:
    return " ".join(
        f'<span class="ptcg-energy ptcg-energy-{re.sub(r"[^a-z0-9]+", "-", str(token).casefold()).strip("-")}">{e(token)}</span>'
        for token in cost
    )


def rule_box(name: str, mechanics: dict[str, Any]) -> tuple[str, str, str]:
    lower_name = name.casefold()
    rules_text = " ".join(mechanics.get("rules") or []).casefold()
    suffix = str(mechanics.get("suffix") or "").strip()
    special: list[str] = []
    affiliation = str(mechanics.get("trainer_affiliation") or "").strip()
    if affiliation:
        special.append(affiliation)
    for token in ("Tera", "Ancient", "Future", "Radiant"):
        if token.casefold() in lower_name or token.casefold() in rules_text or token.casefold() == suffix.casefold():
            special.append(token)

    if lower_name.endswith(" ex"):
        if "mega evolution" in lower_name or "mega evolution" in rules_text:
            return "Mega Evolution Pokémon ex", "3", " · ".join(dict.fromkeys(special))
        return "Pokémon ex", "2", " · ".join(dict.fromkeys(special))
    if lower_name.endswith(" vmax"):
        return "Pokémon VMAX", "3", " · ".join(dict.fromkeys(special))
    if lower_name.endswith((" vstar", " v", "-gx", " gx", "-ex", " ex")):
        return suffix or "Rule Box Pokémon", "2", " · ".join(dict.fromkeys(special))
    return suffix, "1", " · ".join(dict.fromkeys(special))


def load_templates(model_spec: dict[str, Any]) -> list[dict[str, str]]:
    templates = []
    for spec in model_spec["templates"]:
        templates.append(
            {
                "name": spec["name"],
                "qfmt": (ROOT / spec["front"]).read_text(encoding="utf-8"),
                "afmt": (ROOT / spec["back"]).read_text(encoding="utf-8"),
            }
        )
    return templates


def make_models() -> dict[str, genanki.Model]:
    spec = read_json(ROOT / "schemas" / "anki_note_models.json")
    css = (TEMPLATES_DIR / "styling.css").read_text(encoding="utf-8")
    models: dict[str, genanki.Model] = {}
    for name, model_spec in spec.items():
        models[name] = genanki.Model(
            MODEL_IDS[name],
            name,
            fields=[{"name": field} for field in model_spec["fields"]],
            templates=load_templates(model_spec),
            css=css,
            sort_field_index=0,
        )
    return models


def blank_fields(model_fields: list[str]) -> dict[str, str]:
    return {field: "" for field in model_fields}


def source_attribution(card: dict[str, Any]) -> str:
    locators = ", ".join(card.get("source_locators") or [])
    return f"Mechanics: TCGdex. Tournament locators: Limitless TCG ({e(locators)})."


def card_fields(card: dict[str, Any], media: dict[str, Any], model_fields: list[str]) -> dict[str, str]:
    fields = blank_fields(model_fields)
    mechanics = card.get("normalized_mechanics") or {}
    display = card.get("display_printing") or {}
    media_entry = (media.get("cards") or {}).get(card["card_key"], {})
    fields.update(
        {
            "CardKey": e(card["card_key"]),
            "Name": e(card["name"]),
            "AutoDisplayLabel": e(card.get("auto_display_label", "")),
            "DisplayLabelOverride": e(card.get("display_label_override", "")),
            "ArtworkImage": image_field(str(media_entry.get("artwork_filename") or "")),
            "FullCardImage": image_field(str(media_entry.get("full_card_filename") or "")),
            "DisplaySetCode": e(display.get("set_code", "")),
            "DisplayCollectorNumber": e(display.get("collector_number", "")),
            "CompetitiveRole": e(card.get("competitive_role", "")),
            "Rulings": str(card.get("rulings", "")),
            "SourceAttribution": source_attribution(card),
        }
    )
    rules = mechanics.get("rules") or []
    fields["OtherRuleText"] = multiline(rules)

    category = card["category"]
    if category == "Pokemon":
        types = mechanics.get("types") or []
        rule_class, prize_value, special = rule_box(str(card["name"]), mechanics)
        fields.update(
            {
                "PokemonType1": e(types[0] if len(types) > 0 else ""),
                "PokemonType2": e(types[1] if len(types) > 1 else ""),
                "HP": e(mechanics.get("hp", "")),
                "Stage": e(mechanics.get("stage", "")),
                "EvolvesFrom": e(mechanics.get("evolves_from", "")),
                "RuleBoxClass": e(rule_class),
                "PrizeValue": e(prize_value),
                "SpecialLabels": e(special),
                "RetreatCost": e(mechanics.get("retreat", "")),
            }
        )
        for index, ability in enumerate((mechanics.get("abilities") or [])[:3], 1):
            fields[f"Ability{index}Kind"] = e(ability.get("kind", "Ability"))
            fields[f"Ability{index}Name"] = e(ability.get("name", ""))
            fields[f"Ability{index}Text"] = e(ability.get("text", ""))
        for index, attack in enumerate((mechanics.get("attacks") or [])[:4], 1):
            fields[f"Attack{index}Name"] = e(attack.get("name", ""))
            fields[f"Attack{index}Cost"] = energy_cost(attack.get("cost") or [])
            fields[f"Attack{index}Damage"] = e(attack.get("damage", ""))
            fields[f"Attack{index}Text"] = e(attack.get("text", ""))
        for index, weakness in enumerate((mechanics.get("weaknesses") or [])[:2], 1):
            fields[f"Weakness{index}Type"] = e(weakness.get("type", ""))
            fields[f"Weakness{index}Value"] = e(weakness.get("value", ""))
        for index, resistance in enumerate((mechanics.get("resistances") or [])[:2], 1):
            fields[f"Resistance{index}Type"] = e(resistance.get("type", ""))
            fields[f"Resistance{index}Value"] = e(resistance.get("value", ""))
    elif category == "Trainer":
        fields["TrainerSubtype"] = e(mechanics.get("trainer_type", ""))
        fields["RuleBoxClass"] = "ACE SPEC" if "ace spec" in " ".join(rules).casefold() else ""
        fields["EffectText"] = e(mechanics.get("effect", ""))
    else:
        fields["EnergySubtype"] = e(mechanics.get("energy_type", ""))
        name = str(card["name"])
        fields["EnergyProvided"] = e(name.removesuffix(" Energy") if name.endswith(" Energy") else "")
        fields["EffectText"] = e(mechanics.get("effect", ""))
    return fields


def set_fields(row: dict[str, str], media: dict[str, Any], model_fields: list[str]) -> dict[str, str]:
    fields = blank_fields(model_fields)
    code = row.get("limitless_code") or row.get("code") or row.get("tcgdex_set_id") or ""
    media_entry = (media.get("sets") or {}).get(code, {})
    fields.update(
        {
            "SetKey": e(code),
            "Code": e(code),
            "FullName": e(row.get("full_name", "")),
            "SetMarkImage": image_field(str(media_entry.get("mark_filename") or "")),
            "SetLogoImage": image_field(str(media_entry.get("logo_filename") or "")),
            "ReleaseDate": e(row.get("release_date_iso", "")),
            "TournamentLegalDate": e(row.get("tournament_legal_date_iso", "")),
            "Series": e(row.get("series", "")),
            "SetType": e(row.get("set_type", "")),
            "SourceAttribution": "Set metadata: TCGdex; player-facing code: Limitless TCG.",
        }
    )
    return fields


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cards", type=Path, default=GENERATED_DIR / "mechanical_cards.jsonl"
    )
    parser.add_argument(
        "--sets", type=Path, default=GENERATED_DIR / "set_catalog_resolved.csv"
    )
    parser.add_argument(
        "--media", type=Path, default=GENERATED_DIR / "media_manifest.json"
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "dist" / "ptcg_competitive_cards_2026-06-25.apkg"
    )
    parser.add_argument("--allow-missing-media", action="store_true")
    args = parser.parse_args()

    cards = read_jsonl(args.cards)
    if not cards:
        raise SystemExit(f"No mechanical cards in {args.cards}")
    media = read_json(args.media)
    models = make_models()
    card_deck = genanki.Deck(DECK_IDS["Pokémon TCG::Cards"], "Pokémon TCG::Cards")
    set_deck = genanki.Deck(DECK_IDS["Pokémon TCG::Sets"], "Pokémon TCG::Sets")
    note_count = 0
    missing_media: list[str] = []

    for card in cards:
        model_name = f"PTCG {card['category']}"
        model = models[model_name]
        model_fields = [item["name"] for item in model.fields]
        values = card_fields(card, media, model_fields)
        if not values["ArtworkImage"] or not values["FullCardImage"]:
            missing_media.append(str(card["card_key"]))
        note = StableNote(
            model=model,
            fields=[values[name] for name in model_fields],
            tags=list(card.get("tags") or []),
        )
        card_deck.add_note(note)
        note_count += 1

    set_count = 0
    if args.sets.exists():
        model = models["PTCG Set"]
        model_fields = [item["name"] for item in model.fields]
        for row in read_csv(args.sets):
            values = set_fields(row, media, model_fields)
            note = StableNote(model=model, fields=[values[name] for name in model_fields], tags=["ptcg::set"])
            set_deck.add_note(note)
            set_count += 1

    media_files: list[str] = []
    for path in sorted(MEDIA_DIR.iterdir()):
        if path.is_file() and path.suffix.casefold() in {".png", ".jpg", ".jpeg", ".webp"}:
            media_files.append(str(path))

    if missing_media and not args.allow_missing_media:
        raise SystemExit(f"Missing card media for {len(missing_media)} notes; see media pipeline")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    package = genanki.Package([card_deck, set_deck])
    package.media_files = media_files
    package.write_to_file(str(args.output))
    summary = {
        "output": str(args.output),
        "gameplay_note_count": note_count,
        "set_note_count": set_count,
        "review_card_count": note_count + 2 * set_count,
        "media_file_count": len(media_files),
        "missing_card_media_count": len(missing_media),
        "missing_card_media": missing_media,
    }
    write_json(REPORTS_DIR / "anki_build_summary.json", summary)
    print(json.dumps({k: v for k, v in summary.items() if k != "missing_card_media"}, indent=2))


if __name__ == "__main__":
    main()
