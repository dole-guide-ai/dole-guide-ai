"""수급 절차 상태의 응답 스키마와 단계·수급자 유형·종료 사유 값 목록입니다."""

from datetime import date
from enum import StrEnum

from pydantic import BaseModel


class Stage(StrEnum):
    JOB_REGISTRATION = "job_registration"
    EDUCATION = "education"
    ELIGIBILITY_APPLICATION = "eligibility_application"
    ELIGIBILITY_APPLIED = "eligibility_applied"
    RECOGNITION = "recognition"
    ENDED = "ended"


class RecipientGroup(StrEnum):
    GENERAL = "general"
    AGE_60_64 = "age_60_64"
    AGE65_OR_DISABLED = "age65_or_disabled"
    REPEAT = "repeat"


class EndReason(StrEnum):
    PERIOD_EXPIRED = "period_expired"
    EXHAUSTED = "exhausted"
    EMPLOYED = "employed"


class ProcedureRead(BaseModel):
    stage: Stage
    recipient_group: RecipientGroup
    age_at_separation: int
    has_disability: bool
    separation_date: date
    education_done: bool
    eligibility_applied_on: date | None = None
    first_recognition_date: date | None = None
    benefit_days: int
    benefit_end_date: date | None = None
    period_end_date: date
    expected_end_date: date | None = None
    end_reason: EndReason | None = None
    # 회차가 만들어진 뒤에만 채웁니다 (F-33).
    # remaining_rounds: 오늘이 속한 회차를 포함한 남은 회차 수 · last_round: 마지막 회차 번호
    remaining_rounds: int | None = None
    last_round: int | None = None
    # 인터넷 사전제출 대상인지(이직일 만 65세 미만, PROC-048). 판정은 rules/presubmit 한 곳.
    online_presubmit: bool = True
