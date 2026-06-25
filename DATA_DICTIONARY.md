# Data dictionary

## Frozen source tables

### `archetypes_top50.csv`

One row per ranked archetype.

Key fields:

- `rank`: combined-field popularity rank;
- `combined_entries`: NAIC + Turin classified entries;
- `field_share_pct`, `cumulative_field_share_pct`;
- `top10`: whether rank ≤ 10;
- `representative_player`: pilot of the frozen NAIC list;
- `builder_encoding`: full Limitless builder string;
- `representative_deck_distinct_print_locators`: decoded list-line count.

### `representative_decks.json`

Human- and machine-readable frozen deck inputs. Every card entry has quantity,
set code, collector number, and raw locator. The builder encoding is retained
as the compact upstream representation.

### `representative_deck_entries.csv`

One row per deck-list line: 1,305 rows. This is the easiest source for joins,
per-archetype quantities, and reconstruction of each 60-card list.

### `card_source_locators_top50_361.csv`

One row per exact set-number locator in the top-50 representative union. It is
the richest source-level table and includes archetype membership, quantities,
proposed Anki tags, and a direct Limitless card URL.

The resolution/mechanical-key fields intentionally begin blank. The local
network-backed build fills them after structured card resolution.

### `card_source_locators_top10_145.csv`

The exact source-locator subset occurring in archetype ranks 1–10.

### `card_candidates_with_tags_361.csv`

A coding-agent-oriented projection of the top-50 union. It adds
`priority_tier` (`top10_core` or `top50_extended`) and keeps the archetype/tag
columns together. This is the most convenient single CSV to inspect before
resolution.

### `card_locator_archetype_membership.csv`

Long-form many-to-many relation between source locator and archetype. Use it
to union archetype and top-10 tags after exact-reprint merging.

## Durable override/registry state

- `manual_mechanical_merge_overrides.csv`: controlled merge groups when raw
  provider text is functionally identical but fingerprints differ.
- `display_label_overrides.csv`: exceptional community-facing labels.
- `natural_key_registry.csv`: immutable fingerprint → natural-key assignments
  after first audit.
- `art_crop_overrides.csv`: normalized crop rectangles.
- `competitive_role_overrides.csv`: optional pedagogical role text.
- `rulings_overrides.csv`: optional reviewed rulings and citations.
- `set_code_overrides.csv`: TCGdex historical set ID → player-facing/Limitless code crosswalk needed for stable earliest-print natural keys.

Do not regenerate these files destructively.

## Set data

### `set_catalog.csv`

Limitless code → English set-name seed table. TCGdex IDs, dates, counts, and
asset URLs are populated during resolution. Promo and Energy series require
explicit review.

## Snapshot/provenance data

- `snapshot_counts.json`: source invariants and count warning.
- `source_manifest.json`: event/card-source URLs and method.

## Generated files

The supplied scripts create these replaceable outputs:

```text
generated/resolved_source_cards.jsonl
generated/printing_universe.jsonl
generated/set_catalog_resolved.csv
generated/mechanical_cards.jsonl
generated/mechanical_card_roster.csv
generated/mechanical_card_archetype_membership.csv
generated/media_manifest.json
```

The mechanically deduplicated roster—not the 361-locator source table—is the
input to the Anki compiler.
