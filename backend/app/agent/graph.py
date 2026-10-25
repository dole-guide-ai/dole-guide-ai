"""LangGraph 그래프 조립. 구조는 노션 「에이전트 구조 설계」, ADR 0001.

라우팅 워크플로 + 제한된 도구 루프입니다.
경로는 코드가 정하고, LLM은 그 패널의 도구 안에서만 판단합니다.

    preprocess → load_context → route_turn → call_model ⇄ run_tools → finish
                                                    ↘ ask (interrupt, 사용자 답으로 재개) ↗

연결 약속:
- 화면으로 나갈 이벤트는 노드 안에서 `events.emit(...)`으로 냅니다(응답기가 SSE로 흘려보냄).
- 턴 정보(`TurnInput`)와 도구 문맥(`ToolContext`)은 `config["configurable"]`에서 꺼냅니다
  (`turn_of`, `tool_context_of`). 상태에 넣지 않아 체크포인트에 DB 세션이 저장되지 않습니다.
- 사용자 말은 가린 뒤에만 상태(체크포인트)에 넣습니다(preprocess).
"""

from typing import Annotated, Any, NotRequired, TypedDict

from langchain_core.messages import AnyMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph

from app.agent.tools.registry import ToolContext

TURN_KEY = "turn"
TOOL_CONTEXT_KEY = "tool_context"


class AgentState(TypedDict):
    """체크포인트에 저장되는 상태. DB 세션·user_profiles 값은 넣지 않습니다(.claude/rules/ai.md)."""

    messages: Annotated[list[AnyMessage], add_messages]
    # 이번 턴에 고른 패널(resume·round·application·guide). preprocess가 턴마다 비웁니다.
    panel: NotRequired[str | None]
    # 이번 턴 확정 사실(절차 단계·다음 물을 칸·회차 숫자). 개인정보 없음. 매 턴 DB에서 다시 읽음
    facts: NotRequired[dict[str, Any]]
    # 이번 턴 호출 수. 상한을 넘으면 루프를 멈춥니다.
    model_calls: NotRequired[int]
    tool_calls: NotRequired[int]
    # 개인정보 0등급이 있어 모델에 보내지 않은 턴
    blocked: NotRequired[bool]


def turn_of(config: RunnableConfig) -> Any:
    return config["configurable"][TURN_KEY]


def tool_context_of(config: RunnableConfig) -> ToolContext | None:
    return config["configurable"].get(TOOL_CONTEXT_KEY)


def build_graph(checkpointer: BaseCheckpointSaver | None = None) -> CompiledStateGraph:
    # 노드가 graph 모듈의 상태·키를 쓰므로 여기서 import합니다(순환 import 피하기).
    from app.agent.nodes import context, finish, panel, preprocess, route  # noqa: PLC0415

    builder = StateGraph(AgentState)
    builder.add_node("preprocess", preprocess.preprocess)
    builder.add_node("load_context", context.load_context)
    builder.add_node("route_turn", route.route_turn)
    builder.add_node("call_model", panel.call_model)
    builder.add_node("run_tools", panel.run_tools)
    builder.add_node("ask", panel.ask)
    builder.add_node("finish", finish.finish)

    builder.add_edge(START, "preprocess")
    builder.add_conditional_edges("preprocess", preprocess.after_preprocess)
    builder.add_edge("load_context", "route_turn")
    builder.add_edge("route_turn", "call_model")
    builder.add_conditional_edges("call_model", panel.after_model)
    builder.add_conditional_edges("run_tools", panel.after_tools)
    builder.add_edge("ask", "call_model")
    builder.add_edge("finish", END)
    return builder.compile(checkpointer=checkpointer)
