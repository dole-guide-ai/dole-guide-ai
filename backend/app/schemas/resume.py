"""이력서 조회 응답 스키마입니다.

칸 값과 상태, 꼭 묻는 5개 항목의 완성도, 다음에 물을 질문, 저장 가능 여부, 맨 위 기본정보 표시값이
들어갑니다.
칸 구조 자체는 forms/resume.py에 있습니다.
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel
from pydantic import Field as PydanticField

from app.schemas.common import FieldSource, FieldStatus
from app.schemas.forms.resume import ResumeData
from app.schemas.profile import ProfileDisplay


class ResumeStatus(StrEnum):
    DRAFT = "draft"
    SAVED = "saved"


class Completeness(BaseModel):
    filled: int
    total: int = 5


class FieldWrite(BaseModel):
    """대화 턴이 이력서 칸 하나에 쓰는 값. 경로는 `/careers/c1/company_name` 형식입니다."""

    path: str = PydanticField(pattern=r"^/")
    value: Any = None
    status: FieldStatus = FieldStatus.EXTRACTED
    source: FieldSource = FieldSource.USER_ANSWER
    transformed: bool = False
    evidence: dict[str, Any] | None = None


class ResumeRead(BaseModel):
    status: ResumeStatus
    lock_version: int
    data: ResumeData
    completeness: Completeness
    next_question: str | None = None
    can_save: bool
    profile_display: ProfileDisplay | None = None
