"""턴을 마칩니다. 근거 줄(cite)과 다음 할 일(next_action)은 코드가 정합니다.

- 근거 줄: 이번 턴에 쓴 규칙 카드·규칙 함수·정책·FAQ 조각의 출처로 만듭니다(cite_line).
  LLM이 출처를 쓰지 않으므로 지어낸 인용이 나올 수 없습니다.
- 다음 할 일: 절차 단계와 이번 회차 상태로 정합니다(rules/next_action).
"""

from typing import Any

from langchain_core.messages import AIMessage

from app.agent.events import emit
from app.agent.graph import AgentState
from app.rules.next_action import next_action
from app.rules.rule_cards import cite_line
from app.schemas.messages import DoneEvent, TokenEvent

# 상한에 걸려 모델이 마지막 답을 못 했을 때
LIMIT_REPLY = "여기까지 정리했어요. 이어서 말씀해 주시면 계속 도와드릴게요."


def done_event(state: AgentState) -> DoneEvent:
    cited = state.get("cited", [])
    facts = state.get("facts", {})
    action = next_action(facts.get("stage"), facts.get("round"))
    return DoneEvent(
        cite=cite_line(cited, state.get("cited_sources", [])),
        rule_refs=cited,
        next_action=action.value if action else None,
    )


def finish(state: AgentState) -> dict[str, Any]:
    last = state["messages"][-1]
    if state.get("blocked"):
        emit(DoneEvent())
        return {}
    if not (isinstance(last, AIMessage) and last.text):
        emit(TokenEvent(text=LIMIT_REPLY))
        emit(done_event(state))
        return {"messages": [AIMessage(LIMIT_REPLY)]}
    emit(done_event(state))
    return {}
