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
from app.repositories import accounts as repo
from app.repositories import activities as activity_repo
from app.schemas.common import ErrorCode, FieldSource, JsonPatchOp, UpdatesRead
from app.services import accounts as account_service
from app.services.accounts import AccountContext
from app.services.application import CURRENT, find_round
from app.services.recommendations import activity_update

NOT_FOUND_MESSAGE = "활동을 찾지 못했어요."
CLOSED_MESSAGE = "지난 회차 활동은 고칠 수 없어요."
DATE_MESSAGE = "활동 날짜는 이번 회차 대상기간 안이어야 해요."
# 칸 이름 → 최대 글자 수. 날짜·시간은 따로 검사합니다.
TEXT_FIELDS = {
    "kind": 40,
    "route": 40,
    "org_name": 100,
    "job_title": 100,
    "search_method": 40,
    "apply_method": 40,
    "contact_dept": 100,
    "result": 100,
}
REQUIRED = {"activity_date", "kind"}


def patch_activity(
    db: Session, account: AccountContext, activity_id: str, patch: list[JsonPatchOp], today: date
) -> UpdatesRead:
    repo.lock_user(db, account.user_id)
    account_service.ensure_not_ended(db, account.user_id)
    activity = activity_repo.get(db, account.user_id, _uuid(activity_id))
    if activity is None:
        raise NotFoundError(message=NOT_FOUND_MESSAGE)
    target, _ = find_round(db, account.user_id, CURRENT, today)
    period = (target.period_start, target.recognition_date)
    if not period[0] <= activity.activity_date <= period[1]:
        raise ConflictError(code=ErrorCode.ROUND_CLOSED, message=CLOSED_MESSAGE)

    values = {op.path.removeprefix("/"): _value(index, op) for index, op in enumerate(patch)}
    new_date = values.get("activity_date", activity.activity_date)
    if not period[0] <= new_date <= period[1]:
        raise UnprocessableError(
            DATE_MESSAGE, details=[{"field": "activity_date", "reason": "out_of_round"}]
        )
    for name, value in values.items():
        setattr(activity, name, value)
    activity.source = FieldSource.DIRECT
    db.commit()
    return UpdatesRead(updates=[activity_update(activity, "replace")])


def _uuid(raw: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError:
        raise NotFoundError(message=NOT_FOUND_MESSAGE) from None


def _value(index: int, op: JsonPatchOp) -> Any:
    """칸 하나의 새 값. 틀리면 몇 번째 연산이 왜 틀렸는지만 422로 알립니다(입력값은 넣지 않음)."""
    name = op.path.removeprefix("/")

    def bad(reason: str) -> UnprocessableError:
        return UnprocessableError(
            "고칠 수 없는 칸이거나 형식이 맞지 않아요.",
            details=[{"field": f"patch[{index}]", "reason": reason}],
        )

    if name not in TEXT_FIELDS and name not in ("activity_date", "hours"):
        raise bad("unknown_path")
    if op.op == "remove" or op.value is None:
        if name in REQUIRED:
            raise bad("required")
        return None
    if name == "activity_date":
        try:
            return date.fromisoformat(op.value)
        except TypeError, ValueError:
            raise bad("date_format") from None
    if name == "hours":
        try:
            hours = Decimal(str(op.value))
        except InvalidOperation:
            raise bad("number") from None
        if not Decimal(0) <= hours <= Decimal(24):
            raise bad("number")
        return hours
    if not isinstance(op.value, str) or not 0 < len(op.value.strip()) <= TEXT_FIELDS[name]:
        raise bad("text")
    return op.value.strip()
