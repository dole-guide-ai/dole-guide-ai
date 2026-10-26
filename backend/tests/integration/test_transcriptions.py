import pytest
from fastapi.testclient import TestClient

from app.agent import gateway
from app.core.config import get_settings
from app.schemas.common import ErrorCode
from app.services import transcriptions as transcription_service

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def fresh_limiter(monkeypatch: pytest.MonkeyPatch) -> None:
    """테스트마다 계정별 횟수 제한을 새로 시작합니다(다른 테스트의 호출이 쌓이지 않게)."""
    monkeypatch.setattr(transcription_service, "_limiter", transcription_service._MinuteLimiter())


# 합성 녹음: 형식 서명만 맞춘 짧은 바이트
WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 32
M4A = b"\x00\x00\x00\x20ftypM4A " + b"\x00" * 32


@pytest.fixture
def heard(monkeypatch: pytest.MonkeyPatch) -> list[tuple[bytes, str]]:
    """실제 음성 인식 대신 받은 녹음을 기록하고 고정 글을 돌려줍니다."""
    calls: list[tuple[bytes, str]] = []

    def fake(content: bytes, file_name: str) -> str:
        calls.append((content, file_name))
        return "어제 OO물류에 지원했어요"

    monkeypatch.setattr(gateway, "transcribe_audio", fake)
    return calls


def send(client: TestClient, headers: dict[str, str], content: bytes):
    return client.post(
        "/accounts/park/transcriptions", headers=headers, files={"file": ("rec", content)}
    )


def test_recording_becomes_text(client: TestClient, entered_headers, heard):
    res = send(client, entered_headers("park"), WEBM)

    assert res.status_code == 200
    assert res.json() == {"text": "어제 OO물류에 지원했어요"}
    assert heard == [(WEBM, "voice.webm")]


def test_safari_recording_is_named_by_content(client: TestClient, entered_headers, heard):
    send(client, entered_headers("park"), M4A)

    assert heard[0][1] == "voice.m4a"


def test_not_audio_is_415(client: TestClient, entered_headers, heard):
    res = send(client, entered_headers("park"), b"%PDF-1.7\n" + b"0" * 32)

    assert res.status_code == 415
    assert res.json()["code"] == ErrorCode.UNSUPPORTED_FILE
    assert heard == []


def test_too_large_is_413(client: TestClient, entered_headers, heard, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_upload_mb", 0)

    res = send(client, entered_headers("park"), WEBM)

    assert res.status_code == 413
    assert heard == []


def test_without_stt_model_is_503(client: TestClient, entered_headers, monkeypatch):
    monkeypatch.setattr(get_settings(), "stt_model", "")

    res = send(client, entered_headers("park"), WEBM)

    assert res.status_code == 503
    assert res.json()["code"] == ErrorCode.LLM_UNAVAILABLE


def test_too_many_calls_in_a_minute_is_429(
    client: TestClient, entered_headers, heard, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(get_settings(), "stt_rate_limit_per_minute", 2)
    headers = entered_headers("park")
    # 형식이 틀린 요청은 횟수에 넣지 않음
    assert send(client, headers, b"not audio").status_code == 415

    codes = [send(client, headers, WEBM).status_code for _ in range(3)]

    assert codes == [200, 200, 429]
    assert len(heard) == 2


def test_foreign_hallucination_becomes_empty(
    client: TestClient, entered_headers, monkeypatch: pytest.MonkeyPatch
):
    # 잡음이 많으면 모델이 다른 언어 문장을 지어냄(평가 V-08·V-14) → 못 들은 것으로
    monkeypatch.setattr(gateway, "transcribe_audio", lambda content, name: "南風により")

    res = send(client, entered_headers("park"), WEBM)

    assert res.json() == {"text": ""}


def test_needs_entered_account(client: TestClient, heard):
    res = client.post("/accounts/park/transcriptions", files={"file": ("rec", WEBM)})

    assert res.status_code == 401
