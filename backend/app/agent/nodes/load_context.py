from app.agent import retrieval
from app.agent.schemas import AgentState
from app.core.config import get_settings
from app.rules import situation
from app.rules.facts import build_facts
from app.rules.rule_cards import build_rule_cards


def load_context(state: AgentState) -> AgentState:
    """규칙 코드로 지금 상황(회차·필요 건수·인정 건수)을 계산합니다. AI는 이 값을 설명만 합니다.

    계산 결과는 사람이 읽는 사실 문장(facts)으로도 만들어, AI가 숫자·날짜를 그대로 옮기게 합니다.
    설정에 따라 활동 규칙 카드(RULE_CARDS)와 지식 자료 검색 결과(RETRIEVAL_MODE)를 더합니다.
    검색어는 preprocess가 가린 말이라 개인정보가 임베딩 API로 나가지 않습니다.
    """
    settings = get_settings()
    derived = situation.derive(state["state"])
    context = {"today": state["state"]["demo_today"], "derived": derived}
    round_check = None
    if derived["current_round"]:
        round_check, _ = situation.check_round(state["state"], derived, state["data"]["activities"])
        context["round"] = round_check
    context["facts"] = build_facts(state["state"], derived, round_check)
    if settings.rule_cards:
        context["rule_cards"] = build_rule_cards(derived)
    if references := retrieval.as_references(retrieval.search(state["message"])):
        context["references"] = references
    return {"situation": context}
