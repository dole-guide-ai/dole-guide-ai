"""구직활동을 만들고 보여 주는 요청·응답 스키마입니다.

직접 기록할 때는 날짜와 활동 값을, 추천을 예정 활동으로 넣을 때는 추천 ID만 보냅니다.
응답의 회차 번호는 저장된 값이 아니라 대상기간으로 계산한 값입니다.
"""

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, model_validator


class ActivityCategory(StrEnum):
    JOB_SEARCH = "job_search"
    NON_JOB_SEARCH = "non_job_search"


class ActivityField(StrEnum):
    """패널에서 직접 고칠 수 있는 활동 칸 (F-12). 값은 activities 컬럼 이름과 같습니다."""

    ACTIVITY_DATE = "activity_date"
    KIND = "kind"
    ROUTE = "route"
    ORG_NAME = "org_name"
    JOB_TITLE = "job_title"
    SEARCH_METHOD = "search_method"
    APPLY_METHOD = "apply_method"
    CONTACT_DEPT = "contact_dept"
    RESULT = "result"
    HOURS = "hours"


class ActivityRoute(StrEnum):
    """지원·참여 경로 (상세기획 2-2.2). 필요 증빙을 정하고(규칙 표 routes), 신청서 칸은 아닙니다."""

    WORK24 = "work24"
    PORTAL = "portal"
    EMAIL = "email"
    COMPANY_SITE = "company_site"
    NEWSPAPER = "newspaper"
    MAIL = "mail"
    FAX = "fax"
    VISIT = "visit"
    REFERRAL = "referral"
    INTERVIEW = "interview"
    JOB_FAIR = "job_fair"
    TRAINING = "training"
    CENTER = "center"
    STEP_ONLINE = "step_online"


class SearchMethod(StrEnum):
    """구직 방법 (신청서 ★칸, 고용24 선택지 그대로)."""

    CENTER = "고용센터(알선,정보제공)"
    REFERRAL = "친지,학교등의 소개"
    NEWSPAPER = "신문광고(지면,인터넷)"
    OTHER = "기타"
    PORTAL = "취업포탈사이트(민간)"
    WORK24 = "고용24(워크넷)"


class ApplyMethod(StrEnum):
    """응모 방식 (신청서 ★칸, 고용24 선택지 그대로). 경로로 코드가 정합니다 (2-3.4)."""

    OTHER = "기타"
    VISIT = "직접방문"
    FAX = "FAX"
    EMAIL = "전자메일"
    WORK24 = "고용24(워크넷)"
    MAIL = "우편"


class ActivityResult(StrEnum):
    """활동 결과 (신청서 ★칸, 고용24 선택지 9개)."""

    DOCUMENT_REVIEW = "서류전형 심사진행 중"
    DOCUMENT_FAILED = "서류전형 불합격"
    INTERVIEW_FAILED = "면접 불합격"
    INTERVIEW_SCHEDULED = "면접통보 받고 면접 응할 예정"
    INTERVIEW_SKIPPED = "면접통보 받았으나 불참"
    HIRED = "최종 합격, 입사 예정"
    HIRED_DECLINED = "최종 합격, 입사 거부(포기)"
    FINAL_FAILED = "최종 불합격"
    AWAITING_RESULT = "면접을 본 후 결과를 기다리는 중"


# 정해진 선택지만 받는 활동 칸 (데이터 설계 7.1 Enum 검증)
CHOICE_FIELDS: dict[str, type[StrEnum]] = {
    "route": ActivityRoute,
    "search_method": SearchMethod,
    "apply_method": ApplyMethod,
    "result": ActivityResult,
}


class ActivityCreate(BaseModel):
    """직접 기록하거나, `recommendation_id`로 추천을 예정 활동으로 넣습니다."""

    recommendation_id: str | None = None
    activity_date: date | None = None
    category: ActivityCategory | None = None
    kind: str | None = None
    route: ActivityRoute | None = None
    org_name: str | None = None
    job_title: str | None = None
    hours: float | None = None
    file_ids: list[str] = []

    @model_validator(mode="after")
    def need_date_or_recommendation(self) -> ActivityCreate:
        if self.recommendation_id is None and self.activity_date is None:
            raise ValueError("activity_date 또는 recommendation_id가 필요합니다.")
        return self


class ActivityRead(BaseModel):
    activity_id: str
    activity_date: date
    round: int | None
    category: ActivityCategory
    kind: str
    route: str | None = None
    org_name: str | None = None
    job_title: str | None = None
    hours: float | None = None
    planned: bool
    source: str
    status: str | None = None
    file_ids: list[str] = []
