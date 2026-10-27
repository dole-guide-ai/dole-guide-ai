"""검색 문장 고르기 (nodes/context.search_text). 재작성 모델은 가짜로 바꿔 끼웁니다."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agent.nodes import context
from app.core.config import get_settings


@pytest.fixture
def rewrites(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, list[str]]]:
    calls: list[tuple[str, list[str]]] = []

    def fake(text: str, history: list[str]) -> str:
        calls.append((text, list(history)))
        return "고용보험 가입기간 2년 소정급여일수"

    monkeypatch.setattr(context, "rewrite_query", fake)
    monkeypatch.setattr(get_settings(), "retrieval_rewrite", True)
    return calls


def test_follow_up_is_rewritten_with_earlier_user_messages(rewrites: list) -> None:
    state = {
        "messages": [
            HumanMessage("받을 수 있는 조건이 되나요?"),
            AIMessage("네, 조건을 볼게요."),
            HumanMessage("보험을 2년 부었으면 며칠 나와요?"),
        ],
    }

    query = context.search_text(state, "보험을 2년 부었으면 며칠 나와요?")

    assert query == "고용보험 가입기간 2년 소정급여일수"
    assert rewrites == [("보험을 2년 부었으면 며칠 나와요?", ["받을 수 있는 조건이 되나요?"])]


def test_first_message_is_searched_as_is(rewrites: list) -> None:
    state = {"messages": [HumanMessage("날일 하면 끊겨요?")]}

    assert context.search_text(state, "날일 하면 끊겨요?") == "날일 하면 끊겨요?"
    assert rewrites == []


def test_rewrite_off_keeps_text(rewrites: list, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "retrieval_rewrite", False)
    state = {"messages": [HumanMessage("앞 질문"), HumanMessage("그건요?")]}

    assert context.search_text(state, "그건요?") == "그건요?"
