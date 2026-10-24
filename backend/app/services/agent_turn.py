"""대화 턴을 AI 그래프로 처리하는 서비스입니다.

지금은 DB 없이 상태값·서류를 받아 턴을 차례로 돌립니다. 골든셋 평가(evals/golden/adapter.py)가
이 함수를 부르고, 대화 API(POST /messages)는 이후 이 함수를 감싸 SSE로 흘려보냅니다.
"""

from dataclasses import dataclass, field
from typing import Any

import openai

from app.agent import gateway
from app.agent.graph import build_graph
from app.agent.schemas import AgentState, Turn


@dataclass
class ConversationResult:
    replies: list[str] = field(default_factory=list)
    next_action: str | None = None
    cites: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)  # resume · activities · derived · round


def run_conversation(
    state: dict[str, Any], data: dict[str, Any], messages: list[str]
) -> ConversationResult:
    """사용자 말을 한 턴씩 그래프에 넣고, 마지막 서류·상황을 돌려줍니다.

    모델 호출 실패는 LlmUnavailableError·RateLimitedError로 바꿔 던집니다.
    """
    graph = build_graph()
    result = ConversationResult()
    history: list[Turn] = []
    current: AgentState = {"state": state, "data": data}
    for message in messages:
        try:
            current = graph.invoke({**current, "history": history, "message": message})
        except openai.OpenAIError as exc:
            raise gateway.to_app_error(exc) from None
        output = current["output"]
        result.replies.append(output.reply)
        result.next_action = output.next_action
        result.cites = output.cites
        # 지난 턴은 가린 글(current["message"])로만 남깁니다.
        history = [
            *history,
            {"role": "user", "text": current["message"]},
            {"role": "assistant", "text": output.reply},
        ]
    result.data = {**current["data"], **current["situation"]}
    return result
