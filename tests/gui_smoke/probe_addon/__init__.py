"""Visual smoke probe for the Pokemon TCG Anki deck."""

from __future__ import annotations

import json
import os
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aqt
from aqt import gui_hooks
from aqt.qt import QSize, QTimer
from aqt.webview import AnkiWebView

RESULT_ENV = "ANKI_ADDON_WORKBENCH_RESULT"
SCREENSHOT_ENV = "ANKI_ADDON_WORKBENCH_SCREENSHOT"
FIELD_SEPARATOR = "\x1f"
SETTLE_MS = 950
VIEWPORT = QSize(900, 1180)
MAX_START_ATTEMPTS = 60
_renderer: PreviewRenderer | None = None
_start_attempts = 0


@dataclass(frozen=True)
class PreviewJob:
    slug: str
    note_key: str
    side: str
    card_ord: int = 0


JOBS = (
    PreviewJob("pokemon-mega-front", "Mega Lucario ex · MEP 012", "question"),
    PreviewJob("pokemon-mega-back", "Mega Lucario ex · MEP 012", "answer"),
    PreviewJob("trainer-back", "Lillie's Determination · MEG 119", "answer"),
    PreviewJob("energy-back", "Fire Energy · BS 98", "answer"),
    PreviewJob("set-front", "MEG", "question", card_ord=0),
    PreviewJob("set-back", "MEG", "answer", card_ord=0),
)


def _output_root() -> Path:
    screenshot = os.environ.get(SCREENSHOT_ENV)
    if screenshot:
        root = Path(screenshot)
    else:
        result = Path(os.environ.get(RESULT_ENV) or "ptcg-preview.json")
        root = result.with_name("ptcg-preview.png")
    root.parent.mkdir(parents=True, exist_ok=True)
    return root


def _mw() -> Any:
    return aqt.mw


def _find_card_id(note_key: str, card_ord: int) -> int | None:
    window = _mw()
    if window is None or window.col is None:
        return None
    rows = window.col.db.all(
        """
        select c.id, c.ord, n.flds
        from cards c
        join notes n on n.id = c.nid
        order by c.id
        """
    )
    for card_id, ord_value, fields_blob in rows:
        fields = str(fields_blob).split(FIELD_SEPARATOR)
        if fields and fields[0] == note_key and int(ord_value) == card_ord:
            return int(card_id)
    return None


class PreviewRenderer:
    def __init__(self, jobs: tuple[PreviewJob, ...], root: Path) -> None:
        self.jobs = jobs
        self.root = root
        self.index = 0
        self.web = AnkiWebView(_mw(), title="PTCG visual preview")
        self.web.resize(VIEWPORT)
        self.web.setMinimumSize(VIEWPORT)
        self.web.show()
        self.previews: list[dict[str, Any]] = []
        self.failures: list[dict[str, str]] = []

    def start(self) -> None:
        QTimer.singleShot(0, self._render_next)

    def _render_next(self) -> None:
        if self.index >= len(self.jobs):
            self._finish()
            return

        job = self.jobs[self.index]
        self.index += 1
        card_id = _find_card_id(job.note_key, job.card_ord)
        if card_id is None:
            self.failures.append({"job": job.slug, "error": f"missing note {job.note_key}"})
            QTimer.singleShot(0, self._render_next)
            return

        try:
            card = _mw().col.get_card(card_id)
            body = card.question(reload=True) if job.side == "question" else card.answer()
            self.web.stdHtml(
                body,
                css=["css/reviewer.css"],
                js=["js/mathjax.js", "js/vendor/mathjax/tex-chtml-full.js", "js/reviewer.js"],
            )
            QTimer.singleShot(SETTLE_MS, lambda: self._capture(job, card_id))
        except Exception as exc:
            self.failures.append({"job": job.slug, "error": str(exc)})
            QTimer.singleShot(0, self._render_next)

    def _capture(self, job: PreviewJob, card_id: int) -> None:
        path = self.root.with_name(f"{self.root.stem}__{job.slug}.png")
        pixmap = self.web.grab()
        ok = bool(pixmap.save(str(path), "PNG"))
        if not ok:
            self.failures.append({"job": job.slug, "error": f"failed to save {path}"})
        else:
            self.previews.append(
                {
                    "job": job.slug,
                    "note_key": job.note_key,
                    "side": job.side,
                    "card_id": card_id,
                    "path": str(path),
                    "width": int(pixmap.width()),
                    "height": int(pixmap.height()),
                }
            )
        QTimer.singleShot(0, self._render_next)

    def _finish(self) -> None:
        payload = run_checks(self.previews, self.failures)
        _write_result(payload)
        if _mw() is not None:
            _mw().unloadProfileAndExit()


def run_checks(
    previews: list[dict[str, Any]] | None = None,
    failures: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    window = _mw()
    if window is None or window.col is None:
        return {"ok": False, "error": "Anki main window or collection is unavailable"}
    previews = previews or []
    failures = failures or []
    card_count = int(window.col.card_count() or 0)
    note_count = int(window.col.note_count() or 0)
    return {
        "ok": card_count > 0 and note_count > 0 and len(previews) == len(JOBS) and not failures,
        "probe": "ptcg_visual_preview",
        "checks": [
            {"name": "collection has cards", "ok": card_count > 0, "count": card_count},
            {"name": "collection has notes", "ok": note_count > 0, "count": note_count},
            {
                "name": "preview screenshots rendered",
                "ok": len(previews) == len(JOBS) and not failures,
                "rendered": len(previews),
                "expected": len(JOBS),
                "failures": failures,
            },
        ],
        "collection": {"cards": card_count, "notes": note_count},
        "previews": previews,
    }


def _write_result(payload: dict[str, Any]) -> None:
    result_path = os.environ.get(RESULT_ENV)
    if result_path:
        Path(result_path).write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )


def _start() -> None:
    global _renderer, _start_attempts
    if _renderer is not None:
        return
    window = _mw()
    if window is None or window.col is None:
        _start_attempts += 1
        if _start_attempts >= MAX_START_ATTEMPTS:
            _write_result({"ok": False, "error": "Anki collection was not ready for preview"})
            return
        QTimer.singleShot(250, _start)
        return
    try:
        _renderer = PreviewRenderer(JOBS, _output_root())
        _renderer.start()
    except Exception as exc:
        _write_result({"ok": False, "error": str(exc), "traceback": traceback.format_exc()})
        if _mw() is not None:
            _mw().unloadProfileAndExit()


gui_hooks.profile_did_open.append(lambda: QTimer.singleShot(500, _start))
gui_hooks.main_window_did_init.append(lambda: QTimer.singleShot(500, _start))
QTimer.singleShot(1000, _start)
