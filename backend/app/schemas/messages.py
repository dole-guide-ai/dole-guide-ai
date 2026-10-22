"""대화 메시지 보내기 요청과 대화 기록 조회 응답 스키마입니다.

메시지에는 글 내용, 입력 방식(글·음성·선택지), 함께 보낸 파일과 불러오기 항목 ID가 들어갑니다.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class InputKind(StrEnum):
    TEXT = "text"
    VOICE = "voice"
    CHOICE = "choice"


class MessageCreate(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
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
