"""패널에서 구직활동 칸을 직접 고치는 서비스입니다 (F-12).

고칠 수 있는 칸만 받고 형식을 검사합니다. 이번 회차 대상기간 밖(지난 회차) 활동은 고칠 수 없고,
고친 활동은 출처가 직접 입력(direct)이 됩니다.
"""

import uuid
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, UnprocessableError
from app.models import Activity
from app.repositories import accounts as repo
from app.repositories import activities as activity_repo
from app.schemas.activities import ActivityField
from app.schemas.common import (
    ErrorCode,
    FieldSource,
    JsonPatchOp,
    PatchErrorReason,
    PatchOpName,
    UpdatesRead,
)
from app.services import accounts as account_service
from app.services.accounts import AccountContext
from app.services.application import CURRENT, find_round
from app.services.recommendations import activity_update

NOT_FOUND_MESSAGE = "활동을 찾지 못했어요."
DATE_MESSAGE = "활동 날짜는 이번 회차 대상기간 안이어야 해요."
BAD_VALUE_MESSAGE = "고칠 수 없는 칸이거나 형식이 맞지 않아요."
MIN_HOURS = Decimal(0)
MAX_HOURS = Decimal(24)  # 하루 활동 시간
# 지울 수 없는 칸
REQUIRED = {ActivityField.ACTIVITY_DATE, ActivityField.KIND}
# 글자 칸은 컬럼 길이까지 받습니다.
TEXT_LIMITS = {
    f: Activity.__table__.c[f].type.length
    for f in ActivityField
    if f not in (ActivityField.ACTIVITY_DATE, ActivityField.HOURS)
}


def patch_activity(
    db: Session, account: AccountContext, activity_id: str, patch: list[JsonPatchOp], today: date
) -> UpdatesRead:
    repo.lock_user(db, account.user_id)
    account_service.ensure_not_ended(db, account.user_id)
    activity = activity_repo.get(db, account.user_id, _uuid(activity_id))
    if activity is None:
        raise NotFoundError(message=NOT_FOUND_MESSAGE)
    target, _ = find_round(db, account.user_id, CURRENT, today)

    def in_round(day: date) -> bool:
        return target.period_start <= day <= target.recognition_date

    if not in_round(activity.activity_date):
        raise ConflictError(code=ErrorCode.ROUND_CLOSED)

    values = {_field(index, op): _value(index, op) for index, op in enumerate(patch)}
    if not in_round(values.get(ActivityField.ACTIVITY_DATE, activity.activity_date)):
        raise UnprocessableError(
            DATE_MESSAGE,
            details=[
                {"field": ActivityField.ACTIVITY_DATE, "reason": PatchErrorReason.OUT_OF_ROUND}
            ],
        )
    for field, value in values.items():
        setattr(activity, field, value)
    activity.source = FieldSource.DIRECT
    db.commit()
    return UpdatesRead(updates=[activity_update(activity, PatchOpName.REPLACE)])


def _uuid(raw: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError:
        raise NotFoundError(message=NOT_FOUND_MESSAGE) from None


def _bad(index: int, reason: PatchErrorReason) -> UnprocessableError:
    """몇 번째 연산이 왜 틀렸는지만 알립니다 (입력값은 넣지 않음)."""
    return UnprocessableError(
        BAD_VALUE_MESSAGE, details=[{"field": f"patch[{index}]", "reason": reason}]
    )


def _field(index: int, op: JsonPatchOp) -> ActivityField:
    try:
        return ActivityField(op.path.removeprefix("/"))
    except ValueError:
        raise _bad(index, PatchErrorReason.UNKNOWN_PATH) from None


def _value(index: int, op: JsonPatchOp) -> Any:
    field = _field(index, op)
    if op.op == PatchOpName.REMOVE or op.value is None:
        if field in REQUIRED:
            raise _bad(index, PatchErrorReason.REQUIRED)
        return None
    if field == ActivityField.ACTIVITY_DATE:
        try:
            return date.fromisoformat(op.value)
        except TypeError, ValueError:
            raise _bad(index, PatchErrorReason.DATE_FORMAT) from None
    if field == ActivityField.HOURS:
        try:
            hours = Decimal(str(op.value))
        except InvalidOperation:
            raise _bad(index, PatchErrorReason.NUMBER) from None
        if not MIN_HOURS <= hours <= MAX_HOURS:
            raise _bad(index, PatchErrorReason.NUMBER)
        return hours
    text = op.value.strip() if isinstance(op.value, str) else ""
    if not 0 < len(text) <= TEXT_LIMITS[field]:
        raise _bad(index, PatchErrorReason.TEXT)
    return text
