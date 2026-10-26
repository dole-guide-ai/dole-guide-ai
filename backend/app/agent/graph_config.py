"""노드가 실행 config에서 턴 정보와 도구 문맥을 꺼내는 약속입니다.

턴 정보(`TurnInput`)와 도구 문맥(`ToolContext`)은 상태가 아니라 `config["configurable"]`로
넘겨 체크포인트에 DB 세션이 남지 않게 합니다.
"""

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.agent.tools.registry import ToolContext

TURN_KEY = "turn"
TOOL_CONTEXT_KEY = "tool_context"


def turn_of(config: RunnableConfig) -> Any:
    return config["configurable"][TURN_KEY]


def tool_context_of(config: RunnableConfig) -> ToolContext | None:
    return config["configurable"].get(TOOL_CONTEXT_KEY)
