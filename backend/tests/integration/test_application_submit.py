"""회차 신청서 제출·본인 답변 저장 통합 테스트 (F-27)."""

from collections.abc import Callable, Iterator
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import KST, get_now
from app.core.errors import ConflictError
from app.main import app
from app.models import Activity, ProcedureState
from app.models.user import User
from app.schemas.common import JsonPatchOp
from app.services import application as application_service
from app.services.accounts import AccountContext

pytestmark = pytest.mark.integration

NOW = datetime(2026, 10, 21, 10, tzinfo=KST)
ATTEND_ITEMS = ["id_card", "eligibility_card"]


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setitem(app.dependency_overrides, get_now, lambda: NOW)
    yield


def _answer(path: str, value: object) -> JsonPatchOp:
    return JsonPatchOp(op="replace", path=path, value=value)


SELF_ANSWERS = [
    _answer("/work/has_work", "no"),
    _answer("/employment/status", "none"),
    _answer("/industrial_accident/receiving", "no"),
    _answer("/next_plan", [{"item_id": "p1", "kind": "job_search", "planned_on": "2026-11-02"}]),
]


def _fill_job_search_fields(db: Session) -> None:
    """구직활동 필수 칸(담당 부서·모집 직종·결과)은 대화(F-25)로 채우므로 여기서는 DB로 채웁니다."""
    for activity in db.scalars(select(Activity)):
        activity.contact_dept = "인사팀"
        activity.job_title = "일반 사무"
        activity.result = "서류전형 심사진행 중"
    db.flush()


def _submit(client: TestClient, headers: dict[str, str], mode: object, items=None, if_match=None):
    patch = [
        {"op": "replace", "path": "/status", "value": "submitted"},
        {"op": "replace", "path": "/submit_mode", "value": mode},
    ]
    if items is not None:
        patch.append({"op": "replace", "path": "/attend_items", "value": items})
    extra = {"If-Match": if_match} if if_match else {}
    return client.patch(
        "/accounts/lee/rounds/current/application", headers={**headers, **extra}, json=patch
    )


def test_attend_after_answers_and_items_keeps_answers(
    client: TestClient,
    db_session: Session,
    entered_headers: Callable[[str], dict[str, str]],
) -> None:
    """완료 기준: 출석 준비 확인 뒤에도 본인 답변이 지워지지 않는다 (점검 9)."""
    headers = entered_headers("lee")
    account = _account_of(client, headers, db_session)
    _fill_job_search_fields(db_session)

    # 답이 비어 있으면 막는 항목이 남아 제출할 수 없습니다.
    res = _submit(client, headers, "attend", ATTEND_ITEMS)
    assert res.status_code == 409
    assert res.json()["code"] == "CANNOT_SUBMIT"

    updates = application_service.record_user_answer(
        db_session, account, "current", SELF_ANSWERS, NOW
    )
    assert [u.path for u in updates] == [op.path for op in SELF_ANSWERS]

    # 인정일 전에 저장한 답은 다시 불러와도 남아 있습니다 (자동 저장).
    before = client.get("/accounts/lee/rounds/current/application", headers=headers)
    assert before.json()["data"]["work"]["has_work"]["value"] == "no"
    assert before.json()["data"]["work"]["has_work"]["answered_on"] == "2026-10-21"
    assert before.json()["can_submit"] is True

    # 준비물을 체크하지 않으면 출석 준비 확인을 할 수 없습니다.
    res = _submit(client, headers, "attend", ["id_card"])
    assert res.status_code == 409
    assert "신분증과 수급자격증" in res.json()["message"]

    res = _submit(client, headers, "attend", ATTEND_ITEMS, if_match=before.headers["ETag"])
    assert res.status_code == 200, res.text
    assert {"path": "/status", "value": "submitted"}.items() <= res.json()["updates"][0].items()

    after = client.get("/accounts/lee/rounds/current/application", headers=headers).json()
    assert after["status"] == "submitted"
    assert after["data"]["work"]["has_work"]["value"] == "no"
    assert after["data"]["employment"]["status"]["value"] == "none"

    res = _submit(client, headers, "attend", ATTEND_ITEMS)
    assert res.status_code == 409
    assert res.json()["code"] == "APPLICATION_LOCKED"


def test_mode_different_from_server_is_409(
    client: TestClient, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    """완료 기준: 버튼 상태와 다른 모드로 보내면 409 (preview 버튼이 send로 보내던 버그)."""
    headers = entered_headers("lee")

    # 4차는 출석 회차라 send로는 낼 수 없습니다.
    res = _submit(client, headers, "send")
    assert res.status_code == 409
    assert res.json()["code"] == "CANNOT_SUBMIT"

    # 5차는 인정일 전(preview)이라 send로 낼 수 없습니다.
    res = client.patch(
        "/accounts/lee/rounds/5/application",
        headers=headers,
        json=[
            {"op": "replace", "path": "/status", "value": "submitted"},
            {"op": "replace", "path": "/submit_mode", "value": "send"},
        ],
    )
    assert res.status_code == 409
    assert res.json()["code"] == "CANNOT_SUBMIT"


def test_malformed_submit_values_are_422(
    client: TestClient, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    """제출 방식이 글자가 아니거나 준비물이 글자 목록이 아니면 500이 아니라 422."""
    headers = entered_headers("lee")

    assert _submit(client, headers, ["attend"]).status_code == 422
    res = _submit(client, headers, "attend", items=[1, ["id_card"]])
    assert res.status_code == 422
    assert res.json()["code"] == "VALIDATION_ERROR"
    removed = client.patch(
        "/accounts/lee/rounds/current/application",
        headers=headers,
        json=[{"op": "remove", "path": "/status", "value": "submitted"}],
    )
    assert removed.status_code == 422


def test_field_edit_mix_version_and_closed_round(
    client: TestClient, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    headers = entered_headers("lee")
    url = "/accounts/lee/rounds/current/application"

    res = client.patch(
        url, headers=headers, json=[{"op": "replace", "path": "/work/has_work", "value": "no"}]
    )
    assert res.status_code == 422
    assert res.json()["code"] == "USER_ANSWER_ONLY"

    res = client.patch(
        url,
        headers=headers,
        json=[
            {"op": "replace", "path": "/status", "value": "submitted"},
            {"op": "replace", "path": "/work/has_work", "value": "no"},
        ],
    )
    assert res.status_code == 422
    assert res.json()["code"] == "STATUS_WITH_FIELDS"

    res = _submit(client, headers, "attend", ATTEND_ITEMS, if_match='"999"')
    assert res.status_code == 409
    assert res.json()["code"] == "VERSION_CONFLICT"

    res = client.patch(
        "/accounts/lee/rounds/3/application",
        headers=headers,
        json=[{"op": "replace", "path": "/status", "value": "submitted"}],
    )
    assert res.status_code == 409
    assert res.json()["code"] == "ROUND_CLOSED"


def _account_of(client: TestClient, headers: dict[str, str], db: Session) -> AccountContext:
    """API로 입장한 계정을 서비스 테스트용 AccountContext로 찾습니다."""
    user = db.scalars(select(User).where(User.persona_id == "lee")).one()
    return AccountContext(user.user_id, user.persona_id, user.anchor_date)


def test_ended_account_cannot_change_application(
    client: TestClient, db_session: Session, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    """F-33 완료 기준: 수급이 끝난 뒤에는 신청서를 제출하거나 본인 답변을 고칠 수 없습니다."""
    headers = entered_headers("lee")
    account = _account_of(client, headers, db_session)
    state = db_session.get(ProcedureState, account.user_id)
    state.stage = "ended"
    db_session.flush()

    res = _submit(client, headers, "attend", items=ATTEND_ITEMS)
    assert res.status_code == 409
    assert res.json()["code"] == "STAGE_ORDER"
    with pytest.raises(ConflictError):
        application_service.record_user_answer(
            db_session, account, "current", [_answer("/work/has_work", "no")], NOW
        )
