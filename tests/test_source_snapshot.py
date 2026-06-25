from collections import defaultdict

from common import DATA_DIR, read_csv, read_json
from decode_limitless_builder import decode_builder


def test_frozen_snapshot_counts() -> None:
    top50 = read_csv(DATA_DIR / "card_source_locators_top50_361.csv")
    top10 = read_csv(DATA_DIR / "card_source_locators_top10_145.csv")
    decks = read_json(DATA_DIR / "representative_decks.json")
    assert len(top50) == 361
    assert len(top10) == 145
    assert len(decks) == 50


def test_every_representative_deck_is_sixty_cards() -> None:
    for deck in read_json(DATA_DIR / "representative_decks.json"):
        encoding = deck.get("limitless_builder_encoding") or deck.get("builder")
        assert sum(quantity for quantity, _, _ in decode_builder(encoding)) == 60


def test_top10_locators_are_subset_of_top50() -> None:
    top50 = {row["raw_locator"] for row in read_csv(DATA_DIR / "card_source_locators_top50_361.csv")}
    top10 = {row["raw_locator"] for row in read_csv(DATA_DIR / "card_source_locators_top10_145.csv")}
    assert top10 < top50


def test_every_occurrence_has_archetype_tag() -> None:
    rows = read_csv(DATA_DIR / "card_locator_archetype_membership.csv")
    assert rows
    for row in rows:
        assert row["archetype"]
        assert row["archetype_tag"].startswith("ptcg::archetype::")
        assert row["meta_tag_top50"] == "ptcg::meta::2026_06::top50"
