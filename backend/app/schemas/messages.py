"""대화 메시지 보내기 요청과 대화 기록 조회 응답 스키마입니다.

메시지에는 글 내용, 입력 방식(글·음성·선택지), 함께 보낸 파일과 불러오기 항목 ID가 들어갑니다.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field

# 메시지 하나의 최대 글자 수
MESSAGE_MAX_CHARS = 2000


class InputKind(StrEnum):
    TEXT = "text"
    VOICE = "voice"
    CHOICE = "choice"


class MessageCreate(BaseModel):
    text: str = Field(min_length=1, max_length=MESSAGE_MAX_CHARS)
    input_kind: InputKind = InputKind.TEXT
    file_ids: list[str] = []
    import_ids: list[str] = []


class MessageRead(BaseModel):
    seq: int
    role: str
    kind: str
    text: str | None = None
    payload: dict[str, Any] | None = None
    created_at: datetime


class MessageList(BaseModel):
    items: list[MessageRead]
    total: int
    next_cursor: int | None = None


# ── 대화 턴 SSE 이벤트 페이로드
# 노션 「API · ERD 설계」 4절, 프론트 types/chat.types.ts와 같은 모양입니다.
# 이벤트 이름은 shared/sse-events.json을 따릅니다(app/agent/events.py).


class TokenEvent(BaseModel):
    text: str


class ToolCallEvent(BaseModel):
    name: str
    status: Literal["started", "finished"]


class AskUserEvent(BaseModel):
    question_id: str
    text: str
    choices: list[str] = []
    import_kind: str | None = None
    accepts_file: bool = False


class DoneEvent(BaseModel):
    cite: str | None = None
    rule_refs: list[str] = []


class ErrorEvent(BaseModel):
    """턴 도중 실패. code는 LLM_UNAVAILABLE·RATE_LIMITED·INTERNAL_ERROR·TIMEOUT."""

    code: str
    message: str
