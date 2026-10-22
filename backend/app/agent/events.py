"""대화 턴이 내보내는 SSE 이벤트.

이름의 기준은 shared/sse-events.json입니다. 백엔드 Docker 이미지에는 shared/가 들어가지 않아
여기에 같은 값을 두고, tests/unit/test_events.py가 두 곳이 같은지 확인합니다.

응답기(그래프)는 `TurnEvent`를 차례로 내보내고, 서비스가 받아 SSE로 흘려보내며 말풍선을 모읍니다.
"""

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
        return {"event": self.name, "data": self.data.model_dump_json(exclude_none=True)}
