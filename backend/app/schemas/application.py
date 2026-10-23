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
    data: RecognitionData
    job_search_rows: list[JobSearchRow] = []
    checklist: Checklist
    submit_mode: SubmitMode
    can_submit: bool
    locked_reason: LockedReason | None = None
    profile_display: ProfileDisplay | None = None
