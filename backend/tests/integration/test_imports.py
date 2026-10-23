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


def test_lee_applies_job_application_and_round_is_satisfied(
    client: TestClient, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    """F-10 완료 기준: 이정호가 OO물산 1건을 고르면 활동에 들어가고, 다시 고르면 넣지 않습니다."""
    headers = entered_headers("lee")
    url = "/accounts/lee/imports"

    res = client.post(f"{url}/apply", headers=headers, json={"import_ids": ["wa_003"]})

    assert res.status_code == 200, res.text
    added = res.json()["updates"][0]["value"]
    assert (added["org_name"], added["source"], added["route"]) == ("OO물산", "import", "work24")
    check = next(u["value"] for u in res.json()["updates"] if u["path"] == "/round_check")
    assert check["check_status"] == "satisfied"
    items = client.get(f"{url}/job-applications", headers=headers).json()["items"]
    assert all(item["is_recorded"] for item in items)
    again = client.post(f"{url}/apply", headers=headers, json={"import_ids": ["wa_003"]})
    assert again.status_code == 409


def test_park_applies_career_and_license_to_resume(
    client: TestClient, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    headers = entered_headers("park")

    res = client.post(
        "/accounts/park/imports/apply",
        headers=headers,
        json={"import_ids": ["cc_career_001", "cc_license_001"]},
    )

    assert res.status_code == 200, res.text
    resume = client.get("/accounts/park/resume", headers=headers).json()["data"]
    career = resume["careers"][0]
    assert (career["company_name"]["value"], career["start_date"]["value"]) == ("OO산업", "2004-03")
    assert career["company_name"]["source"] == "import"
    assert resume["certifications"][0]["acquired_date"]["value"] == "2011-05-20"
    training = client.post(
        "/accounts/park/imports/apply", headers=headers, json={"import_ids": ["cc_training_001"]}
    )
    missing = client.post(
        "/accounts/park/imports/apply", headers=headers, json={"import_ids": ["nope"]}
    )
    assert training.status_code == 422
    assert missing.status_code == 404
