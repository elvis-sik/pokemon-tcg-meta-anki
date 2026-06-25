"""Shared helpers for the Pokémon TCG Anki handoff build.

The scripts are deliberately dependency-light. Network steps use ``requests``;
validation/build steps otherwise rely on the standard library where possible.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import unicodedata
from collections.abc import Iterable, Iterator, Mapping, Sequence
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
GENERATED_DIR = ROOT / "generated"
CACHE_DIR = ROOT / "cache"
REPORTS_DIR = ROOT / "reports"
MEDIA_DIR = ROOT / "media"
TEMPLATES_DIR = ROOT / "templates"
SCHEMAS_DIR = ROOT / "schemas"

for _directory in (GENERATED_DIR, CACHE_DIR, REPORTS_DIR, MEDIA_DIR):
    _directory.mkdir(parents=True, exist_ok=True)


SMART_TRANSLATION = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u00a0": " ",
        "\u00d7": "x",
    }
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_text(value: Any) -> str:
    """Normalize text for mechanical comparison, not for learner display."""
    if value is None:
        return ""
    text = str(value).translate(SMART_TRANSLATION)
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_name(value: Any) -> str:
    return normalize_text(value)


def normalize_for_match(value: Any) -> str:
    text = normalize_text(value).casefold()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", text)


def slugify(value: str) -> str:
    text = unicodedata.normalize("NFKD", value)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text or "unnamed"


def english(value: Any) -> Any:
    """Return the English member of a multilingual object when present."""
    if isinstance(value, Mapping):
        for key in ("en", "en-US", "en_us", "english"):
            if key in value:
                return value[key]
    return value


def normalize_scalar(value: Any) -> Any:
    value = english(value)
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else value
    return normalize_text(value)


def canonicalize(value: Any) -> Any:
    """Return a JSON-stable representation suitable for hashing."""
    if isinstance(value, Mapping):
        return {
            str(key): canonicalize(value[key])
            for key in sorted(value, key=lambda item: str(item))
        }
    if isinstance(value, (list, tuple)):
        return [canonicalize(item) for item in value]
    if isinstance(value, set):
        return sorted(canonicalize(item) for item in value)
    return normalize_scalar(value)


def canonical_json(value: Any) -> str:
    return json.dumps(
        canonicalize(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def stable_int(namespace: str, value: str, digits: int = 10) -> int:
    digest = hashlib.sha256(f"{namespace}\0{value}".encode("utf-8")).hexdigest()
    maximum = 10**digits - 1
    minimum = 10 ** (digits - 1)
    return minimum + (int(digest[:16], 16) % (maximum - minimum))


def stable_media_stem(card_key: str) -> str:
    digest = hashlib.sha256(card_key.encode("utf-8")).hexdigest()[:16]
    return f"ptcg_{digest}"


def natural_card_key(name: str, set_code: str, collector_number: str) -> str:
    """Human-readable stable key once its origin printing has been audited."""
    return f"{normalize_name(name)} · {normalize_text(set_code)} {normalize_text(collector_number)}"


def compute_display_label(
    *,
    name: str,
    standard_mechanical_identity_count: int,
    display_set_code: str,
    display_collector_number: str,
    override: str = "",
) -> str:
    """Apply the agreed player-facing label rule deterministically."""
    if normalize_text(override):
        return normalize_text(override)
    normalized_name = normalize_name(name)
    if standard_mechanical_identity_count == 1:
        return normalized_name
    return f"{normalized_name} · {normalize_text(display_set_code) or 'UNKNOWN'} {normalize_text(display_collector_number)}"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Iterable[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=False)
        handle.write("\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"Expected object at {path}:{line_number}")
            records.append(value)
    return records


def write_jsonl(path: Path, records: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=False))
            handle.write("\n")


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() in {"1", "true", "yes", "y"}


def split_tags(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [part for part in str(value).split() if part]


def parse_iso_date(value: Any) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def release_sort_key(printing: Mapping[str, Any]) -> tuple[date, tuple[int, str], str]:
    release = parse_iso_date(printing.get("release_date")) or date.min
    local_id = str(
        printing.get("collector_number")
        or printing.get("localId")
        or printing.get("local_id")
        or ""
    )
    match = re.fullmatch(r"0*(\d+)", local_id)
    numeric: tuple[int, str] = (int(match.group(1)), "") if match else (10**9, local_id)
    return release, numeric, str(printing.get("id") or printing.get("tcgdex_card_id") or "")


def normalize_category(value: Any) -> str:
    category = normalize_text(english(value)).casefold()
    if category in {"pokemon", "pokémon"}:
        return "Pokemon"
    if category == "trainer":
        return "Trainer"
    if category == "energy":
        return "Energy"
    raise ValueError(f"Unknown card category: {value!r}")


def normalize_rules(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        value = [value]
    output: list[str] = []
    for item in value:
        item = english(item)
        if isinstance(item, Mapping):
            item = item.get("text") or item.get("effect") or item.get("rule") or item
        text = normalize_text(item)
        if text:
            output.append(text)
    return output


def normalize_named_effects(items: Any, *, include_kind: bool) -> list[dict[str, Any]]:
    if not items:
        return []
    output: list[dict[str, Any]] = []
    for raw in items:
        if not isinstance(raw, Mapping):
            continue
        item: dict[str, Any] = {}
        if include_kind:
            item["kind"] = normalize_text(raw.get("type") or raw.get("kind") or "Ability")
        item["name"] = normalize_text(english(raw.get("name")))
        item["text"] = normalize_text(english(raw.get("effect") or raw.get("text")))
        output.append(item)
    return output


def normalize_attacks(items: Any) -> list[dict[str, Any]]:
    if not items:
        return []
    output: list[dict[str, Any]] = []
    for raw in items:
        if not isinstance(raw, Mapping):
            continue
        cost = raw.get("cost") or []
        if not isinstance(cost, list):
            cost = [cost]
        output.append(
            {
                "name": normalize_text(english(raw.get("name"))),
                "cost": [normalize_text(english(item)) for item in cost],
                "damage": normalize_text(raw.get("damage")),
                "text": normalize_text(english(raw.get("effect") or raw.get("text"))),
            }
        )
    return output


def normalize_type_modifiers(items: Any) -> list[dict[str, str]]:
    if not items:
        return []
    output: list[dict[str, str]] = []
    for raw in items:
        if not isinstance(raw, Mapping):
            continue
        output.append(
            {
                "type": normalize_text(english(raw.get("type"))),
                "value": normalize_text(raw.get("value")),
            }
        )
    return output


def normalized_mechanics(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Project a TCGdex-like payload into gameplay-relevant English fields.

    This is intentionally conservative. Exact reprints with merely editorial
    wording differences may need a row in ``manual_mechanical_merge_overrides.csv``.
    Unknown provider fields are not silently assumed to be mechanical.
    """
    category = normalize_category(payload.get("category"))
    name = normalize_name(english(payload.get("name")))
    if not name:
        raise ValueError("Card payload has no English name")

    rules = normalize_rules(payload.get("rules") or payload.get("rule"))
    common: dict[str, Any] = {
        "name": name,
        "category": category,
        "rules": rules,
    }

    if category == "Pokemon":
        types = payload.get("types") or []
        if not isinstance(types, list):
            types = [types]
        mechanics = {
            **common,
            "hp": normalize_scalar(payload.get("hp")),
            "types": [normalize_text(english(item)) for item in types],
            "stage": normalize_text(payload.get("stage")),
            "evolves_from": normalize_text(
                payload.get("evolveFrom")
                or payload.get("evolvesFrom")
                or payload.get("evolves_from")
            ),
            "suffix": normalize_text(payload.get("suffix")),
            "trainer_affiliation": normalize_text(
                english(
                    payload.get("trainer")
                    or payload.get("trainerAffiliation")
                    or payload.get("trainer_affiliation")
                )
            ),
            "abilities": normalize_named_effects(payload.get("abilities"), include_kind=True),
            "attacks": normalize_attacks(payload.get("attacks")),
            "weaknesses": normalize_type_modifiers(payload.get("weaknesses")),
            "resistances": normalize_type_modifiers(payload.get("resistances")),
            "retreat": normalize_scalar(payload.get("retreat")),
        }
    elif category == "Trainer":
        mechanics = {
            **common,
            "trainer_type": normalize_text(
                payload.get("trainerType") or payload.get("trainer_type") or payload.get("subtype")
            ),
            "effect": normalize_text(english(payload.get("effect") or payload.get("text"))),
        }
    else:
        mechanics = {
            **common,
            "energy_type": normalize_text(
                payload.get("energyType") or payload.get("energy_type") or payload.get("subtype")
            ),
            "effect": normalize_text(english(payload.get("effect") or payload.get("text"))),
        }

    return canonicalize(mechanics)


def mechanical_fingerprint(payload: Mapping[str, Any]) -> str:
    return sha256_json(normalized_mechanics(payload))


def card_name(payload: Mapping[str, Any]) -> str:
    return normalize_name(english(payload.get("name")))


def card_category(payload: Mapping[str, Any]) -> str:
    return normalize_category(payload.get("category"))


def ensure_relative_to_root(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def chunks(items: Sequence[Any], size: int) -> Iterator[Sequence[Any]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]
