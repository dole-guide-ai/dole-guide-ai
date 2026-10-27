"""부족한 활동 추천 · 예정 활동으로 넣기 · 했어요 통합 테스트 (F-19)."""

import uuid
from collections.abc import Callable
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError
from app.models import ProcedureState
from app.models.user import User
from app.schemas.common import ErrorCode
from app.services import recommendations as recommendation_service
from app.services.accounts import AccountContext

pytestmark = pytest.mark.integration

URL = "/accounts/lee/rounds/current/recommendations"


def _add(client: TestClient, headers: dict[str, str], rec_id: str, key: str | None = None):
    extra = {"Idempotency-Key": key} if key else {}
    return client.post(
        "/accounts/lee/activities",
        headers={**headers, **extra},
        json={"recommendation_id": rec_id},
    )


def _lee(db: Session) -> AccountContext:
    user = db.scalars(select(User).where(User.persona_id == "lee")).one()
    return AccountContext(user.user_id, user.persona_id, user.anchor_date)


def test_lee_gets_three_recommendations_and_deadline(
    client: TestClient, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    """완료 기준: 이정호(1건 부족)는 증빙이 쉬운 순서로 추천 3개와 인정일 전날 기한을 받습니다."""
    headers = entered_headers("lee")

    res = client.get(URL, headers=headers)

    assert res.status_code == 200, res.text
    body = res.json()
    assert [item["recommendation_id"] for item in body["items"]] == [
        "rec_4_work24_apply",
        "rec_4_step_lecture",
        "rec_4_interview",
    ]
    assert "모바일 애플리케이션 프로그래머" in body["items"][0]["title"]
    assert body["deadline_text"].startswith("10.26(월)까지")
    assert "10.13(화)" in body["deadline_text"]


def test_pick_goes_in_as_planned_and_done_makes_it_count(
    client: TestClient, db_session: Session, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    """완료 기준: 선택하면 예정으로 들어가 계산에 안 넣고, 했다고 하면 실제 활동이 되어 충족."""
    headers = entered_headers("lee")

    res = _add(client, headers, "rec_4_work24_apply", key="pick-1")
    assert res.status_code == 201, res.text
    update = res.json()["updates"][0]
    assert update["form"] == "activities"
    assert update["value"]["planned"] is True
    assert update["value"]["activity_date"] == "2026-10-26"
    # 같은 키로 다시 보내면 한 번만 만듭니다
    assert _add(client, headers, "rec_4_work24_apply", key="pick-1").json() == res.json()
    # 예정 활동은 계산에 안 넣어 여전히 부족하지만, 이미 넣은 추천은 빼고 다음 후보를 보여 줍니다
    items = client.get(URL, headers=headers).json()["items"]
    assert [item["recommendation_id"] for item in items] == [
        "rec_4_step_lecture",
        "rec_4_interview",
        "rec_4_company_site_apply",
    ]

    done = recommendation_service.mark_done(
        db_session,
        _lee(db_session),
        uuid.UUID(update["value"]["activity_id"]),
        done_on=date(2026, 10, 20),
        today=date(2026, 10, 21),
        org_name="OO물산",
    )
    assert done.updates[0].value["planned"] is False

    assert client.get(URL, headers=headers).json()["items"] == []
    app = client.get("/accounts/lee/rounds/current/application", headers=headers).json()
    assert [r["company_name"] for r in app["job_search_rows"]] == ["OO물류", "OO물산"]


def test_done_date_must_be_in_period_and_not_future(
    client: TestClient, db_session: Session, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    headers = entered_headers("lee")
    activity_id = _add(client, headers, "rec_4_interview").json()["updates"][0]["value"][
        "activity_id"
    ]

    with pytest.raises(ConflictError) as error:
        recommendation_service.mark_done(
            db_session,
            _lee(db_session),
            uuid.UUID(activity_id),
            done_on=date(2026, 10, 22),
            today=date(2026, 10, 21),
        )
    assert error.value.code == ErrorCode.ROUND_CLOSED


def test_duplicate_and_unknown_recommendations_are_409(
    client: TestClient, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    headers = entered_headers("lee")
    assert _add(client, headers, "rec_4_step_lecture").status_code == 201

    dup = _add(client, headers, "rec_4_step_lecture")
    assert dup.status_code == 409
    assert dup.json()["code"] == "DUPLICATE_ACTIVITY"
    for bad in ("rec_3_step_lecture", "rec_4_training", "nope"):
        res = _add(client, headers, bad)
        assert res.status_code == 409, bad
        assert res.json()["code"] == "CONFLICT"


def test_ended_account_cannot_change_activities(
    client: TestClient, db_session: Session, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    """F-33 완료 기준: 수급이 끝난 뒤에는 활동을 넣거나 했어요로 바꿀 수 없습니다."""
    headers = entered_headers("lee")
    planned = _add(client, headers, "rec_4_interview").json()["updates"][0]["value"]
    account = _lee(db_session)
    db_session.get(ProcedureState, account.user_id).stage = "ended"
    db_session.flush()

    res = _add(client, headers, "rec_4_work24_apply")
    assert res.status_code == 409
    assert res.json()["code"] == "STAGE_ORDER"
    with pytest.raises(ConflictError):
        recommendation_service.mark_done(
            db_session,
            account,
            uuid.UUID(planned["activity_id"]),
            done_on=date(2026, 10, 20),
            today=date(2026, 10, 21),
        )


def test_lecture_recommendation_carries_center_schedule(
    client: TestClient, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    """F-30: 추천에 특강이 있으면 고용센터 특강 일정이 붙습니다(외부 조회가 안 되면 스냅샷)."""
    items = client.get(URL, headers=entered_headers("lee")).json()["items"]
    lecture = next(i for i in items if i["kind"] == "lecture")

    assert lecture["external"]["programs"]
    assert lecture["external"]["source"] == "snapshot"


def test_trainings_endpoint_uses_resume_wish_and_snapshot(
    client: TestClient, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    res = client.get("/accounts/lee/trainings", headers=entered_headers("lee"))

    assert res.status_code == 200
    assert res.json()["source"] == "snapshot"
