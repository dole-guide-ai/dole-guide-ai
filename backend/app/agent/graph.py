"""LangGraph 에이전트 그래프 조립 위치.

preprocess(가리기) → classify_intent(규정 질문인지) → load_context(규칙 계산·사실 문장·규칙 카드)
→ respond(모델 한 번) → apply_updates(서류·활동 반영)
guard·verify는 실험 단계에서 붙이며, 기준 점수와 비교합니다.
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
def build_graph() -> CompiledStateGraph:
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
