"""이번 말을 어느 패널이 맡을지 정합니다(노션 「에이전트 구조 설계」 6절).

절차 단계와 대기 중인 이력서 질문처럼 코드가 확실히 아는 것만 규칙으로 정하고,
말의 내용으로 갈리는 것은 LLM 분류(router/classify)에 맡깁니다.
"""

from enum import StrEnum
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from app.agent import gateway
from app.agent.graph import AgentState
from app.agent.nodes.preprocess import ATTACHMENT_OPEN
from app.agent.prompts import load_prompt
from app.rules import obligations as obligation_rules
from app.schemas.procedure import Stage


class Panel(StrEnum):
    RESUME = "resume"
    ROUND = "round"
    APPLICATION = "application"
    GUIDE = "guide"


# 서류를 채우는 패널. 숫자가 규칙이 아니라 사용자 말에서 오므로 근거 검사·근거 줄을 다르게 다룹니다.
FORM_PANELS = frozenset({Panel.RESUME, Panel.APPLICATION})


CLASSIFY_PROMPT = "router/classify"
# 사용자 말 없이 첨부만 올린 턴을 모델 분류에 넘길 때 쓰는 문구
ATTACHMENT_ONLY = "(말 없이 파일만 올렸어요)"


class Scope(StrEnum):
    """말이 이 길잡이가 확정해 답할 수 있는 범위인지. 답 끝의 확인 안내를 정하는 데 씁니다."""

    IN_SCOPE = "in_scope"  # 실업급여 절차·서류·규칙
    CENTER_JUDGMENT = "center_judgment"  # 개인별 수급 가능 여부처럼 고용센터가 판단할 일
    OUT_OF_SCOPE = "out_of_scope"  # 다른 제도·기관의 일
    PRIVACY = "privacy"  # 개인정보를 저장·삭제·처리하는 방식에 대한 말


# 회차·신청서 패널은 실업인정 단계에만 있습니다(그 전에는 회차가 없음).
RECOGNITION_PANELS = frozenset({Panel.ROUND, Panel.APPLICATION})


class RouteChoice(BaseModel):
    panel: Panel
    scope: Scope = Scope.IN_SCOPE


def by_rules(
    stage: str | None, *, resume_pending: bool = False, file_only: bool = False
) -> Panel | None:
    """코드가 확실히 아는 것만 정합니다. 나머지는 None(LLM 분류로).

    - 이력서 질문에 답하는 중(resume_pending)이면 이력서.
    - 말 없이 파일만 올렸으면(file_only) 그 단계의 서류: 구직등록은 이력서 서류, 실업인정은
      구직활동 증빙.
    구직등록 단계라는 것만으로 이력서로 보내지 않습니다. 이 단계의 제도·개인정보 질문까지
    이력서 읽기를 거치면 답 끝에 이력서 질문이 붙어 질문을 밀어냅니다(골든셋 2차 측정 D8).
    말의 내용(단어)으로는 정하지 않습니다. 단어 목록은 예외가 끝없이 늘어나 분류를 모델에 맡깁니다.
    """
    if resume_pending:
        return Panel.RESUME
    if file_only and stage == Stage.JOB_REGISTRATION:
        return Panel.RESUME
    if file_only and stage == Stage.RECOGNITION:
        return Panel.ROUND
    return None


def fit_to_stage(choice: RouteChoice, stage: str | None) -> RouteChoice:
    """모델이 단계에 없는 패널을 고르면 안내 패널로 바꿉니다(회차는 실업인정 단계에만 있음)."""
    if choice.panel in RECOGNITION_PANELS and stage != Stage.RECOGNITION:
        return choice.model_copy(update={"panel": Panel.GUIDE})
    return choice


def by_model(text: str, facts: dict[str, Any], *, attached: bool = False) -> RouteChoice:
    model = gateway.get_chat_model("agent").with_structured_output(RouteChoice)
    files = "\n첨부: 있음(내용은 넣지 않음)" if attached else ""
    choice = model.invoke(
        [
            SystemMessage(load_prompt(CLASSIFY_PROMPT)),
            HumanMessage(
                f"절차 단계: {facts.get('stage')}{files}\n<user_message>\n{text}\n</user_message>"
            ),
        ]
    )
    return fit_to_stage(choice, facts.get("stage"))


def route_turn(state: AgentState) -> dict[str, Any]:
    text = str(state["messages"][-1].content)
    facts = state.get("facts", {})
    # 첨부 속 글은 분류에 쓰지 않습니다(서류 단어·문서 속 지시가 분류를 흔들지 않게).
    said, attached, _ = text.partition(ATTACHMENT_OPEN)
    said = said.strip()
    pending = bool((state.get("resume") or {}).get("pending"))
    panel = by_rules(
        facts.get("stage"), resume_pending=pending, file_only=bool(attached) and not said
    )
    choice = (
        RouteChoice(panel=panel)
        if panel is not None
        else by_model(said or ATTACHMENT_ONLY, facts, attached=bool(attached))
    )
    return {
        "panel": choice.panel.value,
        "scope": choice.scope.value,
        "obligations": scope_obligations(state, choice.scope),
    }


def scope_obligations(state: AgentState, scope: Scope) -> list[dict[str, Any]]:
    """말의 범위와 이번 말의 개인정보에 맞춰 답에 꼭 넣을 안내(rules/obligations)."""
    found = obligation_rules.from_scope(scope.value) + obligation_rules.from_pii(
        state.get("pii_kinds", [])
    )
    return obligation_rules.merge(state.get("obligations", []), found)


def panel_besides_resume(text: str, facts: dict[str, Any]) -> RouteChoice:
    """이력서 질문을 기다리는 중 딴 얘기로 읽힌 말이 갈 패널. 다시 이력서로 나오면 안내 패널."""
    said, attached, _ = text.partition(ATTACHMENT_OPEN)
    choice = by_model(said.strip() or ATTACHMENT_ONLY, facts, attached=bool(attached))
    if choice.panel == Panel.RESUME:
        return choice.model_copy(update={"panel": Panel.GUIDE})
    return choice


def after_route(state: AgentState) -> str:
    return "read_answer" if state.get("panel") == Panel.RESUME else "attach_knowledge"
