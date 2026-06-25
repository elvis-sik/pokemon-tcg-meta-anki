# Design specification

## 1. Conceptual layers

The system has three layers:

```text
tournament snapshot
    ↓
source printings and mechanically normalized cards
    ↓
compiled Anki notes
```

Anki is a study interface, not the authoritative database.

The source layer may retain all printings necessary to resolve identity, legality, origin, and image selection. The generated collection contains one note per mechanical identity and does not present printing history to the learner.

## 2. Identity vocabulary

### Source locator

`ASC-142`, equivalent to `ASC 142`, identifies the exact set/collector-number entry used in a deck list.

### Mechanical identity

A normalized gameplay object. Alternate art, rarity, foil treatment, illustrator, language, set, and collector number do not create a new mechanical identity. Gameplay-relevant text and characteristics do.

### Natural Anki key

```text
ExactName · OriginSetCode OriginCollectorNumber
```

Example:

```text
Pikachu ex · SSP 57
```

The origin locator is the earliest known English printing of that mechanical identity. Once assigned, the key is frozen in `data/natural_key_registry.csv`, even if the data source is later corrected.

The key is the first Anki field, the browser-facing sort/search key, and the seed for a deterministic internal Anki GUID.

### Player-facing display label

Computed at build time:

```python
if display_label_override:
    label = display_label_override
elif legal_mechanical_identity_count_by_exact_name[name] == 1:
    label = name
else:
    label = f"{name} · {display_set_code} {display_collector_number}"
```

Do not use name + set without number: two mechanically distinct cards can share both exact name and set.

The ambiguity universe is the complete current English Standard mechanical pool. It is not limited to the top-50 study set.

## 3. Current display printing

Choose the printing used by `ArtworkImage` and `FullCardImage` independently of the natural key.

Default policy:

1. English.
2. Standard legal on the build's legality date.
3. Exact same mechanical identity.
4. Most recently released set.
5. Prefer a regular/normal-frame printing.
6. Within the chosen set, prefer the lowest collector number among regular-equivalent printings.
7. Permit a manual image override for unsuitable crops or collector-only layouts.

The artwork crop and full-card image must come from the same selected printing.

## 4. Card note types

All gameplay note types generate exactly one card.

### PTCG Pokémon

Common fields:

```text
CardKey
Name
AutoDisplayLabel
DisplayLabelOverride
ArtworkImage
FullCardImage
DisplaySetCode
DisplayCollectorNumber
CompetitiveRole
Rulings
SourceAttribution
```

Pokémon fields:

```text
PokemonType1
PokemonType2
HP
Stage
EvolvesFrom

RuleBoxClass
PrizeValue
SpecialLabels
OtherRuleText

Ability1Kind
Ability1Name
Ability1Text
Ability2Kind
Ability2Name
Ability2Text
Ability3Kind
Ability3Name
Ability3Text

Attack1Name
Attack1Cost
Attack1Damage
Attack1Text
Attack2Name
Attack2Cost
Attack2Damage
Attack2Text
Attack3Name
Attack3Cost
Attack3Damage
Attack3Text
Attack4Name
Attack4Cost
Attack4Damage
Attack4Text

Weakness1Type
Weakness1Value
Weakness2Type
Weakness2Value
Resistance1Type
Resistance1Value
Resistance2Type
Resistance2Value
RetreatCost
```

Four attack slots and three ability slots are a flattened Anki projection. The normalized source representation must use arrays and fail loudly if a card exceeds the allocated template capacity.

`ex` remains part of `Name`. `RuleBoxClass` separately captures the rules classification.

### PTCG Trainer

```text
CardKey
Name
AutoDisplayLabel
DisplayLabelOverride
ArtworkImage
FullCardImage
DisplaySetCode
DisplayCollectorNumber

TrainerSubtype
RuleBoxClass
EffectText
OtherRuleText

CompetitiveRole
Rulings
SourceAttribution
```

### PTCG Energy

```text
CardKey
Name
AutoDisplayLabel
DisplayLabelOverride
ArtworkImage
FullCardImage
DisplaySetCode
DisplayCollectorNumber

EnergySubtype
EnergyProvided
EffectText
OtherRuleText

CompetitiveRole
Rulings
SourceAttribution
```

## 5. Front/back behavior

### Gameplay front

Show only:

- final display label;
- artwork-only image.

Do not reveal HP, type, stage, attack text, set metadata, or regulation marks unless a set/number qualifier is required by the display-label rule.

### Gameplay back

Show:

- final display label;
- full-card image;
- complete mechanics rendered from structured fields;
- a secondary section for competitive role, rulings, and source attribution.

Do not use `{{FrontSide}}`; it would repeat the artwork cue.

Desktop layout should be image-and-text columns. Mobile layout should stack the full card above the mechanics.

## 6. Recall criterion

The learner should recall the whole functional card. Exact punctuation is not required, but the answer is wrong when it omits or changes a decision-relevant item:

- Energy cost;
- damage number/modifier;
- target;
- quantity;
- condition;
- timing;
- optional versus mandatory wording;
- once-per-turn or once-per-game restriction;
- damage versus damage counters;
- Rule Box consequence;
- Weakness, Resistance, or Retreat Cost.

Competitive role is explanatory context and is not part of the strict recall test.

## 7. Set note type

### PTCG Set fields

```text
SetKey
Code
FullName
SetMarkImage
SetLogoImage
ReleaseDate
TournamentLegalDate
Series
SetType
SourceAttribution
```

`SetKey` is normally the code.

Generate two cards:

1. set mark/code → full name;
2. full name → set mark/code.

Dates, series, set type, and logo are secondary information on the back. The operational association is code/mark ↔ name.

## 8. Deck and tag architecture

Decks:

```text
Pokémon TCG::Cards
Pokémon TCG::Sets
Pokémon TCG::Rules
```

Do not make permanent archetype subdecks. Use tags and filtered decks.

Required tags:

```text
ptcg::card_type::pokemon
ptcg::card_type::trainer
ptcg::card_type::energy

ptcg::mechanic::ex
ptcg::mechanic::mega_evolution_ex
ptcg::mechanic::tera
ptcg::mechanic::ace_spec
...

ptcg::archetype::<slug>

ptcg::meta::2026_06::top10
ptcg::meta::2026_06::top50
```

Do not add a generic `ptcg::set::<code>` tag to a mechanical card: one mechanical card may have many exact reprints. A specific `origin_set` tag is permissible but not required.

## 9. Media fields

Store complete Anki image HTML in image fields, for example:

```html
<img src="ptcg_abcd1234_art.webp" alt="">
```

Do not construct media paths in templates from partial fields. Bundle local files so review works offline.

No copyrighted card images are included in this handoff. The builder downloads them locally.

## 10. Update semantics

### New mechanical card

Create a new note, assign a natural key, and add current tags.

### Exact reprint

Keep the existing note and key. It may become the new display printing and replace both images.

### New same-name mechanical card

Recompute ambiguity across Standard. Existing and new notes may both gain set-number qualifiers.

### Ambiguity disappears after rotation

The remaining Standard card may return to name-only.

### Card leaves top 10/top 50

Remove the current snapshot tag. Do not delete the note or reset scheduling.

### Card rotates from Standard

Retain the note and scheduling in the master collection; remove it from active filtered-study tags or add an inactive/rotated tag.

## 11. Stable Anki updates

- Keep note type IDs and field order stable.
- Generate deterministic internal Anki GUIDs from `CardKey`.
- Treat `CardKey` as immutable after registry assignment.
- Preserve media filenames where the underlying image is unchanged.
- Update note fields/tags in place.
- Never delete and recreate notes merely because labels, legality, images, or meta tags changed.
