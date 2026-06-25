# Initial handoff validation

Validated on 2026-06-25 in the artifact environment.

## Frozen-source invariants

- 50 ranked named archetypes.
- 50 representative deck encodings.
- Every representative deck decodes to 60 cards.
- 1,305 representative deck-list lines.
- 361 unique top-50 source set-number locators.
- 145 unique source locators occurring in the top ten.
- 4,194 combined top-ten entries out of 5,775 classified entries.
- 5,688 combined top-50 named entries out of 5,775 classified entries.

## Automated checks

- Python source compilation: passed.
- `scripts/validate_source.py`: passed.
- Unit tests: 11 passed.
- Synthetic `.apkg` compiler integration: passed for Pokémon, Trainer, Energy, and Set note models.

## Deferred network-backed checks

The artifact environment has no outbound network access. The coding agent must
run the TCGdex resolution/discovery steps locally, then inspect:

- unresolved locators;
- mechanical merge groups;
- same-name/different-mechanics groups;
- proposed origin keys;
- display-printing choices;
- final top-10/top-50 mechanical counts;
- media download/crop failures.

The build must not force the earlier approximate counts of 141 and 360.
