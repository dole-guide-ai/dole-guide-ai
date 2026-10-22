"""회차 요약, 회차 점검 결과, 부족한 활동 추천의 응답 스키마입니다.

회차 점검의 숫자(필요 건수, 인정 건수, 남은 건수, D-day)는 모두 규칙 함수가 계산해 채웁니다.
"""

from datetime import date
from enum import StrEnum

from pydantic import BaseModel


class RoundStatus(StrEnum):
    UPCOMING = "upcoming"
    CURRENT = "current"
    CLOSED = "closed"


class ApplicationStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"


class RoundSummary(BaseModel):
    round: int
    period_start: date
    period_end: date
    recognition_date: date
    attendance_required: bool
    status: RoundStatus
    application_status: ApplicationStatus


class ActivityCheck(BaseModel):
    activity_id: str
    state: str
    warnings: list[str] = []


class LimitsUsed(BaseModel):
    lecture: int = 0
    aptitude_test: int = 0
    counseling: int = 0
    volunteer: int = 0


class RoundCheck(RoundSummary):
    """`check_round` 결과. 숫자는 모두 규칙 함수가 계산합니다."""

    d_day: int
    required: int
    required_job_search: int
    counted: int
    remaining: int
    activities: list[ActivityCheck] = []
    required_evidence: list[str] = []
    limits_used: LimitsUsed = LimitsUsed()
    rule_review: str = "not_verified"


class Recommendation(BaseModel):
    recommendation_id: str
    kind: str
    title: str
    reason: str
    evidence_hint: str | None = None
    external: dict | None = None


class RecommendationList(BaseModel):
    items: list[Recommendation]
    total: int
    deadline_text: str
    cite: str | None = None
