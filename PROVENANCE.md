# Provenance and limitations

## Metagame snapshot

Date: 2026-06-25

The ranking combines classified archetype entries from:

- Limitless Labs event 0070: 2026 North America International Championships;
- Limitless Labs event 0069: 2026 Turin Special Event.

The two event tables were grouped by archetype. Closely related variants follow Limitless's grouping. The catch-all `Other` bucket is excluded from the named top-50 ranking.

The combined classified field contains 5,775 deck entries.

- Ranks 1–10: 4,194 entries, 72.6234% of the field.
- Ranks 1–50: 5,688 entries, 98.4935% of the field.

One representative list per archetype was selected from NAIC and frozen as a Limitless builder encoding. This is a pedagogical stock-list sample, not the union of every card ever used by the archetype.

## What the dataset can support

- a coherent representative vocabulary for the top 50 archetypes;
- top-10 versus top-50 Anki tagging;
- archetype-filtered study;
- reproducible source-list reconstruction;
- later refetching and mechanical deduplication.

## What it does not claim

- that the chosen list is the uniquely best build;
- that every common variant/tech card is present;
- that 141 and 360 are exact audited mechanical counts;
- that current metagame shares remain valid after a new expansion;
- that TCGdex or Limitless data is error-free;
- that image rights are transferred by this handoff.

## Data-source roles

### Limitless TCG

Used for tournament archetype tables, representative deck encodings, and set/collector-number locators.

### TCGdex

Recommended structured source for card mechanics and image asset URLs. Its API exposes full card objects by set ID and local collector number.

### Official Pokémon sources

Use official rulebooks, errata, legality announcements, and banned-card announcements to override third-party data where they conflict.

## Reproducibility caveat

A future refetch can legitimately change:

- corrected text;
- legalities;
- set mappings;
- image availability;
- newly discovered exact reprints;
- player-facing ambiguity labels.

Raw responses should be cached with timestamps and source URLs. Generated outputs should include a source-data version.
