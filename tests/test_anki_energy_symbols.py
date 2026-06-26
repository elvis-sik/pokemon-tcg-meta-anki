from __future__ import annotations

from build_anki import (
    energy_cost,
    mechanic_text,
    meta_badges,
    provided_energy_types,
    retreat_icons,
)


def test_energy_cost_uses_symbols_not_visible_type_names() -> None:
    rendered = energy_cost(["Fighting", "Colorless"])

    assert "ptcg-energy-fighting" in rendered
    assert "ptcg-energy-colorless" in rendered
    assert "ptcg-energy-mark" in rendered
    assert "ptcg-energy-glyph" not in rendered
    assert ">Fighting<" not in rendered
    assert ">Colorless<" not in rendered


def test_mechanic_text_replaces_braced_energy_codes() -> None:
    rendered = mechanic_text("Attach a Basic {F} Energy to 1 of your {F} Pokémon.")

    assert "{F}" not in rendered
    assert rendered.count("ptcg-energy-fighting") == 2


def test_retreat_cost_renders_colorless_symbols() -> None:
    rendered = retreat_icons(3)

    assert rendered.count("ptcg-energy-colorless") == 3


def test_special_energy_provided_types_come_from_rules_text() -> None:
    mechanics = {
        "effect": "As long as this card is attached to a Pokémon, it provides {C} Energy."
    }

    assert provided_energy_types("Boomerang Energy", mechanics) == ["Colorless"]


def test_meta_badges_use_tournament_context() -> None:
    rendered = meta_badges(
        {
            "top10": True,
            "archetypes": ["Dragapult", "Mega Lucario", "Raging Bolt", "Slowking"],
            "source_locators": ["MEG-77", "ASC-113"],
        }
    )

    assert "Top 10 core" in rendered
    assert "4 archetypes" in rendered
    assert "Dragapult" in rendered
    assert "+1 more" in rendered
    assert "2 print locators" in rendered
