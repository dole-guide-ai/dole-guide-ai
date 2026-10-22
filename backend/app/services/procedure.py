"""사용자가 고용센터에서 받은 사실을 입력하는 서비스입니다 (F-16).

교육 이수, 수급자격 신청일, 1차 실업인정일 세 가지를 받습니다.

입력은 절차 단계 순서대로 한 번씩만 받습니다. 1차 인정일이 들어오면 회차와 회차별 신청서를 만들고
실업인정 단계로 넘어갑니다. 회차를 고르거나 고치는 값은 받지 않습니다 (설계 3.4).
"""

from datetime import date

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, UnprocessableError
from app.repositories import accounts as repo
from app.rules import periods
from app.schemas.common import ErrorCode, FormName, FormUpdate, JsonPatchOp, UpdatesRead
from app.schemas.procedure import Stage
from app.services import accounts as account_service
from app.services.accounts import AccountContext

EDUCATION_DONE = "/education_done"
APPLIED_ON = "/eligibility_applied_on"
FIRST_RECOGNITION = "/first_recognition_date"

_ORDER_MESSAGE = {
    EDUCATION_DONE: "이력서를 저장한 뒤에 교육 이수를 표시할 수 있어요.",
    APPLIED_ON: "온라인 교육을 마친 뒤에 수급자격 신청일을 넣을 수 있어요.",
    FIRST_RECOGNITION: "수급자격 신청일을 넣은 뒤에 1차 실업인정일을 넣을 수 있어요.",
}
_ALREADY_MESSAGE = "이미 입력한 정보예요. 바꾸려면 고용센터에 문의해 주세요."


def patch_procedure(
    db: Session, account: AccountContext, patch: list[JsonPatchOp], today: date
) -> UpdatesRead:
    # 수급이 끝난 계정(stage = ended)은 아래 단계 순서 검사에서 409 STAGE_ORDER로 막힙니다.
    state = repo.get_procedure(db, account.user_id)
    updates: list[FormUpdate] = []
    for op in patch:
        if op.op == "remove":
            raise UnprocessableError(message="절차 정보는 지울 수 없어요.")
        if op.path == EDUCATION_DONE:
            updates += _education_done(db, account, state, op.value)
        elif op.path == APPLIED_ON:
            updates += _applied_on(state, _date(op.value), today)
        elif op.path == FIRST_RECOGNITION:
            updates += _first_recognition(db, account, state, _date(op.value))
        else:
            raise UnprocessableError(message="바꿀 수 없는 칸이에요.")
    db.commit()
    entry = account_service.read_account(db, account, today).entry
    return UpdatesRead(updates=updates, entry=entry.model_dump(mode="json"))


def _date(value: object) -> date:
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise UnprocessableError(message="날짜는 2026-10-21처럼 연-월-일로 넣어 주세요.") from None


def _update(path: str, value: object) -> FormUpdate:
    return FormUpdate(
        form=FormName.PROCEDURE, path=path, op="replace", value=value, source="user_answer"
    )


def _education_done(db: Session, account: AccountContext, state, value: object) -> list[FormUpdate]:
    """E6 → E5a. 이력서 저장(구직등록) 뒤에만, 한 번만 받습니다."""
    if value is not True:
        raise UnprocessableError(message="교육 이수는 true로만 표시할 수 있어요.")
    if state.education_done:
        raise ConflictError(code=ErrorCode.STAGE_ORDER, message=_ALREADY_MESSAGE)
    resume_ready = account_service.resume_is_saved(db, account.user_id)
    if state.stage not in (Stage.JOB_REGISTRATION, Stage.EDUCATION) or not resume_ready:
        raise ConflictError(code=ErrorCode.STAGE_ORDER, message=_ORDER_MESSAGE[EDUCATION_DONE])
    state.education_done = True
    state.stage = Stage.ELIGIBILITY_APPLICATION
    return [_update(EDUCATION_DONE, True), _update("/stage", Stage.ELIGIBILITY_APPLICATION)]


def _applied_on(state, applied: date, today: date) -> list[FormUpdate]:
    """E5a → E5b. 그만둔 다음 날부터 오늘까지의 날짜만 받습니다."""
    if state.eligibility_applied_on is not None:
        raise ConflictError(code=ErrorCode.STAGE_ORDER, message=_ALREADY_MESSAGE)
    if state.stage != Stage.ELIGIBILITY_APPLICATION:
        raise ConflictError(code=ErrorCode.STAGE_ORDER, message=_ORDER_MESSAGE[APPLIED_ON])
    if not state.separation_date < applied <= today:
        raise UnprocessableError(message="신청일은 그만둔 다음 날부터 오늘까지만 넣을 수 있어요.")
    state.eligibility_applied_on = applied
    state.stage = Stage.ELIGIBILITY_APPLIED
    return [_update(APPLIED_ON, applied.isoformat()), _update("/stage", Stage.ELIGIBILITY_APPLIED)]


def _first_recognition(
    db: Session, account: AccountContext, state, first: date
) -> list[FormUpdate]:
    """E5b → E4a. 대기기간(신청일부터 7일) 뒤 날짜만 받고, 회차와 회차별 신청서를 만듭니다."""
    if state.first_recognition_date is not None:
        raise ConflictError(code=ErrorCode.STAGE_ORDER, message=_ALREADY_MESSAGE)
    if state.stage != Stage.ELIGIBILITY_APPLIED or state.eligibility_applied_on is None:
        raise ConflictError(code=ErrorCode.STAGE_ORDER, message=_ORDER_MESSAGE[FIRST_RECOGNITION])
    applied = state.eligibility_applied_on
    end_date = periods.expected_end_date(
        periods.benefit_end_date(applied, state.benefit_days),
        periods.period_end_date(state.separation_date),
    )
    if not periods.first_recognition_in_range(applied, first, end_date):
        raise UnprocessableError(
            message=(
                "1차 실업인정일은 신청일부터 7일 대기기간이 지난 뒤, 수급기간 안의 날짜예요. "
                "안내문 날짜를 확인해 주세요."
            )
        )
    state.first_recognition_date = first
    state.stage = Stage.RECOGNITION
    account_service.create_rounds(db, account.user_id, state)
    return [
        _update(FIRST_RECOGNITION, first.isoformat()),
        _update("/stage", Stage.RECOGNITION),
    ]
