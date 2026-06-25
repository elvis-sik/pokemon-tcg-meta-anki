# Coding-agent brief

Build a reproducible Anki deck from this handoff. Treat the checked-in CSV/JSON files as frozen source inputs and generated files as replaceable outputs.

## Non-negotiable design decisions

1. One Anki note per **mechanically distinct** gameplay card.
2. Separate Anki note types for Pokémon, Trainer, and Energy.
3. Exactly one review card per gameplay note.
4. No UUID field visible in Anki.
5. First field is a stable natural key:
   `ExactName · OriginSetCode OriginCollectorNumber`.
6. The natural key uses the earliest known English printing of the mechanical identity and is frozen after assignment.
7. Current artwork/full-card images use the newest suitable Standard-legal regular printing.
8. The key and current display printing are independent.
9. Front: current player-facing label + artwork crop.
10. Back: full-card image + complete structured mechanics rendered in HTML.
11. No API calls at Anki review time.
12. The source/build layer may model printings; the Anki collection must not expose a printing collection or printing notes.
13. Dynamic label rule:
    - one Standard-legal mechanical identity with the exact name → name only;
    - more than one → `Name · DisplaySetCode DisplayCollectorNumber`;
    - a manual override wins.
14. Name ambiguity is computed against the full current English Standard mechanical pool, not only this study subset.
15. Exact reprints do not create name ambiguity.
16. Same-name cards with different gameplay mechanics do create ambiguity.
17. Every resolved top-50 note gets `ptcg::meta::2026_06::top50`.
18. A resolved note gets `ptcg::meta::2026_06::top10` if any merged source locator came from archetype ranks 1–10.
19. Archetype tags are unioned across all merged source locators.
20. Do not force the final count to 141 or 360.

## Deliverables

- A clean Python project or equivalent implementation.
- Cached raw card JSON for reproducibility.
- A normalized printing table.
- A mechanically deduplicated card table.
- A merge/audit report.
- Downloaded full-card media and generated artwork crops.
- The final `.apkg`.
- A release-update command that updates tags/data without resetting Anki scheduling.
- Automated tests for all key identity and label rules.

## Required audit outputs

At minimum:

```text
reports/resolution_failures.csv
reports/mechanical_merge_groups.csv
reports/ambiguous_standard_names.csv
reports/image_selection.csv
reports/media_failures.csv
reports/final_counts.json
reports/validation_report.md
```

`final_counts.json` must separately report:

- source locators: top10 and top50;
- resolved printings;
- mechanical identities: top10 and top50;
- unresolved source locators;
- exact-reprint merges;
- same-name/different-mechanics groups.

## Implementation order

1. Validate frozen deck encodings.
2. Resolve set codes to TCGdex set IDs.
3. Fetch structured card data with caching and retry/backoff.
4. Normalize card objects.
5. Compute mechanical fingerprints.
6. Review/merge fingerprint groups and manual overrides.
7. Assign/freeze natural keys.
8. Fetch the full current Standard pool to compute name ambiguity.
9. Choose newest suitable regular Standard printing for display media.
10. Generate labels and tags.
11. Download/crop media.
12. build and validate the `.apkg`.
