"""고용24 OpenAPI 조회 결과(훈련과정·취업역량 프로그램)의 응답 스키마입니다.

실시간 조회인지 스냅샷인지(source)와 조회 시각을 함께 돌려줍니다.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class ExternalSource(StrEnum):
    LIVE = "live"
    SNAPSHOT = "snapshot"


class Training(BaseModel):
    id: str
    title: str
    institution: str
    period: str
    region: str | None = None
    url: str | None = None


class Program(BaseModel):
    id: str
    title: str
    type: str
    schedule: str
    center: str | None = None
    url: str | None = None


class TrainingList(BaseModel):
    items: list[Training]
    total: int
    source: ExternalSource
    fetched_at: datetime


class ProgramList(BaseModel):
    items: list[Program]
    total: int
    source: ExternalSource
    fetched_at: datetime
