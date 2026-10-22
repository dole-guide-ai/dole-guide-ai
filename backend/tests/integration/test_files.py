from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.services import files as file_service

pytestmark = pytest.mark.integration

# 합성 파일: 형식 서명만 맞춘 짧은 바이트
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
PDF = b"%PDF-1.7\n" + b"0" * 32
DOCX = b"PK\x03\x04" + b"\x00" * 32


@pytest.fixture(autouse=True)
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(get_settings(), "upload_dir", str(tmp_path))
    return tmp_path


def upload(client: TestClient, headers: dict[str, str], name: str, content: bytes, **extra):
    return client.post(
        "/accounts/park/files",
        headers=headers | extra.pop("more_headers", {}),
        files={"file": (name, content)},
        data={"purpose": extra.pop("purpose", "evidence")},
    )


def test_upload_then_open_own_file(client: TestClient, entered_headers, upload_dir: Path):
    headers = entered_headers("park")

    res = upload(client, headers, "면접확인서.png", PNG)

    assert res.status_code == 201
    body = res.json()
    assert body["file_name"] == "면접확인서.png"
    assert body["mime_type"] == "image/png"
    assert body["size"] == len(PNG)
    assert len(list(upload_dir.glob(f"*/{body['file_id']}"))) == 1

    opened = client.get(f"/accounts/park/files/{body['file_id']}", headers=headers)
    assert opened.status_code == 200
    assert opened.content == PNG
    assert opened.headers["content-type"] == "image/png"
    assert opened.headers["x-content-type-options"] == "nosniff"
    assert opened.headers["content-disposition"].startswith("inline")


def test_other_visitor_cannot_open_file(client: TestClient, entered_headers):
    file_id = upload(client, entered_headers("park"), "a.pdf", PDF).json()["file_id"]

    res = client.get(f"/accounts/park/files/{file_id}", headers=entered_headers("park"))

    assert res.status_code == 404
    assert res.json()["code"] == "NOT_FOUND"


@pytest.mark.parametrize("file_id", ["not-a-uuid", "00000000-0000-0000-0000-000000000000"])
def test_unknown_file_is_404(client: TestClient, entered_headers, file_id: str):
    res = client.get(f"/accounts/park/files/{file_id}", headers=entered_headers("park"))

    assert res.status_code == 404


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("script.exe", b"MZ" + b"\x00" * 32),  # 허용 안 하는 확장자
        ("photo.png", b"MZ" + b"\x00" * 32),  # 이름만 바꾼 파일
        ("report.pdf", PNG),  # 확장자와 내용이 다름
        ("noext", PNG),
        ("empty.png", b""),
    ],
)
def test_rejects_unsupported_file(client: TestClient, entered_headers, name, content):
    res = upload(client, entered_headers("park"), name, content)

    assert res.status_code == 415
    assert res.json()["code"] == "UNSUPPORTED_FILE"


def test_accepts_docx_as_resume_doc(client: TestClient, entered_headers):
    res = upload(client, entered_headers("park"), "이력서.docx", DOCX, purpose="resume_doc")

    assert res.status_code == 201
    assert res.json()["mime_type"].endswith("wordprocessingml.document")


def test_rejects_too_large(client: TestClient, entered_headers, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(get_settings(), "max_upload_mb", 1)
    content = PNG + b"\x00" * (1024 * 1024)

    res = upload(client, entered_headers("park"), "big.png", content)

    assert res.status_code == 413
    assert res.json()["code"] == "FILE_TOO_LARGE"


def test_path_in_file_name_is_dropped(client: TestClient, entered_headers, upload_dir: Path):
    res = upload(client, entered_headers("park"), "../../etc/evil.png", PNG)

    assert res.status_code == 201
    assert res.json()["file_name"] == "evil.png"
    assert not (upload_dir.parent / "etc").exists()


def test_same_idempotency_key_replays(client: TestClient, entered_headers, upload_dir: Path):
    headers = entered_headers("park")
    key = {"Idempotency-Key": "upload-1"}

    first = upload(client, headers, "a.png", PNG, more_headers=key)
    again = upload(client, headers, "a.png", PNG, more_headers=key)
    other = upload(client, headers, "b.pdf", PDF, more_headers=key)

    assert first.json() == again.json()
    assert len(list(upload_dir.glob("*/*"))) == 1
    assert other.status_code == 409
    assert other.json()["code"] == "IDEMPOTENCY_MISMATCH"


def test_delete_account_removes_files(client: TestClient, entered_headers, upload_dir: Path):
    headers = entered_headers("park")
    upload(client, headers, "a.png", PNG)

    client.delete("/accounts/park", headers=headers)

    assert list(upload_dir.glob("*/*")) == []


def test_same_key_with_different_name_is_conflict(client: TestClient, entered_headers):
    headers = entered_headers("park")
    key = {"Idempotency-Key": "upload-name"}

    upload(client, headers, "a.png", PNG, more_headers=key)
    other = upload(client, headers, "b.png", PNG, more_headers=key)

    assert other.status_code == 409
    assert other.json()["code"] == "IDEMPOTENCY_MISMATCH"


def test_written_file_is_removed_when_save_fails(
    client: TestClient, entered_headers, upload_dir: Path, monkeypatch: pytest.MonkeyPatch
):
    def failing_run_once(db, user_id, key, body, model, create, **_):
        create()  # 실물과 행을 쓴 뒤
        raise RuntimeError("synthetic commit failure")  # commit에서 실패한 상황

    monkeypatch.setattr(file_service, "run_once", failing_run_once)
    test_client = TestClient(client.app, raise_server_exceptions=False)

    res = upload(test_client, entered_headers("park"), "a.png", PNG)

    assert res.status_code == 500
    assert list(upload_dir.glob("*/*")) == []


def test_loser_of_concurrent_same_key_removes_its_file(
    client: TestClient, entered_headers, upload_dir: Path, monkeypatch: pytest.MonkeyPatch
):
    winner = {"file_id": "00000000-0000-0000-0000-000000000001", "file_name": "a.png",
              "mime_type": "image/png", "size": len(PNG)}  # fmt: skip

    def replay_winner(db, user_id, key, body, model, create, **_):
        create()  # 이번 요청도 실물을 썼지만
        return model.model_validate(winner)  # 먼저 끝난 요청의 결과를 돌려받음

    monkeypatch.setattr(file_service, "run_once", replay_winner)

    res = upload(client, entered_headers("park"), "a.png", PNG)

    assert res.json()["file_id"] == winner["file_id"]
    assert list(upload_dir.glob("*/*")) == []
