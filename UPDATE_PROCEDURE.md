# Release-update procedure

Run this workflow after every expansion becomes tournament legal and after rotation.

1. Preserve the existing key registry and manual overrides.
2. Fetch the latest official legality/errata information.
3. Fetch the latest structured card/set data.
4. Recompute the complete English Standard mechanical pool.
5. Add genuinely new mechanical identities.
6. Link exact reprints to existing identities.
7. Recompute name ambiguity and `AutoDisplayLabel`.
8. Re-select newest suitable Standard-legal display printings.
9. Refresh the metagame snapshot from selected tournaments.
10. Replace current top-10/top-50/archetype tags.
11. Keep old snapshot tags only if historical analysis is desired; otherwise archive them.
12. Update Anki notes in place using stable keys/GUIDs.
13. Add new notes, never recreate unchanged notes.
14. Generate audit reports before packaging.

Typical mutable fields:

- `AutoDisplayLabel`;
- current images;
- legality metadata;
- archetype tags;
- top-10/top-50 tags;
- competitive role/rulings.

Stable fields:

- `CardKey` after registry assignment;
- note type identity and field order;
- deterministic internal GUID;
- mechanical fields unless corrected by errata/source repair.
