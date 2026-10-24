"""패널 직접 고치기 통합 테스트 (F-12): 활동 PATCH와 이력서 날짜 형식."""

from collections.abc import Callable
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Activity
from app.models.user import User
from conftest import TEST_TODAY

pytestmark = pytest.mark.integration


def _etag(client: TestClient, headers: dict[str, str], url: str) -> str:
    """REST 서류 PATCH는 If-Match가 필수라(설계 3.11) 지금 ETag를 받아 보냅니다."""
    return client.get(url, headers=headers).headers["ETag"]


def _planned_activity(client: TestClient, headers: dict[str, str]) -> str:
    recs = client.get("/accounts/lee/rounds/current/recommendations", headers=headers).json()
    rec_id = recs["items"][0]["recommendation_id"]
    res = client.post(
        "/accounts/lee/activities", headers=headers, json={"recommendation_id": rec_id}
    )
    return res.json()["updates"][0]["value"]["activity_id"]


def _patch(client: TestClient, headers: dict[str, str], activity_id: str, ops: list[dict]):
    return client.patch(f"/accounts/lee/activities/{activity_id}", headers=headers, json=ops)


def test_edit_activity_marks_direct_and_checks_format(
    client: TestClient, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    headers = entered_headers("lee")
    activity_id = _planned_activity(client, headers)

    res = _patch(
        client, headers, activity_id, [{"op": "replace", "path": "/org_name", "value": "OO물산"}]
    )
    assert res.status_code == 200, res.text
    value = res.json()["updates"][0]["value"]
    assert (value["org_name"], value["source"]) == ("OO물산", "direct")

    for ops in (
        [{"op": "replace", "path": "/activity_date", "value": "12월 8일"}],
        [{"op": "replace", "path": "/planned", "value": False}],
        [{"op": "remove", "path": "/kind"}],
        [{"op": "replace", "path": "/hours", "value": 30}],
        [{"op": "replace", "path": "/activity_date", "value": "2020-01-01"}],
        [{"op": "replace", "path": "/activity_date", "value": "20261021"}],
        [{"op": "replace", "path": "/hours", "value": 1.25}],
        [{"op": "replace", "path": "/hours", "value": "NaN"}],
        [{"op": "replace", "path": "/org_name"}],
        [],
    ):
        bad = _patch(client, headers, activity_id, ops)
        assert bad.status_code == 422, ops
        assert bad.json()["code"] == "VALIDATION_ERROR"

    assert _patch(client, headers, "no-such-id", []).status_code == 404


def test_past_round_activity_is_409(
    client: TestClient, db_session: Session, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    headers = entered_headers("lee")
    user = db_session.scalars(select(User).where(User.persona_id == "lee")).one()
    # 지난 회차(대상기간 전) 활동
    old = Activity(
        user_id=user.user_id,
        activity_date=TEST_TODAY - timedelta(days=60),
        category="job_search",
        kind="application",
        source="seed",
    )
    db_session.add(old)
    db_session.flush()
    res = _patch(client, headers, str(old.activity_id), [{"op": "remove", "path": "/result"}])
    assert res.status_code == 409 and res.json()["code"] == "ROUND_CLOSED"


def test_resume_date_must_be_year_month(
    client: TestClient, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    headers = entered_headers("park")
    url = "/accounts/park/resume"
    bad = client.patch(
        url,
        headers={**headers, "If-Match": _etag(client, headers, url)},
        json=[{"op": "replace", "path": "/careers/c1/start_date", "value": "2004년 3월"}],
    )
    assert bad.status_code == 422 and bad.json()["details"][0]["type"] == "date_format"
    assert client.get(url, headers=headers).json()["data"]["careers"] == []
    ok = client.patch(
        url,
        headers={**headers, "If-Match": _etag(client, headers, url)},
        json=[{"op": "replace", "path": "/certifications/l1/acquired_date", "value": "2011-05-20"}],
    )
    assert ok.status_code == 200, ok.text
    for value in ("２００４-03", "2011-02-31"):
        path = "/certifications/l1/acquired_date" if "-31" in value else "/careers/c1/start_date"
        res = client.patch(
            url,
            headers={**headers, "If-Match": _etag(client, headers, url)},
            json=[{"op": "replace", "path": path, "value": value}],
        )
        assert res.status_code == 422, value
