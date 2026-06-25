"""Small cached TCGdex REST client used by the handoff scripts."""

from __future__ import annotations

import hashlib
import json
import random
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

from common import CACHE_DIR, utc_now_iso


class TCGdexError(RuntimeError):
    pass


class TCGdexClient:
    def __init__(
        self,
        *,
        language: str = "en",
        api_base: str = "https://api.tcgdex.net/v2",
        cache_dir: Path | None = None,
        timeout: float = 30.0,
        retries: int = 5,
        refresh: bool = False,
        user_agent: str = "ptcg-anki-handoff/2026-06-25",
    ) -> None:
        self.language = language
        self.api_base = api_base.rstrip("/")
        self.cache_dir = cache_dir or (CACHE_DIR / "tcgdex")
        self.timeout = timeout
        self.retries = retries
        self.refresh = refresh
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": user_agent,
            }
        )

    @property
    def base(self) -> str:
        return f"{self.api_base}/{self.language}"

    def _cache_path(self, url: str, params: dict[str, Any] | None) -> Path:
        key = url
        if params:
            key += "?" + urlencode(sorted((str(k), str(v)) for k, v in params.items()))
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.cache_dir / digest[:2] / f"{digest}.json"

    def get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        url = path if path.startswith("http") else f"{self.base}/{path.lstrip('/')}"
        cache_path = self._cache_path(url, params)
        if cache_path.exists() and not self.refresh:
            with cache_path.open("r", encoding="utf-8") as handle:
                wrapper = json.load(handle)
            return wrapper["payload"]

        last_error: Exception | None = None
        for attempt in range(self.retries):
            try:
                response = self.session.get(url, params=params, timeout=self.timeout)
                if response.status_code == 404:
                    raise TCGdexError(f"404 from {response.url}")
                if response.status_code == 429 or response.status_code >= 500:
                    raise TCGdexError(f"Transient HTTP {response.status_code} from {response.url}")
                response.raise_for_status()
                payload = response.json()
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                with cache_path.open("w", encoding="utf-8") as handle:
                    json.dump(
                        {
                            "url": response.url,
                            "fetched_at": utc_now_iso(),
                            "payload": payload,
                        },
                        handle,
                        ensure_ascii=False,
                        indent=2,
                    )
                    handle.write("\n")
                return payload
            except (requests.RequestException, ValueError, TCGdexError) as exc:
                last_error = exc
                if attempt + 1 >= self.retries:
                    break
                delay = min(20.0, (2**attempt) + random.random())
                time.sleep(delay)
        raise TCGdexError(f"Failed GET {url}: {last_error}") from last_error

    def list_sets(self) -> list[dict[str, Any]]:
        payload = self.get("sets")
        if not isinstance(payload, list):
            raise TCGdexError("Expected array from /sets")
        return payload

    def get_set(self, set_id: str) -> dict[str, Any]:
        payload = self.get(f"sets/{set_id}")
        if not isinstance(payload, dict):
            raise TCGdexError(f"Expected object for set {set_id}")
        return payload

    def get_card(self, card_id: str) -> dict[str, Any]:
        payload = self.get(f"cards/{card_id}")
        if not isinstance(payload, dict):
            raise TCGdexError(f"Expected object for card {card_id}")
        return payload

    def get_set_card(self, set_id: str, local_id: str) -> dict[str, Any]:
        payload = self.get(f"sets/{set_id}/{local_id}")
        if not isinstance(payload, dict):
            raise TCGdexError(f"Expected card object for {set_id}/{local_id}")
        return payload

    def find_cards_by_exact_name(self, name: str) -> list[dict[str, Any]]:
        payload = self.get("cards", params={"name": f"eq:{name}"})
        if not isinstance(payload, list):
            raise TCGdexError(f"Expected array while searching name {name!r}")
        return [item for item in payload if isinstance(item, dict)]
