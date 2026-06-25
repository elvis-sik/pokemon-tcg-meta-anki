# Pokémon TCG competitive-card Anki handoff

Snapshot: **2026-06-25**

This repository is a coding-agent handoff for building an Anki package that teaches the mechanically distinct cards used by the leading Pokémon TCG Standard archetypes.

## What is frozen here

- The top 50 named archetypes by combined classified tournament share from:
  - 2026 North America International Championships (Limitless Labs event `0070`)
  - 2026 Turin Special Event (Limitless Labs event `0069`)
- One representative NAIC deck list for every archetype.
- Every exact set-code/collector-number locator in those 50 lists.
- Archetype membership and the intended Anki tags for every source locator.
- The complete note-model, display-label, natural-key, media, tag, and update design.
- HTML/CSS card templates and implementation scripts.

## Count warning: do not force 141 or 360

The frozen source data contains:

| Scope | Exact source locators | Earlier planning estimate |
|---|---:|---:|
| Top 10 archetypes | 145 | approximately 141 mechanically distinct cards |
| Top 50 archetypes | 361 | approximately 360 mechanically distinct cards |

A set-number locator identifies a printing. It is **not automatically a mechanical identity**. Exact reprints appearing under different set numbers must be merged. The earlier 141/360 values were planning estimates, not audited outputs.

The build must:

1. resolve all 361 source locators;
2. normalize their gameplay data;
3. collapse exact mechanical reprints;
4. report the resulting top-10 and top-50 counts;
5. **never add, drop, or merge records merely to hit 141 or 360**.

A resolved mechanical note receives `ptcg::meta::2026_06::top10` when any of its source locators occurs in ranks 1–10. Every resolved note in the full union receives `ptcg::meta::2026_06::top50`.

## Intended output

One `.apkg` containing:

- `Pokémon TCG::Cards`
  - one review card per mechanically distinct gameplay card;
  - separate note types for Pokémon, Trainer, and Energy;
- `Pokémon TCG::Sets`
  - two review directions per set: mark/code → full name and full name → mark/code;
- optional `Pokémon TCG::Rules`, outside the immediate scope of this handoff.

No card images are redistributed in this ZIP. The build scripts fetch images and create artwork crops locally.

## Start here

1. Read `HANDOFF_PROMPT.md`.
2. Read `DESIGN_SPEC.md` and `MECHANICAL_IDENTITY.md`.
3. Inspect `data/snapshot_counts.json`.
4. Run:

```bash
sfw uv sync
source .venv/bin/activate

python scripts/validate_source.py
python scripts/resolve_cards_tcgdex.py
python scripts/discover_printings_tcgdex.py
python scripts/materialize_mechanical_pool.py
python scripts/validate_resolved_pool.py
python scripts/download_media.py
python scripts/crop_artwork.py
python scripts/build_anki.py
anki-workbench smoke --screenshot /tmp/ptcg-preview.png
```

On macOS, the workbench smoke command currently opens a disposable Anki GUI window
briefly while it renders cards. The data directory is isolated, and the profile is
named `PTCG Workbench Preview` so it does not look like your review profile.

The network-dependent steps are intentionally separate from validation and compilation. Run `python scripts/freeze_natural_keys.py` only after auditing the proposed origin keys; it creates durable registry state for later updates.

## Acceptance criteria

The finished implementation must satisfy all of these:

- All 50 representative decks decode to exactly 60 cards.
- The frozen source union is 361 locators, of which 145 occur in the top ten.
- Mechanical identity is based on gameplay-relevant fields, not name alone.
- Same-name/different-text cards remain separate notes.
- Exact reprints collapse into one note.
- The first Anki field is a stable, readable natural key.
- The natural key is independent of the current display image.
- The player-facing label is name-only only when the exact name is mechanically unambiguous in the current English Standard pool.
- Ambiguous labels include name, display set code, and collector number.
- Every gameplay note generates exactly one review card.
- Card fronts contain only the player-facing label and artwork crop.
- Card backs contain the full-card image and complete structured mechanics.
- The top-10 tag survives mechanical merging by unioning source-locator tags.
- Existing Anki scheduling survives later release updates.
- The build emits an audit report listing merges, ambiguous names, unresolved cards, missing media, and final counts.

## Repository map

```text
data/
  archetypes_top50.csv
  representative_decks.json
  representative_deck_entries.csv
  card_source_locators_top50_361.csv
  card_source_locators_top10_145.csv
  card_candidates_with_tags_361.csv
  card_locator_archetype_membership.csv
  set_catalog.csv
  *_overrides.csv
  natural_key_registry.csv

schemas/
  source_card.schema.json
  mechanical_card.schema.json
  anki_*.schema.json

templates/
  pokemon_*.html
  trainer_*.html
  energy_*.html
  set_*.html
  styling.css

scripts/
  decode_limitless_builder.py
  validate_source.py
  resolve_cards_tcgdex.py
  discover_printings_tcgdex.py
  materialize_mechanical_pool.py
  validate_resolved_pool.py
  download_media.py
  crop_artwork.py
  freeze_natural_keys.py
  build_anki.py
```
