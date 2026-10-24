"""LangGraph 그래프를 조립하는 자리입니다.

지금은 공용 부품이 이어지는지 보여 주는 예시 그래프(노드 하나, LLM 호출 없음)입니다. 노드 구성과
상태 모양은 영역을 맡은 사람이 설계해 바꿉니다. 바꿀 때 지킬 연결 약속은 이렇습니다.

- 화면으로 나갈 이벤트는 노드 안에서 `events.emit(...)`으로 냅니다(응답기가 SSE로 흘려보냄).
- 턴 정보(`TurnInput`)와 도구 문맥(`ToolContext`)은 `config["configurable"]`에서 꺼냅니다
  (`turn_of`, `tool_context_of`). 상태에 넣지 않아 체크포인트에 DB 세션이 저장되지 않습니다.
- 그래프는 `build_graph(checkpointer)`로 만들고, 응답기가 턴마다 부릅니다.
"""

from typing import Annotated, Any, TypedDict

from langchain_core.messages import AIMessage, AnyMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph

from app.agent.events import emit
from app.agent.tools.registry import ToolContext
from app.schemas.messages import DoneEvent, TokenEvent

TURN_KEY = "turn"
TOOL_CONTEXT_KEY = "tool_context"

PLACEHOLDER_REPLY = "말씀하신 내용을 받았어요. AI 답변은 곧 연결돼요."


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def turn_of(config: RunnableConfig) -> Any:
    return config["configurable"][TURN_KEY]


def tool_context_of(config: RunnableConfig) -> ToolContext:
    return config["configurable"][TOOL_CONTEXT_KEY]


def respond(state: AgentState) -> dict[str, list[AnyMessage]]:
    """예시 노드. 사용자 말은 되풀이하지 않고 고정 문구를 글자 이벤트로 냅니다."""
    for word in PLACEHOLDER_REPLY.split(" "):
        emit(TokenEvent(text=word + " "))
    emit(DoneEvent())
    return {"messages": [AIMessage(PLACEHOLDER_REPLY)]}


def build_graph(checkpointer: BaseCheckpointSaver | None = None) -> CompiledStateGraph:
    builder = StateGraph(AgentState)
    builder.add_node("respond", respond)
    builder.add_edge(START, "respond")
    builder.add_edge("respond", END)
    return builder.compile(checkpointer=checkpointer)
