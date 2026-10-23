"""실업인정 신청서 조회 응답 스키마입니다.

본인 답변 칸, 인정 활동에서 만든 구직활동 줄, 제출을 막는 항목과 경고, 지금 시각 기준 제출 방식,
잠금 사유(취업·산재), 신청인·지급계좌 표시값이 들어갑니다. 칸 구조 자체는 forms/recognition.py에
있습니다.
"""

from datetime import date
from enum import StrEnum

from pydantic import BaseModel

from app.schemas.forms.recognition import RecognitionData
from app.schemas.profile import ProfileDisplay
from app.schemas.rounds import ApplicationStatus


class SubmitMode(StrEnum):
    ATTEND = "attend"
    PREVIEW = "preview"
    SEND = "send"
    VISIT_TODAY = "visit_today"
    CHANGE = "change"


class LockedReason(StrEnum):
    EMPLOYED = "employed"
    INDUSTRIAL_ACCIDENT = "industrial_accident"


class JobSearchRow(BaseModel):
    """구직활동 10칸 한 줄. 인정 활동에서 매번 만들고 저장하지 않습니다."""

    activity_id: str
    activity_date: date
    company_name: str | None = None
    recruitment_contact: str | None = None
    recruitment_occupation: str | None = None
    salary_level: str | None = None
    job_search_method: str | None = None
    application_method: str | None = None
    activity_result: str | None = None
    file_ids: list[str] = []


class OtherActivityRow(BaseModel):
    """구직활동 외 활동사항 한 줄 (취업특강·직업훈련 등). 인정 활동에서 만듭니다."""

    activity_id: str
    activity_date: date
    kind: str
    details: str | None = None


class ExcludedRow(BaseModel):
    """계산에서 뺀 활동 (같은 날 2건째 등). 신청서에는 넣지 않고 참고로만 보여 줍니다."""

    activity_id: str
    reason: str
    activity_date: date
    company_name: str | None = None


class ChecklistItem(BaseModel):
    key: str
    text: str


class Checklist(BaseModel):
    blocking: list[ChecklistItem] = []
    warnings: list[ChecklistItem] = []


class ApplicationRead(BaseModel):
    round: int
    status: ApplicationStatus
    lock_version: int
    # 실업인정 정보등록 칸 (회차에서 계산, F-23)
    period_start: date
    period_end: date
    recognition_date: date
    attendance_required: bool
    required_activities: int
    required_job_search: int
    data: RecognitionData
    job_search_rows: list[JobSearchRow] = []
    other_rows: list[OtherActivityRow] = []
    excluded_rows: list[ExcludedRow] = []
    checklist: Checklist
    submit_mode: SubmitMode
    can_submit: bool
    locked_reason: LockedReason | None = None
    profile_display: ProfileDisplay | None = None
