from collections.abc import Callable
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.clock import get_now
from app.main import app
from app.models import Resume, Work24Import
from app.schemas.imports import ImportCategory
from conftest import TEST_NOW

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
    assert body["total"] == 4
    assert body["source_note"]
    assert _recorded(body) == {
        "OO에이전시": False,
        "OO웹솔루션": True,
        "웹디자인기능사": False,
        "정보처리기사": True,
    }


def _reenter_without_imports(
    client: TestClient, db_session: Session, headers: dict[str, str]
) -> dict:
    """불러오기 테이블(0003)보다 먼저 만든 계정처럼 목록을 비우고 며칠 뒤 다시 입장합니다.

    6일 뒤(방문자 유효 기간 7일 안)면 그날 기준 이직월은 처음 입장일 기준과 다른 달입니다.
    """
    db_session.execute(delete(Work24Import))
    db_session.flush()
    later = TEST_NOW + timedelta(days=6)
    app.dependency_overrides[get_now] = lambda: later
    assert client.put("/accounts/choi", headers=headers).status_code == 200
    return client.get("/accounts/choi/imports/career-certificates", headers=headers).json()


def test_backfill_uses_account_anchor_and_keeps_items_in_resume_recorded(
    client: TestClient, db_session: Session, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    headers = entered_headers("choi")
    fresh = client.get("/accounts/choi/imports/career-certificates", headers=headers).json()

    body = _reenter_without_imports(client, db_session, headers)

    # 퇴사월 등 seed 날짜는 다시 입장한 날이 아니라 처음 입장일(anchor) 기준입니다.
    assert body["items"] == fresh["items"]


def test_backfill_unmarks_seed_items_missing_from_resume(
    client: TestClient, db_session: Session, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    headers = entered_headers("choi")
    # 예전 seed로 만든 계정처럼 지금 seed의 '이미 넣음' 항목이 이력서에 없습니다.
    db_session.execute(delete(Resume))

    body = _reenter_without_imports(client, db_session, headers)

    assert not any(item["is_recorded"] for item in body["items"])


def test_park_career_has_nothing_recorded(
    client: TestClient, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    headers = entered_headers("park")

    body = client.get("/accounts/park/imports/career-certificates", headers=headers).json()

    assert [item["import_id"] for item in body["items"]] == [
        "cc_career_001",
        "cc_career_002",
        "cc_license_001",
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
    expected = ("OO물산", "work24_import", "work24")
    assert (added["org_name"], added["source"], added["route"]) == expected
    check = next(u["value"] for u in res.json()["updates"] if u["path"] == "/round_check")
    assert check["check_status"] == "satisfied"
    items = client.get(f"{url}/job-applications", headers=headers).json()["items"]
    assert all(item["is_recorded"] for item in items)
    again = client.post(f"{url}/apply", headers=headers, json={"import_ids": ["wa_003"]})
    assert again.status_code == 409


def test_park_applies_career_and_license_to_resume(
    client: TestClient, db_session, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    from sqlalchemy import select

    headers = entered_headers("park")
    # 시연 목록에는 직업훈련이 없어서(대화로 받음) 거절 경로를 보려고 한 줄 넣습니다.
    license_row = db_session.scalars(
        select(Work24Import).where(Work24Import.source_id == "cc_license_001")
    ).one()
    db_session.add(
        Work24Import(
            user_id=license_row.user_id,
            source_id="cc_training_001",
            kind=license_row.kind,
            category=ImportCategory.TRAINING,
            title="용접 기초 과정",
            detail="직업훈련 이수 · 2009.03 ~ 2009.06",
            position=9,
        )
    )
    db_session.flush()

    res = client.post(
        "/accounts/park/imports/apply",
        headers=headers,
        json={"import_ids": ["cc_career_001", "cc_license_001"]},
    )

    assert res.status_code == 200, res.text
    resume = client.get("/accounts/park/resume", headers=headers).json()["data"]
    career = resume["careers"][0]
    assert (career["company_name"]["value"], career["start_date"]["value"]) == ("OO산업", "2004-03")
    assert career["company_name"]["source"] == "work24_import"
    assert resume["certifications"][0]["acquired_date"]["value"] == "2011-05-20"
    training = client.post(
        "/accounts/park/imports/apply", headers=headers, json={"import_ids": ["cc_training_001"]}
    )
    missing = client.post(
        "/accounts/park/imports/apply", headers=headers, json={"import_ids": ["nope"]}
    )
    assert training.status_code == 422
    assert missing.status_code == 404


def test_old_account_gets_import_rows_on_enter(
    client: TestClient, db_session, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    """불러오기 테이블보다 먼저 만든 계정도 다시 입장하면 목록이 생깁니다."""

    from app.models import Work24Import

    headers = entered_headers("park")
    db_session.execute(delete(Work24Import))
    db_session.flush()

    assert client.put("/accounts/park", headers=headers).status_code == 200
    body = client.get("/accounts/park/imports/career-certificates", headers=headers).json()
    assert body["total"] == 3


def test_import_fills_the_item_already_told_in_chat(
    client: TestClient, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    """대화로 먼저 적은 같은 회사는 불러와도 새 경력을 만들지 않고 그 항목을 채웁니다."""
    headers = entered_headers("park")
    etag = client.get("/accounts/park/resume", headers=headers).headers["ETag"]
    told = client.patch(
        "/accounts/park/resume",
        headers=headers | {"If-Match": etag},
        json=[{"op": "replace", "path": "/careers/c1/company_name", "value": "(주)OO산업"}],
    )
    assert told.status_code == 200, told.text

    res = client.post(
        "/accounts/park/imports/apply", headers=headers, json={"import_ids": ["cc_career_001"]}
    )

    assert res.status_code == 200, res.text
    careers = client.get("/accounts/park/resume", headers=headers).json()["data"]["careers"]
    assert [c["item_id"] for c in careers] == ["c1"]
    assert careers[0]["start_date"]["value"] == "2004-03"
