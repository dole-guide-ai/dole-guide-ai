"""대화 턴이 내보내는 SSE 이벤트.

이름의 기준은 shared/sse-events.json입니다. 백엔드 Docker 이미지에는 shared/가 들어가지 않아
여기에 같은 값을 두고, tests/unit/test_events.py가 두 곳이 같은지 확인합니다.

응답기(그래프)는 `TurnEvent`를 차례로 내보내고, 서비스가 받아 SSE로 흘려보내며 말풍선을 모읍니다.
"""

import json
from dataclasses import dataclass

from pydantic import BaseModel

from app.schemas.common import FormUpdate
from app.schemas.messages import (
    AskUserEvent,
    DoneEvent,
    ErrorEvent,
    TokenEvent,
    ToolCallEvent,
)

TOKEN = "token"
TOOL_CALL = "tool_call"
ASK_USER = "ask_user"
FORM_UPDATE = "form_update"
DONE = "done"
ERROR = "error"

_EVENT_NAMES: dict[type[BaseModel], str] = {
    TokenEvent: TOKEN,
    ToolCallEvent: TOOL_CALL,
    AskUserEvent: ASK_USER,
    FormUpdate: FORM_UPDATE,
    DoneEvent: DONE,
    ErrorEvent: ERROR,
}


@dataclass(frozen=True)
class TurnEvent:
    data: BaseModel

    @property
    def name(self) -> str:
        return _EVENT_NAMES[type(self.data)]

    def to_sse(self) -> dict[str, str]:
        payload = self.data.model_dump(mode="json", exclude_none=True)
        if isinstance(self.data, FormUpdate) and self.data.op != "remove":
            # 칸을 비우는 replace(value=None)도 값 키가 있어야 화면이 null로 바꿉니다.
            payload["value"] = self.data.model_dump(mode="json")["value"]
        return {"event": self.name, "data": json.dumps(payload, ensure_ascii=False)}


def emit(data: BaseModel) -> None:
    """그래프 노드 안에서 화면으로 이벤트 하나를 냅니다.

    `stream_mode="custom"`으로 응답기에 전달됩니다.
    """
    from langgraph.config import get_stream_writer

    get_stream_writer()(TurnEvent(data))
