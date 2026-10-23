"""회차 요약, 회차 점검 결과, 부족한 활동 추천의 응답 스키마입니다.

회차 점검의 숫자(필요 건수, 인정 건수, 남은 건수, D-day)는 모두 규칙 함수가 계산해 채웁니다.
"""

from datetime import date
from enum import StrEnum

from pydantic import BaseModel

from app.schemas.activities import ActivityCategory


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


class ActivityStatus(StrEnum):
    """활동 하나의 회차 계산 결과 (상세기획 2-2.2·2-2.6)."""

    COUNTED = "counted"
    SAME_DAY = "same_day"
    OUT_OF_PERIOD = "out_of_period"
    NOT_ALLOWED = "not_allowed"
    LIMIT_OVER = "limit_over"
    NEEDS_CHECK = "needs_check"
    PLANNED = "planned"


class CheckStatus(StrEnum):
    """회차 전체 판정: 충족 / 부족 / 규칙으로 셀 수 없어 확인 필요."""

    SATISFIED = "satisfied"
    SHORT = "short"
    NEEDS_CHECK = "needs_check"


class WarningId(StrEnum):
    """사전 경고 (상세기획 2-2.7). W7은 MVP 제외, W8은 대화에서만 냅니다."""

    SAME_DAY = "W1"
    OUT_OF_PERIOD = "W2"
    SAME_COMPANY = "W3"
    LIMIT_OVER = "W4"
    NO_EVIDENCE = "W5"
    NO_JOB_SEARCH = "W6"
    INTERVIEW_CONFIRMATION = "W8"


class RuleReview(StrEnum):
    VERIFIED = "verified"
    NOT_VERIFIED = "not_verified"


class ActivityCheck(BaseModel):
    activity_id: str
    activity_date: date
    category: ActivityCategory
    kind: str
    route: str | None = None
    org_name: str | None = None
    job_title: str | None = None
    source: str
    planned: bool
    status: ActivityStatus
    # 경로별 필요 증빙. 빈 목록이면 증빙 불필요, None이면 표에 없는 경로라 확인 필요
    required_evidence: list[str] | None = []
    has_evidence: bool = False
    rule_refs: list[str] = []


class RoundWarning(BaseModel):
    id: WarningId
    message: str
    activity_ids: list[str] = []
    rule_refs: list[str] = []


class WeekCheck(BaseModel):
    """8차부터 일반 수급자의 주 단위 구직활동 (대상기간 시작일부터 7일씩, 설계 6.2)."""

    start: date
    end: date
    job_search: int


class LimitsUsed(BaseModel):
    lecture: int = 0
    aptitude_test: int = 0
    counseling: int = 0
    volunteer: int = 0


class RoundCheck(RoundSummary):
    """`check_round` 결과. 숫자는 모두 규칙 함수가 계산합니다 (상세기획 2-2.6·2-2.12).

    `status`는 회차 상태(지난·지금·다음)이고, 활동 충족 여부는 `check_status`입니다.
    `required`가 None이면 규칙으로 셀 수 없어(대상기간이 28일이 아님 등) `check_status`가
    needs_check입니다.
    """

    d_day: int
    rule_group: str
    period_days: int
    required: int | None
    required_job_search: int | None
    counted: int
    counted_job_search: int
    remaining: int
    remaining_job_search: int
    check_status: CheckStatus
    weeks: list[WeekCheck] = []
    activities: list[ActivityCheck] = []
    warnings: list[RoundWarning] = []
    limits_used: LimitsUsed = LimitsUsed()
    rule_review: RuleReview = RuleReview.NOT_VERIFIED
    rule_refs: list[str] = []


class Recommendation(BaseModel):
    recommendation_id: str
    category: ActivityCategory
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
