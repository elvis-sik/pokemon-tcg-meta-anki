from __future__ import annotations

from crop_artwork import DEFAULT_PROFILES, POKEMON_EX_PROFILE, profile_for


def test_trainer_default_starts_below_title_band() -> None:
    x, y, width, height = DEFAULT_PROFILES["Trainer"]

    assert x == 0.075
    assert y >= 0.14
    assert width == 0.850
    assert y + height <= 0.53


def test_pokemon_ex_uses_lower_full_art_crop() -> None:
    profile, source = profile_for(
        "Beedrill ex · CRI 003",
        {"category": "Pokemon", "name": "Beedrill ex", "normalized_mechanics": {}},
        {},
    )

    assert profile == POKEMON_EX_PROFILE
    assert source == "derived_Pokemon_ex"


def test_manual_override_wins_over_derived_profile() -> None:
    manual = (0.1, 0.2, 0.3, 0.4)

    profile, source = profile_for(
        "Ceruledge ex · SSP 036",
        {"category": "Pokemon", "name": "Ceruledge ex", "normalized_mechanics": {}},
        {"Ceruledge ex · SSP 036": manual},
    )

    assert profile == manual
    assert source == "manual"
