"""여러 API가 같이 쓰는 응답 스키마."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class ErrorCode(StrEnum):
    """프론트와 공유하는 오류 코드. 새 코드는 여기에만 추가합니다(대문자 스네이크)."""

    BAD_REQUEST = "BAD_REQUEST"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    RATE_LIMITED = "RATE_LIMITED"
    LLM_UNAVAILABLE = "LLM_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class FieldError(BaseModel):
    field: str
    type: str


class ErrorResponse(BaseModel):
    """모든 실패 응답의 형식."""

    code: ErrorCode
    message: str
    details: Any = None


class Page[T](BaseModel):
    """목록 응답. 성공 응답은 감싸지 않고, 목록만 이 형식을 씁니다."""

    items: list[T]
    total: int
