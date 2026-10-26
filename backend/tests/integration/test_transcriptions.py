import pytest
from fastapi.testclient import TestClient

from app.agent import gateway
from app.core.config import get_settings
from app.schemas.common import ErrorCode

pytestmark = pytest.mark.integration

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


def test_needs_entered_account(client: TestClient, heard):
    res = client.post("/accounts/park/transcriptions", files={"file": ("rec", WEBM)})

    assert res.status_code == 401
