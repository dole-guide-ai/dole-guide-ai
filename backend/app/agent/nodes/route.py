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
from app.agent.prompts import load_prompt
from app.schemas.procedure import Stage


class Panel(StrEnum):
    RESUME = "resume"
    ROUND = "round"
    APPLICATION = "application"
    GUIDE = "guide"


# 서류를 채우는 패널. 숫자가 규칙이 아니라 사용자 말에서 오므로 근거 검사·근거 줄을 다르게 다룹니다.
FORM_PANELS = frozenset({Panel.RESUME, Panel.APPLICATION})


CLASSIFY_PROMPT = "router/classify"


class RouteChoice(BaseModel):
    panel: Panel


def by_rules(stage: str | None, *, resume_pending: bool = False) -> Panel | None:
    """코드가 확실히 아는 것만 정합니다. 나머지는 None(LLM 분류로).

    - 이력서 질문에 답하는 중(resume_pending)이면 이력서.
    - 구직등록 단계면 이력서(이 단계의 할 일이 이력서 하나뿐).
    말의 내용(단어)으로는 정하지 않습니다. 단어 목록은 예외가 끝없이 늘어나 분류를 모델에 맡깁니다.
    """
    if resume_pending or stage == Stage.JOB_REGISTRATION:
        return Panel.RESUME
    return None


def by_model(text: str, facts: dict[str, Any]) -> Panel:
    model = gateway.get_chat_model("agent").with_structured_output(RouteChoice)
    choice = model.invoke(
        [
            SystemMessage(load_prompt(CLASSIFY_PROMPT)),
            HumanMessage(
                f"절차 단계: {facts.get('stage')}\n<user_message>\n{text}\n</user_message>"
            ),
        ]
    )
    return choice.panel


def route_turn(state: AgentState) -> dict[str, Any]:
    text = str(state["messages"][-1].content)
    facts = state.get("facts", {})
    pending = bool((state.get("resume") or {}).get("pending"))
    panel = by_rules(facts.get("stage"), resume_pending=pending)
    calls = state.get("model_calls", 0)
    if panel is None:
        panel = by_model(text, facts)
        calls += 1
    return {"panel": panel.value, "model_calls": calls}


def after_route(state: AgentState) -> str:
    return "read_answer" if state.get("panel") == Panel.RESUME else "attach_knowledge"
