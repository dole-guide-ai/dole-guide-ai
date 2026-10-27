"""LangGraph 그래프 조립. 구조는 노션 「에이전트 구조 설계」, ADR 0001.

라우팅 워크플로 + 제한된 도구 루프입니다.
경로는 코드가 정하고, LLM은 그 패널의 도구 안에서만 판단합니다.

    preprocess → apply_choice → load_context → route_turn
        ├ 이력서: read_answer(모델 ①, 값만 읽음 → 코드 저장) → speak(모델 ③, 확인+질문) → finish
        └ 그 밖:  attach_knowledge → call_model ⇄ run_tools (ask: interrupt, 재개) → finish → END
- 이력서(nodes/resume): 버튼 답은 apply_choice가 코드로 저장하고, 딴 얘기(제도 질문)는
  안내 패널로 한 턴 보낸 뒤 대기 질문으로 돌아옵니다. 그림: docs/agent/graph.md

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
    # 이번 말이 확정해 답할 범위인지(nodes/route.Scope). 라우터가 정하고 preprocess가 비웁니다.
    scope: NotRequired[str | None]
    # 이번 턴 확정 사실(절차 단계·다음 물을 칸·회차 숫자). 개인정보 없음. 매 턴 DB에서 다시 읽음
    facts: NotRequired[dict[str, Any]]
    # 이번 턴 도구 루프의 답 모델 호출 수와 도구 호출 수. 상한을 넘으면 루프를 멈춥니다.
    loop_calls: NotRequired[int]
    tool_calls: NotRequired[int]
    # 개인정보 0등급이 있어 모델에 보내지 않은 턴
    blocked: NotRequired[bool]
    # 이번 턴 답의 근거로 쓴 규칙 ID(규칙 카드·규칙 함수). finish가 근거 줄을 만듭니다.
    cited: NotRequired[list[str]]
    # 이번 턴에 미리 붙인 규칙 카드 ID. 답에 내용이 나온 카드만 근거 줄에 남깁니다(finish).
    attached: NotRequired[list[str]]
    # 지금 단계·회차의 근거 규칙 카드 ID와 카드를 고를 사용자 조건(수급자 유형·회차).
    # load_context가 매 턴 채웁니다.
    situation_rules: NotRequired[list[str]]
    profile: NotRequired[dict[str, Any]]
    # 이력서 작업 기억(물은 횟수·미룬 칸·대기 질문·버튼으로 저장한 칸). nodes/resume가 씁니다.
    resume: NotRequired[dict[str, Any]]
    # 이번 턴에 답하는 모델에 사진째 보내도 되는 첨부 파일 ID(받아쓴 글에 등급 0 개인정보가
    # 없는 사진만). preprocess가 턴마다 다시 정합니다. 파일 ID라 개인정보가 아닙니다.
    vision_files: NotRequired[list[str]]
    # 이번 턴에 올렸지만 아직 활동에 붙이지 않은 구직활동 증빙 파일 ID. 질문(interrupt)에서
    # 재개하는 요청에는 첨부가 없어서, 여기서 도구 문맥으로 되살립니다(responder). preprocess가
    # 턴마다 다시 정하고 run_tools가 붙인 만큼 비웁니다. 파일 ID라 개인정보가 아닙니다.
    pending_evidence: NotRequired[list[str]]


def turn_of(config: RunnableConfig) -> Any:
    return config["configurable"][TURN_KEY]


def tool_context_of(config: RunnableConfig) -> ToolContext | None:
    return config.get("configurable", {}).get(TOOL_CONTEXT_KEY)


def build_graph(checkpointer: BaseCheckpointSaver | None = None) -> CompiledStateGraph:
    # 노드가 graph 모듈의 상태·키를 쓰므로 여기서 import합니다(순환 import 피하기).
    from app.agent.nodes import (  # noqa: PLC0415
        context,
        finish,
        panel,
        preprocess,
        resume,
        route,
    )

    builder = StateGraph(AgentState)
    builder.add_node("preprocess", preprocess.preprocess)
    builder.add_node("load_context", context.load_context)
    builder.add_node("attach_knowledge", context.attach_knowledge)
    builder.add_node("route_turn", route.route_turn)
    builder.add_node("call_model", panel.call_model)
    builder.add_node("run_tools", panel.run_tools)
    builder.add_node("ask", panel.ask)
    builder.add_node("finish", finish.finish)
    builder.add_node("apply_choice", resume.apply_choice)
    builder.add_node("read_answer", resume.read_answer)
    builder.add_node("speak", resume.speak)

    builder.add_edge(START, "preprocess")
    # path_map을 적어야 조건 분기가 그림(get_graph().draw_mermaid)에 나옵니다.
    builder.add_conditional_edges(
        "preprocess", preprocess.after_preprocess, ["apply_choice", "finish"]
    )
    builder.add_edge("apply_choice", "load_context")
    # 패널을 먼저 골라야 정책·FAQ를 안내 패널에만 붙일 수 있습니다.
    builder.add_edge("load_context", "route_turn")
    builder.add_conditional_edges(
        "route_turn", route.after_route, ["read_answer", "attach_knowledge"]
    )
    builder.add_conditional_edges("read_answer", resume.after_read, ["speak", "attach_knowledge"])
    builder.add_edge("speak", "finish")
    builder.add_edge("attach_knowledge", "call_model")
    builder.add_conditional_edges("call_model", panel.after_model, ["run_tools", "finish"])
    builder.add_conditional_edges("run_tools", panel.after_tools, ["ask", "call_model", "finish"])
    builder.add_edge("ask", "call_model")
    builder.add_edge("finish", END)
    return builder.compile(checkpointer=checkpointer)
