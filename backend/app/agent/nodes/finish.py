"""턴을 마칩니다. 근거 줄(cite)은 검증 단계(verify, 6단계)에서 채웁니다."""

from typing import Any

from langchain_core.messages import AIMessage

from app.agent.events import emit
from app.agent.graph import AgentState
from app.schemas.messages import DoneEvent, TokenEvent

# 상한에 걸려 모델이 마지막 답을 못 했을 때
LIMIT_REPLY = "여기까지 정리했어요. 이어서 말씀해 주시면 계속 도와드릴게요."


def finish(state: AgentState) -> dict[str, Any]:
    last = state["messages"][-1]
    if not state.get("blocked") and not (isinstance(last, AIMessage) and last.text):
        emit(TokenEvent(text=LIMIT_REPLY))
        emit(DoneEvent())
        return {"messages": [AIMessage(LIMIT_REPLY)]}
    emit(DoneEvent())
    return {}
