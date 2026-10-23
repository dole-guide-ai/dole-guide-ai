"""절차 사실 입력과 회차 자동 전환 통합 테스트 (F-16·F-28).

박진수(이력서 저장 전)를 교육 단계로 옮겨 교육 이수 → 수급자격 신청일 → 1차 인정일을 넣고,
이정호(4차)는 오늘을 4차 인정일 다음 날로 옮겨 5차로 넘어가는지 봅니다.
"""

from collections.abc import Callable
from datetime import date, datetime, time, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import KST, get_now, get_today
from app.main import app
from app.models import ProcedureState, RecognitionApplication, Round
from app.models.user import User
from conftest import TEST_TODAY

pytestmark = pytest.mark.integration

Headers = Callable[[str], dict[str, str]]
PROCEDURE = "/accounts/park/procedure"


def _set(client: TestClient, headers: dict[str, str], path: str, value):
    return client.patch(
        PROCEDURE, headers=headers, json=[{"op": "replace", "path": path, "value": value}]
    )


def _state(db: Session, persona_id: str) -> ProcedureState:
    user = db.scalars(select(User).where(User.persona_id == persona_id)).one()
    return db.get(ProcedureState, user.user_id)


def test_center_facts_in_order_create_rounds(
    client: TestClient, db_session: Session, entered_headers: Headers
):
    """F-16·F-28: 교육 이수 → 신청일 → 1차 인정일 순서로 넣으면 회차·신청서가 생깁니다."""
    headers = entered_headers("park")
    # 순서가 틀리면 막습니다 (이력서 저장 전이라 아직 교육 단계가 아님).
    early = _set(client, headers, "/education_done", True)
    assert early.status_code == 409
    assert early.json()["code"] == "STAGE_ORDER"
    _state(db_session, "park").stage = "education"
    db_session.flush()

    done = _set(client, headers, "/education_done", True)
    assert done.status_code == 200, done.text
    assert done.json()["updates"][-1] == {
        **done.json()["updates"][-1],
        "path": "/stage",
        "value": "eligibility_application",
    }
    assert done.json()["entry"]["branch_id"]

    applied = TEST_TODAY - timedelta(days=3)
    assert (
        _set(client, headers, "/eligibility_applied_on", str(TEST_TODAY + timedelta(1))).status_code
        == 422
    )
    assert _set(client, headers, "/eligibility_applied_on", applied.isoformat()).status_code == 200
    again = _set(client, headers, "/eligibility_applied_on", applied.isoformat())
    assert again.status_code == 409
    assert "이미 입력한" in again.json()["message"]

    # 1차 인정일은 대기기간(신청일부터 7일) 뒤여야 합니다.
    too_early = applied + timedelta(days=6)
    assert (
        _set(client, headers, "/first_recognition_date", too_early.isoformat()).status_code == 422
    )
    first = applied + timedelta(days=21)
    res = _set(client, headers, "/first_recognition_date", first.isoformat())
    assert res.status_code == 200, res.text

    state = _state(db_session, "park")
    rounds = list(
        db_session.scalars(
            select(Round).where(Round.user_id == state.user_id).order_by(Round.round_no)
        )
    )
    assert state.stage == "recognition"
    assert rounds[0].period_start == applied + timedelta(days=7)
    assert rounds[0].recognition_date >= first  # 휴일이면 다음 평일
    assert len(rounds) > 1
    applications = db_session.scalars(
        select(RecognitionApplication).where(RecognitionApplication.user_id == state.user_id)
    ).all()
    assert len(applications) == len(rounds)
    assert all(a.status == "draft" for a in applications)


def test_round_moves_on_after_recognition_day(client: TestClient, entered_headers: Headers):
    """F-28 완료 기준: 4차 인정일 다음 날 열면 5차이고, 4차 활동·신청서는 고칠 수 없습니다(409)."""
    headers = entered_headers("lee")
    fourth = client.get("/accounts/lee/rounds/current", headers=headers).json()
    activity_id = client.get("/accounts/lee/activities", headers=headers).json()["items"][0][
        "activity_id"
    ]
    next_day = date.fromisoformat(fourth["recognition_date"]) + timedelta(days=1)
    app.dependency_overrides[get_today] = lambda: next_day
    app.dependency_overrides[get_now] = lambda: datetime.combine(next_day, time(9), KST)

    fifth = client.get("/accounts/lee/rounds/current", headers=headers).json()
    account = client.get("/accounts/lee", headers=headers).json()
    removed = client.delete(f"/accounts/lee/activities/{activity_id}", headers=headers)

    assert fifth["round"] == fourth["round"] + 1
    assert account["current_round"]["round"] == fifth["round"]
    assert removed.status_code == 409
    assert removed.json()["code"] == "ROUND_CLOSED"
    past = f"/accounts/lee/rounds/{fourth['round']}/application"
    etag = client.get(past, headers=headers).headers["ETag"]
    edit = client.patch(
        past,
        headers={**headers, "If-Match": etag},
        json=[{"op": "replace", "path": "/status", "value": "submitted"}],
    )
    assert edit.status_code == 409, edit.text
    assert edit.json()["code"] == "ROUND_CLOSED"


def test_rounds_cannot_be_changed_by_api(client: TestClient, entered_headers: Headers):
    """회차를 바꾸는 API는 없습니다: 절차 PATCH로 회차·인정일 칸을 보내면 받지 않습니다."""
    headers = entered_headers("lee")

    res = client.patch(
        "/accounts/lee/procedure",
        headers=headers,
        json=[{"op": "replace", "path": "/first_recognition_date", "value": "2026-12-01"}],
    )
    other = client.patch(
        "/accounts/lee/procedure",
        headers=headers,
        json=[{"op": "replace", "path": "/rounds/4/recognition_date", "value": "2026-12-01"}],
    )

    assert res.status_code == 409
    assert other.status_code == 422
