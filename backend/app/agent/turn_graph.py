"""대화 한 턴을 처리하는 에이전트 흐름 (이슈 #176 실험 버전).

preprocess(가리기) → classify_intent(규정 질문인지) → load_context(규칙 계산·사실 문장·규칙 카드)
→ respond(모델 한 번) → apply_updates(서류·활동 반영)

대화 API가 쓰는 공용 그래프(`graph.build_graph`, 메시지 상태·체크포인터·SSE 이벤트)와는 아직 따로
둡니다. 지금은 골든셋 평가와 `services.agent_turn`이 이 흐름을 부르고, 대화 화면에 붙일 때
공용 그래프의 연결 약속(`events.emit`, `turn_of`·`tool_context_of`)에 맞춰 옮깁니다.
"""

from functools import cache

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agent.nodes.apply_updates import apply_updates
from app.agent.nodes.classify_intent import classify_intent
from app.agent.nodes.load_context import load_context
from app.agent.nodes.preprocess import preprocess
from app.agent.nodes.respond import respond
from app.agent.schemas import AgentState


@cache
def build_turn_graph() -> CompiledStateGraph:
    graph = StateGraph(AgentState)
    graph.add_node("preprocess", preprocess)
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("load_context", load_context)
    graph.add_node("respond", respond)
    graph.add_node("apply_updates", apply_updates)
    graph.add_edge(START, "preprocess")
    graph.add_edge("preprocess", "classify_intent")
    graph.add_edge("classify_intent", "load_context")
    graph.add_edge("load_context", "respond")
    graph.add_edge("respond", "apply_updates")
    graph.add_edge("apply_updates", END)
    return graph.compile()
