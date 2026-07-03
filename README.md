# Pokémon TCG Competitive Anki Deck

A small, reproducible Anki deck builder for learning the cards that show up in
current competitive Pokémon TCG lists.

The deck is built from a frozen metagame snapshot, normalizes card mechanics,
deduplicates exact gameplay reprints, and emits Anki notes with stable IDs so
future updates can preserve scheduling. It is meant to be practical study glue:
less "memorize every printing ever", more "recognize the cards people are
actually putting on tables".

Snapshot: **2026-06-25**

## Public Release Policy

The public `.apkg` should be the **no-art build**:

- no card artwork;
- no full-card images;
- no set logos or marks;
- no bundled generated media files.

That is the version to upload to GitHub Releases or AnkiWeb. It is still a fan
project using Pokémon card names, mechanics, and metagame references, so this is
not legal advice and it is not zero-risk. It is simply the much cleaner release
shape than redistributing copyrighted card images.

The local/private build can include card art if you run the media pipeline on
your own machine. Generated media and `.apkg` files are intentionally ignored by
Git.

This project is not affiliated with, endorsed by, or sponsored by The Pokémon
Company, Nintendo, Creatures, Game Freak, Limitless TCG, TCGdex, or Anki.
Pokémon names, card text, artwork, logos, and related marks belong to their
respective rights holders.

## What Is In The Snapshot

- Top 50 named archetypes from the combined classified field of:
  - 2026 North America International Championships, Limitless Labs event `0070`;
  - 2026 Turin Special Event, Limitless Labs event `0069`.
- One representative NAIC deck list per archetype.
- 361 exact set-code/collector-number source locators.
- 145 source locators that appear in top-10 archetypes.
- Archetype membership, Anki tags, note model definitions, templates, and build
  scripts.

A set-number locator is a printing, not necessarily a unique gameplay card. The
builder resolves the source locators, normalizes gameplay fields, and collapses
exact mechanical reprints.

## What Is Not In The Repo

- downloaded card images;
- cropped artwork cues;
- generated media manifests;
- built `.apkg` packages;
- private credentials, API keys, or environment-specific config.

See [media/README.md](media/README.md) for the media policy.

## Quick Start

Install dependencies:

```bash
sfw uv sync
source .venv/bin/activate
```

Validate the frozen source data:

```bash
make test
make validate-source
```

Build the resolved card pool:

```bash
make resolve
make discover
make materialize
make validate-resolved
```

## Build The Public No-Art Deck

Use this for GitHub Releases and AnkiWeb:

```bash
make build-no-art
```

This package keeps the same notes, tags, stable keys, and structured mechanics,
but leaves all image fields empty and bundles zero media files.

## Build A Local Art Deck

Use this only for local/private study:

```bash
make media
make crop
python scripts/build_anki.py
```

Before trusting the cropped art cues, review the contact sheet:

```text
reports/artwork_crop_contact_sheet.jpg
```

The full-card images and crops are generated into `media/`, and the media-bearing
package is generated into `dist/`. Both are ignored by Git.

## Repository Map

```text
data/        Frozen source lists, overrides, and natural-key inputs
generated/   Reproducible generated tables that are safe to keep when audited
media/       Local-only downloaded images and crops
reports/     Validation and build summaries
schemas/     JSON schemas and Anki note-model specs
scripts/     Resolver, materializer, media, crop, and Anki build scripts
templates/   Anki HTML/CSS templates
tests/       Source, identity, template, and smoke tests
```

## Provenance

- Limitless TCG: tournament archetype pages, representative list encodings, and
  set/collector-number locators.
- TCGdex: structured card and set data used during resolution.
- Official Pokémon sources: preferred authority for rules, errata, legality, and
  bans when third-party data conflicts.

See [PROVENANCE.md](PROVENANCE.md) and [LICENSE_NOTES.md](LICENSE_NOTES.md) for
the longer version.
