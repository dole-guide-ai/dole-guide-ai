"""절차 사실 입력 (F-16·F-28, 설계 3.4·6.5).

사용자가 입력하는 것은 고용센터에서 받은 사실 세 가지뿐이고, 각각 한 번만 넣습니다.
교육 이수 → 수급자격 신청일 → 1차 인정일 순서이며, 1차 인정일이 들어오면 서버가 종료 예정일까지
회차와 회차별 신청서를 한꺼번에 만듭니다. 회차를 고르거나 바꾸는 값은 없습니다.
"""

from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, UnprocessableError
from app.repositories import accounts as repo
from app.rules import periods
from app.schemas.common import (
    ErrorCode,
    FormName,
    FormUpdate,
    JsonPatchOp,
    PatchErrorType,
    PatchOpName,
    UpdatesRead,
)
from app.schemas.procedure import Stage
from app.services import accounts as account_service
from app.services.accounts import AccountContext

ALREADY_MESSAGE = "이미 입력한 날짜예요. 바꾸려면 고용센터에 문의해 주세요."
ORDER_MESSAGE = "아직 이 단계가 아니에요."
ONE_FIELD_MESSAGE = "한 번에 한 가지만 입력해 주세요."
DATE_MESSAGE = "날짜를 확인해 주세요."
NOT_FOUND_MESSAGE = "절차 정보를 찾지 못했어요."


class ProcedureField(StrEnum):
    """사용자가 입력하는 고용센터 사실 (설계 3.4)."""

    EDUCATION_DONE = "/education_done"
    ELIGIBILITY_APPLIED_ON = "/eligibility_applied_on"
    FIRST_RECOGNITION_DATE = "/first_recognition_date"


# 칸마다 입력할 수 있는 단계와 입력한 뒤의 단계
_STAGE_FOR = {
    ProcedureField.EDUCATION_DONE: (Stage.EDUCATION, Stage.ELIGIBILITY_APPLICATION),
    ProcedureField.ELIGIBILITY_APPLIED_ON: (
        Stage.ELIGIBILITY_APPLICATION,
        Stage.ELIGIBILITY_APPLIED,
    ),
    ProcedureField.FIRST_RECOGNITION_DATE: (Stage.ELIGIBILITY_APPLIED, Stage.RECOGNITION),
}


def _bad(error_type: PatchErrorType, message: str = DATE_MESSAGE) -> UnprocessableError:
    return UnprocessableError(message, details=[{"field": "patch[0]", "type": error_type}])


def _date(value: Any) -> date:
    if not isinstance(value, str):
        raise _bad(PatchErrorType.DATE_FORMAT)
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise _bad(PatchErrorType.DATE_FORMAT) from None


def patch_procedure(
    db: Session, account: AccountContext, patch: list[JsonPatchOp], now: datetime
) -> UpdatesRead:
    """고용센터 사실 하나를 입력하고 바뀐 단계와 첫 화면(entry)을 돌려줍니다.

    순서가 틀리거나 이미 넣은 값이면 409 STAGE_ORDER, 날짜가 틀리면 422입니다.
    """
    today = now.date()
    repo.lock_user(db, account.user_id)
    account_service.ensure_not_ended(db, account.user_id)
    state = repo.get_procedure(db, account.user_id)
    if state is None:
        raise NotFoundError(message=NOT_FOUND_MESSAGE)
    if len(patch) != 1 or patch[0].op != PatchOpName.REPLACE:
        raise _bad(PatchErrorType.TOO_MANY, ONE_FIELD_MESSAGE)
    op = patch[0]
    try:
        field = ProcedureField(op.path)
    except ValueError:
        raise _bad(PatchErrorType.UNKNOWN_PATH, ORDER_MESSAGE) from None
    allowed, next_stage = _STAGE_FOR[field]
    if state.stage != allowed:
        # 이미 지난 단계면 이미 입력한 값입니다(각 한 번만, 설계 3.4).
        message = ALREADY_MESSAGE if _passed(state.stage, allowed) else ORDER_MESSAGE
        raise ConflictError(code=ErrorCode.STAGE_ORDER, message=message)

    updates: list[FormUpdate] = []
    if field == ProcedureField.EDUCATION_DONE:
        if op.value is not True:
            raise _bad(PatchErrorType.BAD_SHAPE, ORDER_MESSAGE)
        state.education_done = True
        updates.append(_update("/education_done", True))
    elif field == ProcedureField.ELIGIBILITY_APPLIED_ON:
        applied = _date(op.value)
        # 이직일 뒤, 오늘까지 (센터에서 이미 신청한 날)
        if not state.separation_date < applied <= today:
            raise _bad(PatchErrorType.OUT_OF_ROUND)
        state.eligibility_applied_on = applied
        updates.append(_update("/eligibility_applied_on", applied.isoformat()))
    else:
        first = _date(op.value)
        applied = state.eligibility_applied_on
        # 1차 대상기간 시작일(신청일 + 대기기간 7일) 뒤여야 합니다 (설계 6.5).
        if applied is None or first < applied + timedelta(days=periods.WAITING_DAYS):
            raise _bad(PatchErrorType.OUT_OF_ROUND)
        state.first_recognition_date = first
        account_service.create_rounds(db, account.user_id, state)
        updates.append(_update("/first_recognition_date", first.isoformat()))

    state.stage = next_stage
    state.lock_version += 1
    updates.append(_update("/stage", next_stage.value))
    db.commit()
    entry = account_service.read_account(db, account, now).entry
    return UpdatesRead(updates=updates, entry=entry.model_dump(mode="json"))


_ORDER = list(Stage)


def _passed(stage: str, allowed: Stage) -> bool:
    return _ORDER.index(Stage(stage)) > _ORDER.index(allowed)


def _update(path: str, value: Any) -> FormUpdate:
    return FormUpdate(form=FormName.PROCEDURE, path=path, op=PatchOpName.REPLACE, value=value)
