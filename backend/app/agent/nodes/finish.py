"""턴을 마칩니다. 근거 줄(cite)과 다음 할 일(next_action)은 코드가 정합니다.

- 근거 줄: 도구가 돌려준 규칙과, 미리 붙인 카드·정책 조각 중 답에 실제로 나온 것의 출처로
  만듭니다(cite_line). 붙이기만 하고 답에 안 쓴 카드는 근거 줄에 넣지 않습니다.
  LLM이 출처를 쓰지 않으므로 지어낸 인용이 나올 수 없습니다.
- 다음 할 일: 절차 단계와 이번 회차 상태로 정합니다(rules/next_action).
"""

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage

from app.agent.events import emit
from app.agent.graph import AgentState
from app.agent.grounding import claims, used_in_answer
from app.agent.nodes.route import Panel
from app.agent.tools.guide import OVERVIEW_TERMS
from app.rules.next_action import NextAction, next_action
from app.rules.rule_cards import RuleCard, cards_by_id, cite_line
from app.schemas.messages import DoneEvent, TokenEvent

# 회차 값 중 답에 "N건"으로 나오는 칸
COUNT_KEYS = ("required", "counted", "remaining", "remaining_job_search")
# 서류를 채우는 패널(근거 줄은 규칙명·증빙을 직접 말할 때만)
FORM_PANELS = {Panel.RESUME, Panel.APPLICATION}
# 상한에 걸려 모델이 마지막 답을 못 했을 때
LIMIT_REPLY = "여기까지 정리했어요. 이어서 말씀해 주시면 계속 도와드릴게요."


def turn_answer(messages: list[Any]) -> str:
    """이번 턴(마지막 사용자 말 뒤)에 모델이 낸 글 전체. 도구 앞뒤로 나뉜 글을 모두 봅니다."""
    texts: list[str] = []
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            break
        if isinstance(message, AIMessage) and message.text:
            texts.append(message.text)
    return "\n".join(reversed(texts))


def used_rules(attached: list[str], answer: str, *, by_numbers: bool = True) -> list[str]:
    """미리 붙인 카드 중 답에 숫자·규칙명·증빙 이름이 나온 카드.

    by_numbers=False면 숫자가 겹친 것만으로는 쓴 것으로 보지 않습니다. 서류 대화의 날짜·건수
    ("2025년 8월", "1건")가 회차 카드 숫자와 우연히 겹쳐 근거 줄이 붙던 문제를 막습니다.
    """
    cards = [card for rule_id in attached if (card := cards_by_id().get(rule_id))]
    return [
        c.rule_id
        for c in cards
        if used_in_answer(_card_text(c) if by_numbers else "", _card_terms(c), answer, c.body)
    ]


def _card_text(card: RuleCard) -> str:
    return " ".join(card.for_model().values())


def _card_terms(card: RuleCard) -> str:
    """답에 나오면 그 카드를 쓴 것으로 보는 말: 규칙명과 증빙 이름."""
    return f"{card.name} {card.evidence}"


def used_guides(guides: list[dict[str, str]], answer: str) -> list[str]:
    """붙인 정책·FAQ 조각 중 답에 쓴 조각의 출처 표시."""
    return [g["출처"] for g in guides if used_in_answer(g["내용"], g["제목"], answer)]


def used_fact_refs(facts: dict[str, Any], answer: str) -> list[str]:
    """코드가 계산해 지금 상황에 넣은 값(회차 숫자·전체 순서)을 답에 썼으면 그 규칙 카드."""
    refs: list[str] = []
    round_ = facts.get("round") or {}
    if round_ and claims(answer) & _round_claims(round_):
        refs += round_.get("rule_refs", [])
    steps = facts.get("procedure_steps")
    if steps and used_in_answer("", OVERVIEW_TERMS, answer):
        refs += steps["rule_refs"]
    return refs


def _round_claims(round_: dict[str, Any]) -> set[str]:
    """회차 값을 답에 쓸 법한 모양으로: 날짜("12-22")와 건수("1건")."""
    dates = claims(" ".join(str(round_.get(k, "")) for k in ("period_start", "period_end",
                                                                 "recognition_date")))  # fmt: skip
    counts = {f"{round_[k]}건" for k in COUNT_KEYS if isinstance(round_.get(k), int)}
    return dates | counts


def done_event(state: AgentState) -> DoneEvent:
    """근거 줄 = 도구가 돌려준 규칙(모델이 고른 것) + 미리 붙인 근거 중 답에 쓴 것."""
    answer = turn_answer(state.get("messages", []))
    facts = state.get("facts", {})
    cited = list(state.get("cited", []))
    # 서류 패널은 규칙명·증빙 이름을 직접 말했을 때만 근거를 붙입니다(회차·순서 값 겹침은 빼고).
    form = state.get("panel") in FORM_PANELS
    used = used_rules(state.get("attached", []), answer, by_numbers=not form)
    if not form:
        used += used_fact_refs(facts, answer)
    cited += [r for r in dict.fromkeys(used) if r not in cited]
    # load_context가 계산해 모델에도 보여 준 값. 없으면(단위 테스트 등) 여기서 계산합니다.
    action = (
        NextAction(facts["next_action"])
        if facts.get("next_action")
        else next_action(
            facts.get("stage"),
            facts.get("round"),
            resume_ready=bool(facts.get("resume_ready")),
            education_done=facts.get("education_done"),
        )
    )
    return DoneEvent(
        cite=cite_line(cited, used_guides(facts.get("guides", []), answer)),
        rule_refs=cited,
        next_action=action.value if action else None,
    )


def finish(state: AgentState) -> dict[str, Any]:
    last = state["messages"][-1]
    if state.get("blocked"):
        emit(DoneEvent())
        return {}
    if not (isinstance(last, AIMessage) and last.text):
        emit(TokenEvent(text=LIMIT_REPLY))
        emit(done_event(state))
        return {"messages": [AIMessage(LIMIT_REPLY)]}
    emit(done_event(state))
    return {}
