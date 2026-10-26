"""검색을 돕는 모델 호출 두 가지: 질의 재작성과 후보 재정렬.

질의 재작성: 검색 전에 사용자 말을 검색 문장으로 바꿉니다.

"작년에 공장 다니다 짤렸는데 받을 수 있나"처럼 흐트러진 말을 "해고로 이직한 경우 수급자격"처럼
규칙표 용어에 가까운 문장으로 바꿔 단어·벡터 검색을 돕습니다. 턴마다 LLM 호출이 하나 늘어서
평가로 효과가 확인될 때만 켭니다(설정 RETRIEVAL_REWRITE). 켜면 이어지는 말에만 씁니다
(nodes/context.attach_knowledge).

재정렬: 검색 점수로 넉넉히 뽑은 규칙 카드 후보 중 질문에 답하는 데 필요한 카드를 모델이 고릅니다.
비슷한 카드(나이·기간별 소정급여일수 등)가 앞자리를 차지해 필요한 카드가 밀리는 것을 막습니다
(설정 RETRIEVAL_RERANK).
"""

import logging
from collections.abc import Sequence

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.agent import gateway
from app.agent.prompts import load_prompt
from app.rules.rule_cards import RuleCard

logger = logging.getLogger(__name__)

REWRITE_PROMPT = "retrieval/rewrite"
RERANK_PROMPT = "retrieval/rerank"
# 후보 카드 내용은 앞부분만 보여 줍니다(고르는 데는 이름·대상·핵심 문장이면 충분).
RERANK_BODY_CHARS = 160
REWRITE_MAX_CHARS = 80


class RewrittenQuery(BaseModel):
    query: str = Field(max_length=REWRITE_MAX_CHARS)


def rewrite_query(text: str, history: Sequence[str] = ()) -> str:
    """검색 문장. 모델 호출이 실패하면 원래 말로 찾습니다(검색은 재작성 없이도 됩니다).

    history는 앞선 사용자 말(가린 글)입니다. "그건요?"처럼 앞 말을 받는 질문을 풀 때 씁니다.
    """
    model = gateway.get_chat_model("extract").with_structured_output(RewrittenQuery)
    earlier = "".join(f"<earlier_message>\n{h}\n</earlier_message>\n" for h in history)
    try:
        result = model.invoke(
            [
                SystemMessage(load_prompt(REWRITE_PROMPT)),
                HumanMessage(f"{earlier}<user_message>\n{text}\n</user_message>"),
            ]
        )
    except Exception as exc:  # noqa: BLE001 — 재작성 실패는 검색을 막지 않습니다
        logger.warning("query_rewrite_failed", extra={"code": gateway.to_app_error(exc).code})
        return text
    return result.query.strip() or text


class ChosenCards(BaseModel):
    ids: list[str]


def _candidate(card: RuleCard) -> str:
    parts = [card.rule_id, card.name, card.target, card.body[:RERANK_BODY_CHARS]]
    return " | ".join(p for p in parts if p)


def rerank_cards(text: str, cards: Sequence[RuleCard], limit: int) -> list[RuleCard]:
    """질문에 필요한 카드를 limit장까지 골라 고른 순서로. 관련 카드가 없으면 빈 목록.

    모델 호출이 실패하거나 후보에 없는 ID만 돌아오면 검색 순위 앞의 limit장을 씁니다.
    """
    if not cards:
        return []
    model = gateway.get_chat_model("extract").with_structured_output(ChosenCards)
    listing = "\n".join(_candidate(c) for c in cards)
    try:
        result = model.invoke(
            [
                SystemMessage(load_prompt(RERANK_PROMPT).replace("{limit}", str(limit))),
                HumanMessage(
                    f"<candidates>\n{listing}\n</candidates>\n"
                    f"<user_message>\n{text}\n</user_message>"
                ),
            ]
        )
    except Exception as exc:  # noqa: BLE001 — 재정렬 실패는 검색 순위로 대신합니다
        logger.warning("card_rerank_failed", extra={"code": gateway.to_app_error(exc).code})
        return list(cards[:limit])
    by_id = {c.rule_id: c for c in cards}
    chosen = [by_id[i] for i in dict.fromkeys(result.ids) if i in by_id]
    if result.ids and not chosen:  # 모두 후보 밖 ID: 모델 답을 믿지 않습니다
        return list(cards[:limit])
    return chosen[:limit]
