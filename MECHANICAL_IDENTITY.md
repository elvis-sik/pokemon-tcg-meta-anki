# Mechanical identity and deduplication

## Purpose

The frozen tournament data identifies printings. The study deck needs gameplay identities. This document defines the conversion.

## Mechanical fingerprint

Canonicalize a resolved card into a deterministic JSON object, then hash its UTF-8 serialization with SHA-256.

### Include for every card

- exact official card name;
- category/supertype;
- mechanically relevant subtype/classification;
- normalized rules text.

### Include for Pokémon

- type(s);
- HP;
- stage;
- evolves-from name;
- named abilities: kind, name, effective text, in printed order;
- attacks: name, Energy cost sequence, damage string, effective text, in printed order;
- Weakness entries;
- Resistance entries;
- Retreat Cost;
- Rule Box and other special rules;
- special labels that affect gameplay.

### Include for Trainers

- exact name;
- Trainer subtype;
- Rule Box/classification such as ACE SPEC;
- complete effective effect text;
- additional rule text.

### Include for Energy

- exact name;
- Basic/Special classification;
- Energy provided;
- complete effective effect text;
- additional rule text.

## Exclude

- set and collector number;
- rarity;
- illustrator;
- artwork;
- foil/parallel finish;
- language;
- regulation mark;
- legality;
- release date;
- market price;
- flavor text;
- source-specific IDs;
- harmless formatting differences.

## Text normalization

Normalize representation, not meaning:

- Unicode NFC;
- typographic apostrophes/dashes to a selected canonical form;
- collapse repeated whitespace;
- trim;
- normalize Energy symbols to canonical tokens;
- normalize line breaks between clauses consistently;
- apply official errata before hashing.

Do not paraphrase or aggressively rewrite text. A semantic merger based on an LLM must never be the sole authority.

## Merge rules

### Merge

- alternate art with the same effective mechanics;
- secret/full-art version of the same card;
- reverse-holo/foil treatment;
- exact reprint in a later set;
- text that differs only because an official erratum makes the effective rules identical.

### Do not merge

- same exact name but different attacks, HP, Ability, stage, or other mechanics;
- different exact names even if the effects appear identical;
- cards whose text is merely similar;
- cards whose only apparent equivalence comes from a temporary format interaction.

Different names must remain separate because name affects deck construction, evolution, search effects, and other interactions.

## Natural-key assignment

For each merge group:

1. enumerate all known English printings;
2. order by release date, then set sequence, then collector number;
3. propose `Name · SET Number` from the earliest;
4. if a key is already present in `natural_key_registry.csv`, preserve it;
5. if an earlier printing is discovered later, record the discovery but do not rename an established Anki note automatically.

## Top-10/top-50 propagation

Tags are set unions over source locators.

```python
mechanical.top10 = any(source.in_top10 for source in merged_sources)
mechanical.top50 = any(source.in_top50 for source in merged_sources)
mechanical.archetypes = union(source.archetypes for source in merged_sources)
```

This is why `card_locator_archetype_membership.csv` is retained after deduplication.

## Required human-review cases

Emit review rows when:

- two records have the same normalized fingerprint but different exact names;
- one source locator fails to resolve;
- source providers disagree on mechanics;
- a card has more than four attacks or three abilities;
- an official erratum is known;
- image selection cannot identify a regular printing;
- a same-name group contains multiple mechanical identities;
- two candidate printings differ only in punctuation that normalization cannot safely classify.

## Count policy

The final mechanical counts are outputs, not targets. The source invariants are 145 top-10 locators and 361 top-50 locators. Any final mechanical count must be accompanied by a merge report showing exactly which source locators collapsed.
