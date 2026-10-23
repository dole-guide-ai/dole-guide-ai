"""구직활동 증빙 보관·연결·열기 (F-21).

이정호 OO상사(기업 홈페이지 지원, 증빙 필요)에 캡처를 붙이면 증빙 있음이 되고, 신청서 줄에서
파일을 열 수 있으며 다른 방문자는 404입니다.
"""

from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings

pytestmark = pytest.mark.integration

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
ACTIVITIES = "/accounts/lee/activities"
Headers = Callable[[str], dict[str, str]]


@pytest.fixture(autouse=True)
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(get_settings(), "upload_dir", str(tmp_path))
    return tmp_path


def _upload(client: TestClient, headers: dict[str, str]) -> str:
    res = client.post(
        "/accounts/lee/files",
        headers=headers,
        files={"file": ("캡처.png", PNG)},
        data={"purpose": "evidence"},
    )
    assert res.status_code == 201, res.text
    return res.json()["file_id"]


def _check(res) -> dict:
    return next(u["value"] for u in res.json()["updates"] if u["path"] == "/round_check")


def test_attach_evidence_then_open_from_application(client: TestClient, entered_headers: Headers):
    headers = entered_headers("lee")
    trading = next(
        a
        for a in client.get(ACTIVITIES, headers=headers).json()["items"]
        if a["org_name"] == "OO상사"
    )
    url = f"{ACTIVITIES}/{trading['activity_id']}"
    file_id = _upload(client, headers)

    attached = client.patch(
        url, headers=headers, json=[{"op": "add", "path": "/file_ids/-", "value": file_id}]
    )

    assert attached.status_code == 200, attached.text
    row = next(
        a for a in _check(attached)["activities"] if a["activity_id"] == trading["activity_id"]
    )
    assert row["has_evidence"] is True
    assert "W5" not in {w["id"] for w in _check(attached)["warnings"]}
    listed = client.get(ACTIVITIES, headers=headers).json()["items"]
    assert next(a for a in listed if a["org_name"] == "OO상사")["file_ids"] == [file_id]
    assert client.get(f"/accounts/lee/files/{file_id}", headers=headers).status_code == 200
    assert (
        client.get(f"/accounts/lee/files/{file_id}", headers=entered_headers("lee")).status_code
        == 404
    )

    detached = client.patch(
        url, headers=headers, json=[{"op": "remove", "path": f"/file_ids/{file_id}"}]
    )
    assert "W5" in {w["id"] for w in _check(detached)["warnings"]}


def test_cannot_attach_someone_elses_file(client: TestClient, entered_headers: Headers):
    other = _upload(client, entered_headers("lee"))
    headers = entered_headers("lee")
    activity_id = client.get(ACTIVITIES, headers=headers).json()["items"][0]["activity_id"]

    res = client.patch(
        f"{ACTIVITIES}/{activity_id}",
        headers=headers,
        json=[{"op": "add", "path": "/file_ids/-", "value": other}],
    )

    assert res.status_code == 404
