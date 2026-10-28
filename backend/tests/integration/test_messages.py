"""대화 기록 조회와 멈춘 질문 복원 통합 테스트 (F-03)."""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.services import messages as message_service
from app.services.messages import TurnMessage

pytestmark = pytest.mark.integration

ASK = TurnMessage(
    role="assistant",
    kind="ask_user",
    text="어떤 활동이었어요?",
    payload={
        "question_id": "activity.category",
        "choices": ["입사지원", "면접", "다른 활동"],
        "accepts_file": True,
    },
)


def _lee_id(db: Session):
    return db.scalars(select(User.user_id).where(User.persona_id == "lee")).one()


def test_new_account_has_no_history_and_no_pending_question(
    client: TestClient, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    headers = entered_headers("lee")

    res = client.get("/accounts/lee/messages", headers=headers)

    assert res.status_code == 200, res.text
    assert res.json() == {"items": [], "total": 0, "next_cursor": None}
    assert client.get("/accounts/lee", headers=headers).json()["pending_ask"] is None


def test_refresh_restores_messages_and_pending_question(
    client: TestClient, db_session: Session, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    """완료 기준: 새로고침해도 대화와 멈춘 질문의 선택지가 그대로 돌아옵니다."""
    headers = entered_headers("lee")
    user_id = _lee_id(db_session)
    message_service.save_turn(
        db_session,
        user_id,
        [
            TurnMessage(role="user", kind="text", text="오늘 면접 봤어요"),
            TurnMessage(
                role="assistant", kind="text", text="기록할게요.", payload={"cite": "ACT-002"}
            ),
            ASK,
        ],
    )
    db_session.flush()

    body = client.get("/accounts/lee/messages", headers=headers).json()
    assert [(m["seq"], m["role"], m["kind"]) for m in body["items"]] == [
        (1, "user", "text"),
        (2, "assistant", "text"),
        (3, "assistant", "ask_user"),
    ]
    assert body["items"][1]["payload"] == {"cite": "ACT-002"}
    pending = client.get("/accounts/lee", headers=headers).json()["pending_ask"]
    assert pending == {
        "question_id": "activity.category",
        "text": "어떤 활동이었어요?",
        "choices": ["입사지원", "면접", "다른 활동"],
        "import_kind": None,
        "accepts_file": True,
        "file_choice": None,
    }

    # 답하면 더는 멈춘 질문이 아닙니다
    message_service.save_turn(
        db_session, user_id, [TurnMessage(role="user", kind="text", text="면접")]
    )
    db_session.flush()
    assert client.get("/accounts/lee", headers=headers).json()["pending_ask"] is None


def test_history_pages_by_cursor(
    client: TestClient, db_session: Session, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    headers = entered_headers("lee")
    message_service.save_turn(
        db_session,
        _lee_id(db_session),
        [TurnMessage(role="assistant", kind="text", text=f"말풍선 {i}") for i in range(105)],
    )
    db_session.flush()

    first = client.get("/accounts/lee/messages", headers=headers).json()
    assert (len(first["items"]), first["total"], first["next_cursor"]) == (100, 105, 100)
    rest = client.get(
        "/accounts/lee/messages", headers=headers, params={"cursor": first["next_cursor"]}
    ).json()
    assert [m["seq"] for m in rest["items"]] == [101, 102, 103, 104, 105]
    assert rest["next_cursor"] is None


def test_history_is_per_account(
    client: TestClient, db_session: Session, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    lee = entered_headers("lee")
    message_service.save_turn(db_session, _lee_id(db_session), [ASK])
    db_session.flush()
    choi = entered_headers("choi")

    assert client.get("/accounts/choi/messages", headers=choi).json()["total"] == 0
    assert client.get("/accounts/lee/messages", headers=lee).json()["total"] == 1
