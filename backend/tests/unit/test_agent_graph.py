"""에이전트 그래프: 라우팅 규칙, 개인정보 관문, 도구 제한, interrupt 되묻기와 재개, 호출 상한.

DB 없이(도구 문맥 None) 가짜 모델로 한 턴씩 돌립니다. 입력은 모두 합성 값입니다.
"""

import uuid
from datetime import date

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.agent.nodes.finish import LIMIT_REPLY
from app.agent.nodes.panel import MAX_MODEL_CALLS
from app.agent.nodes.preprocess import BLOCKED_REPLY
from app.agent.nodes.route import Panel, by_rules
from app.agent.responder import TurnInput, graph_responder
from app.schemas.messages import AskUserEvent, DoneEvent, TokenEvent

TODAY = date(2026, 10, 21)
SYNTHETIC_RRN = "900101-1234568"


def _turn(user_id: uuid.UUID, text: str) -> TurnInput:
    return TurnInput(user_id, "lee", text, "text", TODAY)


def _messages(saver: InMemorySaver, user_id: uuid.UUID) -> list:
    state = saver.get({"configurable": {"thread_id": str(user_id)}})
    return state["channel_values"]["messages"]


def _call(name: str, args: dict, call_id: str = "c1") -> AIMessage:
    return AIMessage("", tool_calls=[{"name": name, "args": args, "id": call_id}])


@pytest.mark.parametrize(
    ("text", "stage", "panel"),
    [
        ("실업급여 받으면서 알바해도 돼요?", "recognition", Panel.GUIDE),
        ("작년 3월에 들어가서 올해 9월에 그만뒀어요", "job_registration", Panel.RESUME),
        ("어제 OO기획 홈페이지에서 지원했어요", "recognition", Panel.ROUND),
        ("이번 회차엔 몇 번 해야 돼요", "recognition", Panel.ROUND),
        ("지난주에 이틀 일당 받고 일했어요", "recognition", Panel.APPLICATION),
        ("교육 다 들었어요. 다음은 뭐예요", "education", Panel.GUIDE),
        # 평서문 "~요"와 "자격증"은 제도 질문이 아닙니다(F-017 회귀)
        ("지게차 자격증 있어요. 2011년에 땄어요", "job_registration", Panel.RESUME),
        ("65세 넘으면 실업급여 자격이 없나요", "job_registration", Panel.GUIDE),
    ],
)
def test_route_rules(text: str, stage: str, panel: Panel) -> None:
    assert by_rules(text, stage) == panel


def test_route_rules_leave_ambiguous_to_model() -> None:
    assert by_rules("음 그게요", "recognition") is None


def test_route_ignores_words_inside_attachment() -> None:
    # 골든셋 F-076: 증빙 사진 글의 "입사지원"이 이력서 단어로 잡혀 이력서 패널로 가던 문제
    photo = "지원 완료 화면이에요\n\n<첨부>\n입사지원 완료\n지원 기업: OO식품\n</첨부>"
    assert by_rules(photo, "recognition") == Panel.ROUND
    # 실업인정 단계라도 소득을 말하면 신청서
    income = "이거 알바했던 거예요\n\n<첨부>\n급여명세서\n</첨부>"
    assert by_rules(income, "recognition") == Panel.APPLICATION
    # 구직등록 단계의 경력증명서는 그대로 이력서
    career = "경력증명서예요\n\n<첨부>\n회사명 OO산업\n</첨부>"
    assert by_rules(career, "job_registration") == Panel.RESUME


def test_blocking_pii_never_reaches_model_or_checkpoint(fake_agent_llm) -> None:
    model = fake_agent_llm([AIMessage("합성 답")])
    saver, user = InMemorySaver(), uuid.uuid4()

    out = list(graph_responder(_turn(user, f"제 번호는 {SYNTHETIC_RRN}이에요"), saver))

    assert model.calls == 0
    assert [type(e.data) for e in out] == [TokenEvent, DoneEvent]
    assert out[0].data.text == BLOCKED_REPLY
    assert SYNTHETIC_RRN not in str(_messages(saver, user))


def test_phone_is_masked_before_checkpoint(fake_agent_llm) -> None:
    fake_agent_llm([AIMessage("합성 답")])
    saver, user = InMemorySaver(), uuid.uuid4()

    list(graph_responder(_turn(user, "연락처는 010-0000-0000이에요"), saver))

    assert "010-0000-0000" not in str(_messages(saver, user))
    assert "[전화]" in str(_messages(saver, user)[0].content)


def test_tool_outside_panel_is_refused(fake_agent_llm) -> None:
    """guide 패널에서 활동 기록 도구를 부르면 실행하지 않고 거절 사유를 모델에 돌려줍니다."""
    fake_agent_llm([_call("record_activity", {"when": "어제", "kind": "x"}),
                    AIMessage("안내했어요")], route="guide")  # fmt: skip
    saver, user = InMemorySaver(), uuid.uuid4()

    list(graph_responder(_turn(user, "음 그게요"), saver))

    tool_results = [m for m in _messages(saver, user) if isinstance(m, ToolMessage)]
    assert tool_results[0].content == "이 단계에서 쓸 수 없는 도구예요."


def test_ask_user_interrupts_then_resumes_with_answer(fake_agent_llm) -> None:
    ask = _call("ask_user", {"question": "언제부터 다니셨어요?", "choices": []})
    model = fake_agent_llm([ask, AIMessage("고마워요, 저장할게요")], route="resume")
    saver, user = InMemorySaver(), uuid.uuid4()

    first = list(graph_responder(_turn(user, "음 그게요"), saver))

    assert [type(e.data) for e in first] == [AskUserEvent, DoneEvent]
    assert first[0].data.text == "언제부터 다니셨어요?"
    assert model.calls == 1

    second = list(graph_responder(_turn(user, "2004년 3월이요"), saver))

    assert "".join(e.data.text for e in second if isinstance(e.data, TokenEvent)) == (
        "고마워요, 저장할게요"
    )
    answers = [m.content for m in _messages(saver, user) if isinstance(m, ToolMessage)]
    assert answers == ["사용자 답: 2004년 3월이요"]


def test_blocked_answer_keeps_question_waiting(fake_agent_llm) -> None:
    ask = _call("ask_user", {"question": "확인할 게 있어요", "choices": ["예", "아니요"]})
    model = fake_agent_llm([ask, AIMessage("고마워요")])
    saver, user = InMemorySaver(), uuid.uuid4()
    list(graph_responder(_turn(user, "음 그게요"), saver))

    out = list(graph_responder(_turn(user, SYNTHETIC_RRN), saver))

    assert out[0].data.text == BLOCKED_REPLY
    assert model.calls == 1  # 재개하지 않음
    assert SYNTHETIC_RRN not in str(_messages(saver, user))


def test_tool_loop_stops_at_model_call_limit(fake_agent_llm) -> None:
    model = fake_agent_llm([_call("no_such_tool", {})])  # 끝없이 도구만 부르는 모델
    saver, user = InMemorySaver(), uuid.uuid4()

    out = list(graph_responder(_turn(user, "음 그게요"), saver))

    # 상한에는 라우팅 분류 1회가 포함됩니다("음 그게요"는 규칙으로 못 정함).
    assert model.calls == MAX_MODEL_CALLS - 1
    assert out[-2].data.text == LIMIT_REPLY


def test_new_turn_after_cut_stream_closes_dangling_tool_call(fake_agent_llm) -> None:
    """질문 이벤트 직후 스트림이 끊겨도 다음 턴에 결과 없는 도구 호출이 남지 않습니다."""
    ask = _call("ask_user", {"question": "언제부터요?", "choices": []})
    fake_agent_llm([ask, AIMessage("다시 도와드릴게요")])
    saver, user = InMemorySaver(), uuid.uuid4()
    stream = graph_responder(_turn(user, "음 그게요"), saver)
    next(stream)  # 질문 이벤트까지만 받고 끊음
    stream.close()

    list(graph_responder(_turn(user, "다른 질문이요"), saver))

    messages = _messages(saver, user)
    calls = {c["id"] for m in messages if isinstance(m, AIMessage) for c in m.tool_calls}
    results = {m.tool_call_id for m in messages if isinstance(m, ToolMessage)}
    assert calls <= results
