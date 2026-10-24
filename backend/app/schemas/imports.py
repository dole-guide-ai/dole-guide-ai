"""고용24 불러오기(모의) 목록의 응답 스키마입니다. 이미 넣은 항목은 is_recorded로 표시합니다."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ImportKind(StrEnum):
    """고용24 불러오기 목록 두 가지 (설계 3.7)."""

    CAREER_CERTIFICATE = "career_certificate"  # 경력·자격·훈련 (이력서용)
    JOB_APPLICATION = "job_application"  # 입사지원 내역 (구직활동용)


class ImportCategory(StrEnum):
    CAREER = "career"
    LICENSE = "license"
    TRAINING = "training"
    JOB_SEARCH = "job_search"


class ImportApply(BaseModel):
    """고른 항목 넣기. import_id는 목록 응답의 값입니다."""

    import_ids: list[str] = Field(min_length=1, max_length=20)


class ImportItem(BaseModel):
    import_id: str
    is_recorded: bool
    values: dict[str, Any]


class ImportList(BaseModel):
    items: list[ImportItem]
    total: int
    source_note: str
