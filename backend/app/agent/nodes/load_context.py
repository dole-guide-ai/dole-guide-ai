from app.agent.schemas import AgentState
from app.rules import situation


def load_context(state: AgentState) -> AgentState:
    """규칙 코드로 지금 상황(회차·필요 건수·인정 건수)을 계산합니다. AI는 이 값을 설명만 합니다."""
    derived = situation.derive(state["state"])
    context = {"today": state["state"]["demo_today"], "derived": derived}
    if derived["current_round"]:
        context["round"] = situation.check_round(derived, state["data"]["activities"])
    return {"situation": context}
