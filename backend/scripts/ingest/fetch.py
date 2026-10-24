"""공공 사이트 요청 공통 함수: 요청 간 지연, 재시도, User-Agent, 수집 기록."""

import json
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import httpx

from scripts.ingest import paths

USER_AGENT = "dole-guide-ai/0.1 (public-data research crawler; github.com/dole-guide-ai)"
DELAY_SECONDS = 1.0
MAX_ATTEMPTS = 3


class Fetcher:
    """요청 사이에 delay초를 쉬고, 실패하면 최대 MAX_ATTEMPTS번까지 다시 시도합니다."""

    def __init__(
        self,
        client: httpx.Client | None = None,
        delay: float = DELAY_SECONDS,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.client = client or httpx.Client(
            headers={"User-Agent": USER_AGENT}, timeout=30.0, follow_redirects=True
        )
        self.delay = delay
        self.sleep = sleep
        self._last_request: float | None = None

    def get(self, url: str, params: dict[str, str | int] | None = None) -> str:
        last_error: Exception | None = None
        for attempt in range(MAX_ATTEMPTS):
            self._wait()
            try:
                response = self.client.get(url, params=params)
                response.raise_for_status()
                return response.text
            except httpx.HTTPError as error:
                last_error = error
                if attempt < MAX_ATTEMPTS - 1:
                    self.sleep(self.delay * 2 ** (attempt + 1))
        raise RuntimeError(f"{MAX_ATTEMPTS}번 시도했지만 실패했습니다: {url}") from last_error

    def _wait(self) -> None:
        if self._last_request is not None:
            self.sleep(self.delay)
        self._last_request = time.monotonic()


def save_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def save_json(path: Path, data: object) -> None:
    save_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def record(source: str, item_id: str, url: str, ok: bool, error: str | None = None) -> None:
    """crawl_manifest.json에 항목별 수집 결과를 남깁니다."""
    manifest = load_json(paths.MANIFEST)
    manifest.setdefault(source, {})[item_id] = {
        "url": url,
        "ok": ok,
        "error": error,
        "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    save_json(paths.MANIFEST, manifest)
