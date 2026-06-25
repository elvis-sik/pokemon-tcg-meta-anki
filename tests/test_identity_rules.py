from common import compute_display_label, mechanical_fingerprint, natural_card_key


def pokemon_payload(name: str, damage: str = "30") -> dict:
    return {
        "category": "Pokemon",
        "name": name,
        "hp": 70,
        "types": ["Lightning"],
        "stage": "Basic",
        "attacks": [
            {"name": "Zap", "cost": ["Lightning"], "damage": damage, "effect": ""}
        ],
        "weaknesses": [{"type": "Fighting", "value": "x2"}],
        "retreat": 1,
    }


def test_exact_reprints_share_fingerprint() -> None:
    first = pokemon_payload("Pikachu")
    second = {**first, "id": "unrelated-print-id", "image": "https://example.invalid/a"}
    assert mechanical_fingerprint(first) == mechanical_fingerprint(second)


def test_same_name_different_mechanics_are_distinct() -> None:
    assert mechanical_fingerprint(pokemon_payload("Pikachu", "30")) != mechanical_fingerprint(
        pokemon_payload("Pikachu", "40")
    )


def test_different_names_are_distinct_even_with_same_text() -> None:
    assert mechanical_fingerprint(pokemon_payload("Pikachu")) != mechanical_fingerprint(
        pokemon_payload("Raichu")
    )


def test_name_only_when_unique_in_standard() -> None:
    assert (
        compute_display_label(
            name="Fezandipiti ex",
            standard_mechanical_identity_count=1,
            display_set_code="SFA",
            display_collector_number="38",
        )
        == "Fezandipiti ex"
    )


def test_ambiguous_name_gets_set_and_number() -> None:
    assert (
        compute_display_label(
            name="Pikachu ex",
            standard_mechanical_identity_count=2,
            display_set_code="PRE",
            display_collector_number="28",
        )
        == "Pikachu ex · PRE 28"
    )


def test_override_wins() -> None:
    assert (
        compute_display_label(
            name="Budew",
            standard_mechanical_identity_count=3,
            display_set_code="PRE",
            display_collector_number="4",
            override="Itchy Pollen Budew",
        )
        == "Itchy Pollen Budew"
    )


def test_natural_key_is_readable() -> None:
    assert natural_card_key("Pikachu ex", "SSP", "57") == "Pikachu ex · SSP 57"
