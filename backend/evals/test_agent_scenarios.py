"""보안 · 일상 질문 시나리오 (노션 「AI 설계」 2-3-1 · 5-2).

scenarios/security/*.json, scenarios/small_talk/*.json을 실제 대화 턴으로 돌립니다.
`pnpm test:eval`에 포함. 보안 시나리오는 실제 모델이 필요합니다(키가 없으면 건너뜀).

기대값
- no_form_update: 칸이 하나도 바뀌지 않음
- forbidden_forms / forbidden_paths: 그 서류 · 칸은 바뀌지 않음
- must_include / must_not_include: 답 글자
- no_pii_in_reply: 답에 개인정보 패턴 없음
- never_seen: 모델 입력과 답 어디에도 나오지 않음 (개인정보 가림)
- max_llm_calls: 모델 호출 수 상한 (고정 경로는 0)
"""

from datetime import date, datetime, time
from typing import Any

import pytest
from langchain_core.callbacks import BaseCallbackHandler
from sqlalchemy import delete

from app.agent import gateway
from app.agent.input import pii
from app.core.clock import KST
from app.core.db import SessionLocal
from app.models import Visitor
from app.schemas.messages import MessageCreate
from app.services import accounts as account_service
from app.services import chat as chat_service
from app.services.seed import load_personas
from app.services.visitors import authenticate, create_visitor
from evals.conftest import load_scenarios

pytestmark = pytest.mark.eval

TODAY = date(2026, 10, 21)
SECURITY = load_scenarios("security")
SMALL_TALK = load_scenarios("small_talk")


@pytest.fixture
def llm_calls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    texts: list[str] = []

    class Recorder(BaseCallbackHandler):
        def on_chat_model_start(self, serialized, messages, **kwargs) -> None:
            texts.extend(str(m.content) for batch in messages for m in batch)
            texts.append("<call>")

    original = gateway.get_chat_model

    def recording(role: str = "agent"):
        model = original(role=role)
        model.callbacks = [*(model.callbacks or []), Recorder()]
        return model

    monkeypatch.setattr(gateway, "get_chat_model", recording)
    return texts


def _run(scenario: dict[str, Any]) -> tuple[list[Any], str]:
    now = datetime.combine(TODAY, time(10), KST)
    persona = scenario["input"]["persona"]
    with SessionLocal() as db:
        load_personas(db)
        visitor = create_visitor(db, now)
        visitor_id = authenticate(db, visitor.visitor_token, now).visitor_id
        account_service.enter(db, visitor_id, persona, TODAY)
        account = account_service.find_account(db, visitor_id, persona)
        db.commit()
        events: list[Any] = []
        try:
            for text in scenario["input"]["messages"]:
                turn = chat_service.start_turn(db, account, MessageCreate(text=text), None, TODAY)
                events += list(turn.events())
        finally:
            db.rollback()
            db.execute(delete(Visitor).where(Visitor.visitor_id == visitor_id))
            db.commit()
    reply = "".join(e.data.text for e in events if e.name == "token")
    return events, reply


def _check(scenario: dict[str, Any], events: list[Any], reply: str, calls: list[str]) -> None:
    expected = scenario["expected"]
    updates = [e.data for e in events if e.name == "form_update"]
    if expected.get("no_form_update"):
        assert not updates, "칸이 바뀌었어요"
    for form in expected.get("forbidden_forms", []):
        assert all(u.form != form for u in updates), f"{form} 서류가 바뀌었어요"
    for path in expected.get("forbidden_paths", []):
        assert all(not u.path.startswith(path) for u in updates), f"{path} 칸이 바뀌었어요"
    for phrase in expected.get("must_include", []):
        assert phrase in reply
    for phrase in expected.get("must_not_include", []):
        assert phrase not in reply
    if expected.get("no_pii_in_reply"):
        assert not pii.detect(reply)
    for secret in expected.get("never_seen", []):
        assert secret not in reply
        assert all(secret not in text for text in calls), "모델 입력에 개인정보가 있어요"
    if "max_llm_calls" in expected:
        assert calls.count("<call>") <= expected["max_llm_calls"]


@pytest.mark.parametrize("scenario", SMALL_TALK, ids=lambda s: s["id"])
def test_small_talk(scenario: dict[str, Any], llm_calls: list[str]) -> None:
    events, reply = _run(scenario)
    _check(scenario, events, reply, llm_calls)


@pytest.mark.parametrize("scenario", SECURITY, ids=lambda s: s["id"])
def test_security(scenario: dict[str, Any], llm_calls: list[str], requires_llm) -> None:
    events, reply = _run(scenario)
    _check(scenario, events, reply, llm_calls)
