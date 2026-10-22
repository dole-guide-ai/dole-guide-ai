"""절차 정보 입력(PATCH …/procedure) 통합 테스트 (F-16).

이력서 저장(F-15)은 아직 없으므로, 저장한 상태는 DB에서 직접 만듭니다.
"""

from collections.abc import Callable
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import KST
from app.models import Resume
from app.models.user import User

pytestmark = pytest.mark.integration


def _save_resume(db: Session, persona_id: str) -> None:
    user = db.scalars(select(User).where(User.persona_id == persona_id)).one()
    resume = db.scalars(select(Resume).where(Resume.user_id == user.user_id)).one()
    resume.status = "saved"
    resume.saved_at = datetime(2026, 10, 21, 9, tzinfo=KST)
    db.flush()


def _patch(client: TestClient, headers: dict[str, str], path: str, value: object):
    return client.patch(
        "/accounts/choi/procedure",
        headers=headers,
        json=[{"op": "replace", "path": path, "value": value}],
    )


def test_choi_goes_from_education_to_first_round(
    client: TestClient,
    db_session: Session,
    entered_headers: Callable[[str], dict[str, str]],
) -> None:
    """완료 기준: 최영수가 이력서를 저장하면 패널 E, 이수 확인을 누르면 수급자격 신청 단계."""
    headers = entered_headers("choi")
    _save_resume(db_session, "choi")
    assert client.get("/accounts/choi", headers=headers).json()["entry"]["panel"] == "E"

    res = _patch(client, headers, "/education_done", True)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["entry"]["branch_id"] == "E5a"
    assert body["entry"]["panel"] == "Q"
    assert {"path": "/stage", "value": "eligibility_application"}.items() <= body["updates"][
        1
    ].items()

    res = _patch(client, headers, "/eligibility_applied_on", "2026-10-12")
    assert res.status_code == 200, res.text
    assert res.json()["entry"]["branch_id"] == "E5b"

    res = _patch(client, headers, "/first_recognition_date", "2026-11-04")
    assert res.status_code == 200, res.text
    assert res.json()["entry"]["branch_id"] == "E4a"

    account = client.get("/accounts/choi", headers=headers).json()
    assert account["procedure"]["stage"] == "recognition"
    assert account["current_round"]["round"] == 1
    assert account["current_round"]["recognition_date"] == "2026-11-04"
    rounds = client.get("/accounts/choi/rounds", headers=headers).json()
    assert rounds["total"] >= 1
    assert all(r["application_status"] == "draft" for r in rounds["items"])


def test_first_round_shows_during_waiting_period(
    client: TestClient,
    db_session: Session,
    entered_headers: Callable[[str], dict[str, str]],
) -> None:
    """대기기간 중(1회차 시작 전)에도 1차 인정일을 넣으면 다가올 1회차를 보여 줍니다."""
    headers = entered_headers("choi")
    _save_resume(db_session, "choi")
    _patch(client, headers, "/education_done", True)
    _patch(client, headers, "/eligibility_applied_on", "2026-10-18")

    res = _patch(client, headers, "/first_recognition_date", "2026-11-04")
    assert res.status_code == 200, res.text
    assert res.json()["entry"]["branch_id"] == "E4a"
    account = client.get("/accounts/choi", headers=headers).json()
    assert account["current_round"]["round"] == 1
    assert account["current_round"]["status"] == "upcoming"


def test_education_before_resume_saved_is_stage_order(
    client: TestClient, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    headers = entered_headers("choi")

    res = _patch(client, headers, "/education_done", True)

    assert res.status_code == 409
    assert res.json()["code"] == "STAGE_ORDER"


def test_same_fact_twice_and_wrong_order_are_rejected(
    client: TestClient,
    db_session: Session,
    entered_headers: Callable[[str], dict[str, str]],
) -> None:
    headers = entered_headers("choi")
    _save_resume(db_session, "choi")

    # 교육 이수 전에 1차 인정일부터 넣을 수 없습니다.
    res = _patch(client, headers, "/first_recognition_date", "2026-11-04")
    assert res.status_code == 409
    assert res.json()["code"] == "STAGE_ORDER"

    assert _patch(client, headers, "/education_done", True).status_code == 200
    res = _patch(client, headers, "/education_done", True)
    assert res.status_code == 409
    assert "이미 입력한" in res.json()["message"]


def test_dates_out_of_range_are_422(
    client: TestClient,
    db_session: Session,
    entered_headers: Callable[[str], dict[str, str]],
) -> None:
    headers = entered_headers("choi")
    _save_resume(db_session, "choi")
    _patch(client, headers, "/education_done", True)

    # 오늘(2026-10-21) 뒤 신청일, 형식이 틀린 날짜
    assert _patch(client, headers, "/eligibility_applied_on", "2026-10-30").status_code == 422
    res = _patch(client, headers, "/eligibility_applied_on", "10월 12일")
    assert res.status_code == 422
    assert res.json()["code"] == "VALIDATION_ERROR"

    _patch(client, headers, "/eligibility_applied_on", "2026-10-12")
    # 대기기간(신청일부터 7일) 안의 1차 인정일
    assert _patch(client, headers, "/first_recognition_date", "2026-10-19").status_code == 422
    # 수급기간·소정급여일수가 끝난 뒤의 1차 인정일
    assert _patch(client, headers, "/first_recognition_date", "2028-01-04").status_code == 422


def test_unknown_path_and_remove_are_422(
    client: TestClient, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    headers = entered_headers("choi")

    assert _patch(client, headers, "/stage", "recognition").status_code == 422
    res = client.patch(
        "/accounts/choi/procedure",
        headers=headers,
        json=[{"op": "remove", "path": "/education_done"}],
    )
    assert res.status_code == 422


def test_recognition_account_cannot_enter_facts_again(
    client: TestClient, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    headers = entered_headers("lee")

    res = client.patch(
        "/accounts/lee/procedure",
        headers=headers,
        json=[
            {"op": "replace", "path": "/first_recognition_date", "value": str(date(2026, 12, 1))}
        ],
    )

    assert res.status_code == 409
    assert res.json()["code"] == "STAGE_ORDER"
