"""검색 전에 사용자 말을 검색 문장으로 바꿉니다(질의 재작성).

"작년에 공장 다니다 짤렸는데 받을 수 있나"처럼 흐트러진 말을 "해고로 이직한 경우 수급자격"처럼
규칙표 용어에 가까운 문장으로 바꿔 단어·벡터 검색을 돕습니다. 턴마다 LLM 호출이 하나 늘어서
평가로 효과가 확인될 때만 켭니다(설정 RETRIEVAL_REWRITE).
"""

import logging

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.agent import gateway
from app.agent.prompts import load_prompt

logger = logging.getLogger(__name__)

REWRITE_PROMPT = "retrieval/rewrite"
REWRITE_MAX_CHARS = 80


class RewrittenQuery(BaseModel):
    query: str = Field(max_length=REWRITE_MAX_CHARS)


def rewrite_query(text: str) -> str:
    """검색 문장. 모델 호출이 실패하면 원래 말로 찾습니다(검색은 재작성 없이도 됩니다)."""
    model = gateway.get_chat_model("extract").with_structured_output(RewrittenQuery)
    try:
        result = model.invoke(
            [
                SystemMessage(load_prompt(REWRITE_PROMPT)),
                HumanMessage(f"<user_message>\n{text}\n</user_message>"),
            ]
        )
    except Exception as exc:  # noqa: BLE001 — 재작성 실패는 검색을 막지 않습니다
        logger.warning("query_rewrite_failed", extra={"code": gateway.to_app_error(exc).code})
        return text
    return result.query.strip() or text
