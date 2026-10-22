import json
import time
from collections.abc import Iterator
from datetime import datetime
from datetime import time as dtime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.agent import responder
from app.agent.events import TurnEvent
from app.core.clock import KST
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.models import Visitor
from app.schemas.common import FormUpdate
from app.schemas.messages import (
    AskUserEvent,
    DoneEvent,
    MessageCreate,
    TokenEvent,
    ToolCallEvent,
)
from app.services import accounts as account_service
from app.services import chat as chat_service
from app.services.seed import load_personas
from app.services.visitors import authenticate, create_visitor
from conftest import TEST_TODAY

pytestmark = pytest.mark.integration


def use_responder(monkeypatch: pytest.MonkeyPatch, fn) -> None:
    monkeypatch.setattr(responder, "get_responder", lambda: fn)


def sse_events(res) -> list[tuple[str, dict]]:
    """SSE 본문을 (이벤트, 데이터) 목록으로."""
    out, name = [], None
    for line in res.text.splitlines():
        if line.startswith("event:"):
            name = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            out.append((name, json.loads(line.split(":", 1)[1].strip())))
    return out


def send(client: TestClient, headers, text="합성 질문", **extra):
    return client.post("/accounts/lee/messages", headers=headers | extra, json={"text": text})


def scripted(*items) -> responder.Responder:
    def run(_: responder.TurnInput) -> Iterator[TurnEvent]:
        for item in items:
            if isinstance(item, Exception):
                raise item
            yield TurnEvent(item)

    return run


def test_turn_streams_events_and_saves_bubbles(client, entered_headers, monkeypatch):
    use_responder(
        monkeypatch,
        scripted(
            ToolCallEvent(name="check_round", status="started"),
            ToolCallEvent(name="check_round", status="finished"),
            FormUpdate(form="resume", path="/title", op="replace", value="지게차 운전"),
            TokenEvent(text="이번 회차는 "),
            TokenEvent(text="1건 남았어요."),
            DoneEvent(cite="고용24 실업인정 안내", rule_refs=["R-4"]),
        ),
    )
    headers = entered_headers("lee")

    res = send(client, headers)

    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")
    events = sse_events(res)
    assert [e for e, _ in events] == [
        "tool_call", "tool_call", "form_update", "token", "token", "done",
    ]  # fmt: skip
    assert events[2][1]["path"] == "/title"
    history = client.get("/accounts/lee/messages", headers=headers).json()
    assert [(m["role"], m["kind"], m["text"]) for m in history["items"]] == [
        ("user", "text", "합성 질문"),
        ("assistant", "text", "이번 회차는 1건 남았어요."),
    ]
    assert history["items"][1]["payload"]["cite"] == "고용24 실업인정 안내"
    assert history["total"] == 2
    assert history["next_cursor"] is None


def test_default_echo_responder_works(client, entered_headers):
    events = sse_events(send(client, entered_headers("lee")))

    assert events[-1][0] == "done"
    assert all(name == "token" for name, _ in events[:-1])


def test_responder_failure_becomes_error_event(client, entered_headers, monkeypatch):
    use_responder(monkeypatch, scripted(TokenEvent(text="잠깐만요 "), RuntimeError("boom")))
    headers = entered_headers("lee")

    events = sse_events(send(client, headers))

    assert events[-1] == ("error", {"code": "LLM_UNAVAILABLE", "message": events[-1][1]["message"]})
    assert "boom" not in json.dumps(events, ensure_ascii=False)
    kinds = [
        m["kind"] for m in client.get("/accounts/lee/messages", headers=headers).json()["items"]
    ]
    assert kinds == ["text", "text", "error"]


def test_turn_timeout_sends_timeout_error(client, entered_headers, monkeypatch):
    monkeypatch.setattr(get_settings(), "turn_timeout_seconds", 0)

    def slow(_):
        yield TurnEvent(TokenEvent(text="생각 중"))
        time.sleep(0.01)
        yield TurnEvent(TokenEvent(text="안 보여야 함"))

    use_responder(monkeypatch, slow)

    events = sse_events(send(client, entered_headers("lee")))

    assert [e for e, _ in events] == ["token", "error"]
    assert events[-1][1]["code"] == "TIMEOUT"


def test_ask_user_is_restored_as_pending_ask(client, entered_headers, monkeypatch):
    ask = AskUserEvent(
        question_id="q-quit", text="퇴사 사유를 골라 주세요", choices=["계약만료", "권고사직"]
    )
    use_responder(monkeypatch, scripted(TokenEvent(text="하나만 여쭤볼게요."), DoneEvent(), ask))
    headers = entered_headers("lee")
    send(client, headers)

    account = client.get("/accounts/lee", headers=headers).json()

    assert account["pending_ask"]["question_id"] == "q-quit"
    assert account["pending_ask"]["choices"] == ["계약만료", "권고사직"]


def test_same_idempotency_key_is_not_run_twice(client, entered_headers, monkeypatch):
    headers = entered_headers("lee") | {"Idempotency-Key": "msg-1"}

    first = send(client, headers)
    again = send(client, headers)

    assert first.status_code == 200
    assert again.status_code == 409
    assert again.json()["code"] == "CONFLICT"
    users = [m for m in client.get("/accounts/lee/messages", headers=headers).json()["items"]]
    assert sum(m["role"] == "user" for m in users) == 1


def test_messages_are_paged_by_cursor(client, entered_headers, monkeypatch):
    monkeypatch.setattr(chat_service, "PAGE_SIZE", 3)
    headers = entered_headers("lee")
    for _ in range(2):
        send(client, headers)

    first = client.get("/accounts/lee/messages", headers=headers).json()
    rest = client.get(
        f"/accounts/lee/messages?cursor={first['next_cursor']}", headers=headers
    ).json()

    assert [m["seq"] for m in first["items"]] == [1, 2, 3]
    assert first["next_cursor"] == 3
    assert [m["seq"] for m in rest["items"]] == [4]
    assert rest["next_cursor"] is None


def test_other_visitor_cannot_read_messages(client, entered_headers):
    send(client, entered_headers("lee"))

    res = client.get("/accounts/lee/messages", headers=entered_headers("lee"))

    assert res.json()["total"] == 0


def test_rejects_empty_text(client, entered_headers):
    res = client.post("/accounts/lee/messages", headers=entered_headers("lee"), json={"text": ""})

    assert res.status_code == 422


@pytest.fixture
def committed_account(migrated_db):
    """잠금은 커밋된 행에만 걸리므로, 실제로 커밋한 계정을 만들고 끝나면 지웁니다."""
    now = datetime.combine(TEST_TODAY, dtime(9), KST)
    with SessionLocal() as db:
        load_personas(db)
        visitor = create_visitor(db, now)
        ctx = authenticate(db, visitor.visitor_token, now)
        account_service.enter(db, ctx.visitor_id, "lee", TEST_TODAY)
        account = account_service.find_account(db, ctx.visitor_id, "lee")
    yield account
    with SessionLocal() as db:
        db.execute(delete(Visitor).where(Visitor.visitor_id == ctx.visitor_id))
        db.commit()


def test_second_turn_while_first_runs_is_409(committed_account):
    body = MessageCreate(text="합성 질문")
    with SessionLocal() as first_db, SessionLocal() as second_db:
        turn = chat_service.start_turn(first_db, committed_account, body, None, TEST_TODAY)
        events = turn.events()
        next(events)  # 첫 턴이 스트리밍 중

        with pytest.raises(Exception) as exc:
            chat_service.start_turn(second_db, committed_account, body, None, TEST_TODAY)
        assert getattr(exc.value, "code", None) == "TURN_IN_PROGRESS"

        events.close()  # 첫 턴이 끝나면(끊김 포함) 잠금이 풀립니다
        turn2 = chat_service.start_turn(second_db, committed_account, body, None, TEST_TODAY)
        assert list(turn2.events())[-1].name == "done"


def test_closing_stream_stops_responder_and_saves(committed_account, monkeypatch):
    stopped = []

    def long_answer(_):
        try:
            for i in range(100):
                yield TurnEvent(TokenEvent(text=f"{i} "))
        finally:
            stopped.append(True)

    use_responder(monkeypatch, long_answer)
    with SessionLocal() as db:
        turn = chat_service.start_turn(
            db, committed_account, MessageCreate(text="합성 질문"), None, TEST_TODAY
        )
        events = turn.events()
        next(events), next(events)
        events.close()  # 연결이 끊긴 경우와 같음

    assert stopped == [True]
    with SessionLocal() as db:
        saved = chat_service.list_messages(db, committed_account, None).items
    assert [m.text for m in saved] == ["합성 질문", "0 1"]
