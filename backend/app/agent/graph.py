"""LangGraph 그래프 조립 (노션 「AI 설계」 2절).

바깥 그래프 하나 + 패널 서브그래프 넷(resume · round · application · education).

```
START → preprocess → load_context ─(고정 경로)──────────────────┐
                          └─(패널 라우터)→ {panel}_agent ⇄ {panel}_tools ─→ verify → ask → END
```

- preprocess: 개인정보 가림 · 서류 판독 · 입력 가드
- load_context: 절차 단계로 패널을 고르고(LLM 아님), 다음 질문 · 쓸 수 있는 칸을 정함, 고정 경로
- {panel}_agent ⇄ {panel}_tools: 값 추출 → 도구 → 답 문장 (최대 AGENT_MAX_TOOL_ROUNDS바퀴)
- verify: 숫자 · 근거 · 출력 가드를 검사한 뒤에만 답을 흘려보냄
- ask: 다음 질문(ask_user)

연결 약속
- 화면 이벤트는 노드 안에서 `events.emit(...)`으로 냅니다(응답기가 SSE로 흘려보냄).
- 턴 정보 · 도구 문맥은 `config["configurable"]`에서 꺼냅니다(graph_config).
"""

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agent.graph_config import TOOL_CONTEXT_KEY, TURN_KEY, tool_context_of, turn_of
from app.agent.nodes.ask import ask
from app.agent.nodes.context import load_context
from app.agent.nodes.panel import after_agent, make_agent, make_tools
from app.agent.nodes.preprocess import preprocess
from app.agent.nodes.verify import verify
from app.agent.panels import Panel
from app.agent.state import AgentState

__all__ = [
    "TOOL_CONTEXT_KEY",
    "TURN_KEY",
    "AgentState",
    "build_graph",
    "tool_context_of",
    "turn_of",
]

VERIFY = "verify"


def _route(state: AgentState) -> str:
    """고정 경로면 바로 verify(검사 없이 흘려보냄), 아니면 고른 패널의 agent로."""
    if state.get("fixed") or not state.get("panel"):
        return VERIFY
    return f"{state['panel']}_agent"


def build_graph(checkpointer: BaseCheckpointSaver | None = None) -> CompiledStateGraph:
    builder = StateGraph(AgentState)
    builder.add_node("preprocess", preprocess)
    builder.add_node("load_context", load_context)
    builder.add_node(VERIFY, verify)
    builder.add_node("ask", ask)

    targets = {VERIFY: VERIFY}
    for panel in Panel:
        agent, tools = f"{panel}_agent", f"{panel}_tools"
        builder.add_node(agent, make_agent(panel))
        builder.add_node(tools, make_tools(panel))
        builder.add_conditional_edges(agent, after_agent, {"tools": tools, VERIFY: VERIFY})
        builder.add_edge(tools, agent)
        targets[agent] = agent

    builder.add_edge(START, "preprocess")
    builder.add_edge("preprocess", "load_context")
    builder.add_conditional_edges("load_context", _route, targets)
    builder.add_edge(VERIFY, "ask")
    builder.add_edge("ask", END)
    return builder.compile(checkpointer=checkpointer)
