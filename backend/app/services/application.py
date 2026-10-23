"""회차별 실업인정 신청서를 조회하는 서비스입니다 (F-23).

신청서 행에는 본인 답변 칸만 저장하고, 구직활동 줄은 그 회차 대상기간의 인정 활동에서 매번 만듭니다.
지난 회차에 답한 통지 방법·실업크레딧은 이번 회차가 비어 있으면 불러와 보여 줍니다.
제출 방식·체크리스트(F-26)와 고치기·제출(F-27)은 이 서비스에 이어서 붙입니다.
"""

import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.repositories import accounts as repo
from app.repositories import activities as activity_repo
from app.rules import application as rules
from app.schemas.application import (
    ApplicationRead,
    Checklist,
    ExcludedRow,
    JobSearchRow,
    OtherActivityRow,
    SubmitMode,
)
from app.schemas.common import ErrorCode
from app.schemas.forms.recognition import RecognitionData
from app.services.accounts import AccountContext
from app.services.profile import read_profile_display

CURRENT = "current"
ROUND_NOT_FOUND_MESSAGE = "그 회차의 신청서가 없어요."


def _find_round(db: Session, user_id: uuid.UUID, round_ref: str, today: date):
    rounds = repo.list_rounds(db, user_id)
    if round_ref == CURRENT:
        found = next((r for r in rounds if r.period_start <= today <= r.recognition_date), None)
        if found is None:
            raise NotFoundError(code=ErrorCode.NO_ACTIVE_ROUND)
        return found, rounds
    found = next((r for r in rounds if r.round_no == int(round_ref)), None)
    if found is None:
        raise NotFoundError(message=ROUND_NOT_FOUND_MESSAGE)
    return found, rounds


def _previous_answers(db: Session, rounds: list, round_no: int) -> dict | None:
    """이번 회차 바로 전까지 제출한 회차 중 가장 최근 신청서의 답."""
    for r in reversed([r for r in rounds if r.round_no < round_no]):
        previous = repo.get_application(db, r.round_id)
        if previous is not None and previous.status == "submitted":
            return previous.data
    return None


def _activity_inputs(db: Session, user_id: uuid.UUID, start: date, end: date):
    return [
        rules.ActivityInput(
            activity_id=str(a.activity_id),
            activity_date=a.activity_date,
            category=a.category,
            kind=a.kind,
            route=a.route,
            org_name=a.org_name,
            job_title=a.job_title,
            search_method=a.search_method,
            apply_method=a.apply_method,
            contact_dept=a.contact_dept,
            result=a.result,
            planned=a.planned,
        )
        for a in activity_repo.list_between(db, user_id, start, end)
    ]


def read_application(
    db: Session, account: AccountContext, round_ref: str, today: date
) -> ApplicationRead:
    target, rounds = _find_round(db, account.user_id, round_ref, today)
    application = repo.get_application(db, target.round_id)
    if application is None:
        raise NotFoundError(message=ROUND_NOT_FOUND_MESSAGE)
    procedure = repo.get_procedure(db, account.user_id)
    group = procedure.recipient_group if procedure else "general"
    required, required_job_search = rules.required_activities(group, target.round_no)

    data = rules.carry_previous_answers(
        application.data, _previous_answers(db, rounds, target.round_no)
    )
    activities = rules.build_form_activities(
        _activity_inputs(db, account.user_id, target.period_start, target.period_end),
        target.period_start,
        target.period_end,
    )
    return ApplicationRead(
        round=target.round_no,
        status=application.status,
        lock_version=application.lock_version,
        period_start=target.period_start,
        period_end=target.period_end,
        recognition_date=target.recognition_date,
        attendance_required=target.attendance_required,
        required_activities=required,
        required_job_search=required_job_search,
        data=RecognitionData.model_validate(data),
        job_search_rows=[JobSearchRow.model_validate(row) for row in activities.job_search],
        other_rows=[OtherActivityRow.model_validate(row) for row in activities.other],
        excluded_rows=[ExcludedRow.model_validate(row) for row in activities.excluded],
        # 제출 방식·체크리스트는 F-26에서 규칙 함수로 계산합니다. 그 전에는 미리 보기로 둡니다.
        checklist=Checklist(),
        submit_mode=SubmitMode.PREVIEW,
        can_submit=False,
        locked_reason=rules.locked_reason(data),
        profile_display=read_profile_display(db, account.user_id),
    )
