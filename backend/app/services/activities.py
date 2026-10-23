"""패널에서 구직활동 칸을 직접 고치는 서비스입니다 (F-12).

고칠 수 있는 칸만 받고 형식을 검사합니다. 이번 회차 대상기간 밖(지난 회차) 활동은 고칠 수 없고,
고친 활동은 출처가 직접 입력(direct)이 됩니다.
"""

import re
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
    PatchErrorType,
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
HOURS_DECIMALS = 1  # activities.hours는 Numeric(5, 1)
# fromisoformat은 20261021·주 날짜도 받아서 YYYY-MM-DD(ASCII 숫자)만 먼저 거릅니다.
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}", re.ASCII)
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

    if not patch:  # 고칠 칸이 없으면 출처도 바꾸지 않습니다.
        raise UnprocessableError(BAD_VALUE_MESSAGE)
    values = {_field(index, op): _value(index, op) for index, op in enumerate(patch)}
    if not in_round(values.get(ActivityField.ACTIVITY_DATE, activity.activity_date)):
        raise UnprocessableError(
            DATE_MESSAGE,
            details=[{"field": ActivityField.ACTIVITY_DATE, "type": PatchErrorType.OUT_OF_ROUND}],
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


def _bad(index: int, error_type: PatchErrorType) -> UnprocessableError:
    """몇 번째 연산이 왜 틀렸는지만 알립니다 (입력값은 넣지 않음)."""
    return UnprocessableError(
        BAD_VALUE_MESSAGE, details=[{"field": f"patch[{index}]", "type": error_type}]
    )


def _field(index: int, op: JsonPatchOp) -> ActivityField:
    try:
        return ActivityField(op.path.removeprefix("/"))
    except ValueError:
        raise _bad(index, PatchErrorType.UNKNOWN_PATH) from None


def _value(index: int, op: JsonPatchOp) -> Any:
    field = _field(index, op)
    # add·replace는 value가 꼭 있어야 합니다(RFC 6902). 명시한 null은 지우기로 봅니다.
    if op.op != PatchOpName.REMOVE and "value" not in op.model_fields_set:
        raise _bad(index, PatchErrorType.REQUIRED)
    if op.op == PatchOpName.REMOVE or op.value is None:
        if field in REQUIRED:
            raise _bad(index, PatchErrorType.REQUIRED)
        return None
    if field == ActivityField.ACTIVITY_DATE:
        if not isinstance(op.value, str) or not ISO_DATE.fullmatch(op.value):
            raise _bad(index, PatchErrorType.DATE_FORMAT)
        try:
            return date.fromisoformat(op.value)
        except ValueError:
            raise _bad(index, PatchErrorType.DATE_FORMAT) from None
    if field == ActivityField.HOURS:
        try:
            hours = Decimal(str(op.value))
        except InvalidOperation:
            raise _bad(index, PatchErrorType.NUMBER) from None
        # NaN은 비교에서 500이 나므로 먼저 거르고, 소수는 저장되는 자리수까지만 받습니다.
        if (
            not hours.is_finite()
            or hours.as_tuple().exponent < -HOURS_DECIMALS
            or not MIN_HOURS <= hours <= MAX_HOURS
        ):
            raise _bad(index, PatchErrorType.NUMBER)
        return hours
    text = op.value.strip() if isinstance(op.value, str) else ""
    if not 0 < len(text) <= TEXT_LIMITS[field]:
        raise _bad(index, PatchErrorType.TEXT)
    return text
