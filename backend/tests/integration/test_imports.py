from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def _recorded(body: dict) -> dict[str, bool]:
    return {item["values"]["title"]: item["is_recorded"] for item in body["items"]}


def test_choi_career_marks_resume_items_recorded(
    client: TestClient, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    headers = entered_headers("choi")

    res = client.get("/accounts/choi/imports/career-certificates", headers=headers)

    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 3
    assert body["source_note"]
    assert _recorded(body) == {"OO빌딩": False, "OO아파트 관리사무소": True, "전기기능사": True}


def test_park_career_has_nothing_recorded(
    client: TestClient, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    headers = entered_headers("park")

    body = client.get("/accounts/park/imports/career-certificates", headers=headers).json()

    assert [item["import_id"] for item in body["items"]] == [
        "cc_career_001",
        "cc_license_001",
        "cc_training_001",
    ]
    assert not any(item["is_recorded"] for item in body["items"])
    assert body["items"][0]["values"]["category"] == "career"


def test_lee_job_applications_mark_recorded_activity(
    client: TestClient, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    headers = entered_headers("lee")

    res = client.get("/accounts/lee/imports/job-applications", headers=headers)

    assert res.status_code == 200
    items = {item["import_id"]: item for item in res.json()["items"]}
    assert items["wa_001"]["is_recorded"] is True
    assert items["wa_001"]["values"]["date"] == "2026-10-13"
    assert items["wa_003"]["is_recorded"] is False
    assert items["wa_003"]["values"]["date"] == "2026-10-21"


def test_imports_need_token_and_entered_account(
    client: TestClient, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    assert client.get("/accounts/lee/imports/job-applications").status_code == 401

    headers = entered_headers("park")
    res = client.get("/accounts/lee/imports/job-applications", headers=headers)

    assert res.status_code == 404
    assert res.json()["code"] == "ACCOUNT_NOT_FOUND"
