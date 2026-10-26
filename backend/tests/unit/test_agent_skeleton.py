"""AI 공용 뼈대: 예시 그래프·응답기 연결, 도구 어댑터, 프롬프트 로더, 체크포인터 접속 문자열."""

import uuid
from datetime import date, datetime
from unittest.mock import MagicMock

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app.agent.checkpointer import conninfo
from app.agent.prompts import load_prompt
from app.agent.responder import TurnInput, graph_responder, run_config
from app.agent.tools.langchain import as_langchain_tools
from app.agent.tools.registry import TOOLS_BY_PANEL, ToolContext
from app.core.clock import KST
from app.schemas.messages import DoneEvent, TokenEvent
from app.services.accounts import AccountContext

TODAY = date(2026, 10, 21)


def _turn(user_id: uuid.UUID, text: str = "합성 입력 문장") -> TurnInput:
    return TurnInput(user_id, "lee", text, "text", TODAY)


def _ctx(allowed: tuple[str, ...] | None = None) -> ToolContext:
    account = AccountContext(uuid.uuid4(), "lee", TODAY)
    now = datetime(2026, 10, 21, 10, tzinfo=KST)
    return ToolContext(MagicMock(), account, TODAY, now, allowed_paths=allowed)


def test_graph_responder_streams_tokens_then_done() -> None:
    out = list(graph_responder(_turn(uuid.uuid4()), InMemorySaver()))

    assert all(isinstance(e.data, TokenEvent) for e in out[:-1])
    assert isinstance(out[-1].data, DoneEvent)
    assert "합성 입력 문장" not in "".join(e.data.text for e in out[:-1])


def test_checkpointer_keeps_conversation_per_account() -> None:
    saver, user = InMemorySaver(), uuid.uuid4()
    list(graph_responder(_turn(user, "첫 말"), saver))
    list(graph_responder(_turn(user, "둘째 말"), saver))
    list(graph_responder(_turn(uuid.uuid4(), "다른 계정"), saver))

    state = saver.get({"configurable": {"thread_id": str(user)}})

    assert len(state["channel_values"]["messages"]) == 4


def test_run_config_has_thread_and_no_tool_context_without_db() -> None:
    user = uuid.uuid4()
    config = run_config(_turn(user))

    assert config["configurable"]["thread_id"] == str(user)
    assert config["configurable"]["tool_context"] is None
    assert "request_id" in config["metadata"]


def test_adapter_exposes_registry_tools_with_schema() -> None:
    tools = as_langchain_tools(_ctx(), TOOLS_BY_PANEL["resume"])

    assert [t.name for t in tools] == list(TOOLS_BY_PANEL["resume"])
    assert "fields" in tools[0].args
    (overview,) = as_langchain_tools(_ctx(), ["answer_overview"])
    assert overview.invoke({})["text"].startswith("실업급여는 네 단계")


def test_adapter_returns_tool_error_to_llm_instead_of_raising() -> None:
    (save,) = as_langchain_tools(_ctx(allowed=("/careers",)), ["save_resume_fields"])

    result = save.invoke({"fields": [{"path": "/desired/job", "value": "합성 직무"}]})

    assert result == "지금 질문과 관계없는 칸이라 쓰지 않았어요."


def test_load_prompt_rejects_missing_and_outside_paths() -> None:
    with pytest.raises(FileNotFoundError):
        load_prompt("no_such_prompt")
    with pytest.raises(FileNotFoundError):
        load_prompt("../graph")


def test_conninfo_drops_sqlalchemy_driver() -> None:
    assert conninfo("postgresql+psycopg://u:p@h:5432/d") == "postgresql://u:p@h:5432/d"


def test_done_is_sent_only_after_checkpoint_saved() -> None:
    """체크포인트 저장이 실패하면 done 없이 실패로 끝납니다 (done 뒤 error가 오지 않게)."""

    class FailingSaver(InMemorySaver):
        def put(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN201
            raise RuntimeError("synthetic checkpoint failure")

    sent = []
    with pytest.raises(RuntimeError):
        for event in graph_responder(_turn(uuid.uuid4()), FailingSaver()):
            sent.append(event)

    assert not any(isinstance(e.data, DoneEvent) for e in sent)
