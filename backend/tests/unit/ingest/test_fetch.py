"""요청 함수: 네트워크 없이 httpx.MockTransport로 확인합니다."""

import httpx
import pytest

from scripts.ingest.fetch import MAX_ATTEMPTS, USER_AGENT, Fetcher


def _fetcher(handler) -> tuple[Fetcher, list[float]]:
    sleeps: list[float] = []
    client = httpx.Client(
        transport=httpx.MockTransport(handler), headers={"User-Agent": USER_AGENT}
    )
    return Fetcher(client=client, delay=1.0, sleep=sleeps.append), sleeps


def test_get_waits_between_requests_and_sends_user_agent():
    agents = []

    def handler(request: httpx.Request) -> httpx.Response:
        agents.append(request.headers["User-Agent"])
        return httpx.Response(200, text="ok")

    fetcher, sleeps = _fetcher(handler)

    assert fetcher.get("https://example.test/a") == "ok"
    assert fetcher.get("https://example.test/b", {"page": 2}) == "ok"
    assert sleeps == [1.0]
    assert agents == [USER_AGENT, USER_AGENT]


def test_get_retries_then_succeeds():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(503 if len(calls) < 3 else 200, text="ok")

    fetcher, sleeps = _fetcher(handler)

    assert fetcher.get("https://example.test") == "ok"
    assert len(calls) == 3
    assert sleeps == [2.0, 1.0, 4.0, 1.0]


def test_get_gives_up_after_max_attempts():
    fetcher, _ = _fetcher(lambda request: httpx.Response(500))

    with pytest.raises(RuntimeError, match=f"{MAX_ATTEMPTS}번"):
        fetcher.get("https://example.test")
