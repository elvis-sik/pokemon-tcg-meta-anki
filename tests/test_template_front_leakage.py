from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_gameplay_fronts_are_label_and_art_only() -> None:
    for name in ["pokemon_front.html", "trainer_front.html", "energy_front.html"]:
        template = (ROOT / "templates" / name).read_text(encoding="utf-8")

        assert "ptcg-kicker" not in template
        assert "DisplaySetCode" not in template
        assert "DisplayCollectorNumber" not in template
        assert "data-type=" not in template
        assert "data-trainer=" not in template
        assert "data-energy=" not in template
