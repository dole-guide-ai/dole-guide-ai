from app.agent.schemas import AgentState
from app.rules import situation
from app.rules.facts import build_facts


def load_context(state: AgentState) -> AgentState:
    """규칙 코드로 지금 상황(회차·필요 건수·인정 건수)을 계산합니다. AI는 이 값을 설명만 합니다.

    계산 결과는 사람이 읽는 사실 문장(facts)으로도 만들어, AI가 숫자·날짜를 그대로 옮기게 합니다.
    """
    derived = situation.derive(state["state"])
    context = {"today": state["state"]["demo_today"], "derived": derived}
    round_check = None
    if derived["current_round"]:
        round_check, _ = situation.check_round(state["state"], derived, state["data"]["activities"])
        context["round"] = round_check
    context["facts"] = build_facts(state["state"], derived, round_check)
    return {"situation": context}
