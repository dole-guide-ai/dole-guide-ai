"""구직활동 기록·목록·빼기 (F-17·F-20, 상세기획 2-2.5·2-2.11).

활동은 날짜만 저장하고 회차는 대상기간으로 계산합니다. 넣거나 빼면 회차 점검을 다시 계산해
바뀐 칸(updates)으로 돌려줍니다. 지난 회차 활동은 넣거나 뺄 수 없습니다(409 ROUND_CLOSED).
"""

import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, UnprocessableError
from app.models import Activity
from app.repositories import accounts as repo
from app.repositories import activities as activity_repo
from app.repositories import files as file_repo
from app.rules.activity_table import load_rules
from app.schemas.activities import ActivityCreate, ActivityRead
from app.schemas.common import ErrorCode, FieldSource, Page, UpdatesRead
from app.schemas.files import FilePurpose
from app.services import accounts as account_service
from app.services import idempotency
from app.services import recommendations as recommendation_service
from app.services import rounds as round_service
from app.services.accounts import AccountContext

DUPLICATE_MESSAGE = "이미 기록한 활동이에요."
ROUND_CLOSED_MESSAGE = "지난 회차 활동은 넣거나 뺄 수 없어요."
CATEGORY_MESSAGE = "어떤 활동인지(구직활동·구직 외 활동) 알려 주세요."
ACTIVITY_NOT_FOUND_MESSAGE = "그 활동을 찾지 못했어요."
FILE_NOT_FOUND_MESSAGE = "증빙 파일을 찾지 못했어요."


def _org_key(name: str | None) -> str:
    return "".join((name or "").split())


def list_activities(
    db: Session, account: AccountContext, round_no: int | None, today: date
) -> Page[ActivityRead]:
    """활동 목록. 회차는 대상기간으로 계산하고, 지금 회차 활동에는 계산 결과(status)를 붙입니다."""
    rounds = repo.list_rounds(db, account.user_id)
    activities = activity_repo.list_all(db, account.user_id)
    files = activity_repo.file_ids_by_activity(db, [a.activity_id for a in activities])
    statuses: dict[str, str] = {}
    if round_service.round_of(rounds, today) is not None:
        result = round_service.evaluate(db, account.user_id, today).result
        statuses = {a.activity_id: a.status for a in result.activities}
    items = []
    for a in activities:
        found = round_service.round_of(rounds, a.activity_date)
        number = found.round_no if found else None
        if round_no is not None and number != round_no:
            continue
        items.append(
            ActivityRead(
                activity_id=str(a.activity_id),
                activity_date=a.activity_date,
                round=number,
                category=a.category,
                kind=a.kind,
                route=a.route,
                org_name=a.org_name,
                job_title=a.job_title,
                hours=float(a.hours) if a.hours is not None else None,
                planned=a.planned,
                source=a.source,
                status=statuses.get(str(a.activity_id)),
                file_ids=[str(f) for f in files.get(a.activity_id, [])],
            )
        )
    return Page(items=items, total=len(items))


def _ensure_open(db: Session, user_id: uuid.UUID, day: date, today: date) -> None:
    """지금 회차 대상기간보다 앞선 날짜는 지난 회차라 바꿀 수 없습니다."""
    rounds = repo.list_rounds(db, user_id)
    current = round_service.current_round(rounds, today)
    if day < current.period_start:
        raise ConflictError(code=ErrorCode.ROUND_CLOSED, message=ROUND_CLOSED_MESSAGE)


def _evidence_files(db: Session, user_id: uuid.UUID, file_ids: list[str]) -> list[uuid.UUID]:
    found = []
    for raw in file_ids:
        try:
            file_id = uuid.UUID(raw)
        except ValueError:
            raise NotFoundError(message=FILE_NOT_FOUND_MESSAGE) from None
        file = file_repo.get_for_user(db, user_id, file_id)
        if file is None or file.purpose != FilePurpose.EVIDENCE:
            raise NotFoundError(message=FILE_NOT_FOUND_MESSAGE)
        found.append(file_id)
    return found


def record_activity(
    db: Session, account: AccountContext, body: ActivityCreate, today: date
) -> UpdatesRead:
    """활동을 직접 기록합니다. 구분은 종류로 코드가 정하고(2-2.3 표), 오늘보다 뒤면 예정입니다.

    날짜·종류·회사가 같은 활동이 있으면 넣지 않고 409 DUPLICATE_ACTIVITY (2-2.11).
    """
    # 같은 활동이 동시에 두 번 와도 중복 검사와 저장이 겹치지 않게 계정 단위로 줄 세웁니다.
    repo.lock_user(db, account.user_id)
    account_service.ensure_not_ended(db, account.user_id)
    day = body.activity_date
    assert day is not None  # ActivityCreate가 날짜 또는 추천 ID를 요구합니다
    _ensure_open(db, account.user_id, day, today)
    rule = load_rules().kind(body.kind) if body.kind else None
    category = rule.category if rule else body.category
    if category is None or not body.kind:
        raise UnprocessableError(message=CATEGORY_MESSAGE)
    duplicate = any(
        a.activity_date == day
        and a.kind == body.kind
        and _org_key(a.org_name) == _org_key(body.org_name)
        for a in activity_repo.list_between(db, account.user_id, day, day)
    )
    if duplicate:
        raise ConflictError(code=ErrorCode.DUPLICATE_ACTIVITY, message=DUPLICATE_MESSAGE)
    file_ids = _evidence_files(db, account.user_id, body.file_ids)

    activity = activity_repo.add(
        db,
        Activity(
            user_id=account.user_id,
            activity_date=day,
            category=category,
            kind=body.kind,
            route=body.route,
            org_name=body.org_name,
            job_title=body.job_title,
            hours=body.hours,
            source=FieldSource.DIRECT,
            planned=day > today,
        ),
    )
    activity_repo.link_files(db, activity.activity_id, file_ids)
    return UpdatesRead(
        updates=[
            round_service.activity_update(activity),
            round_service.round_check_update(db, account.user_id, today),
        ]
    )


def create_activity(
    db: Session,
    account: AccountContext,
    body: ActivityCreate,
    idempotency_key: str | None,
    today: date,
) -> UpdatesRead:
    """`POST /activities`: 추천 넣기(recommendation_id) 또는 직접 기록."""
    if body.recommendation_id is not None:
        recommendation = body.recommendation_id

        def create() -> UpdatesRead:
            return recommendation_service.add_recommended(db, account, recommendation, today)
    else:

        def create() -> UpdatesRead:
            return record_activity(db, account, body, today)

    return idempotency.run_once(
        db, account.user_id, idempotency_key, body.model_dump(mode="json"), UpdatesRead, create
    )


def delete_activity(
    db: Session, account: AccountContext, activity_id: str, today: date
) -> UpdatesRead:
    """활동을 빼고 다시 계산한 회차 점검을 돌려줍니다 (F-20).

    같은 날이라 빠졌던 활동이 인정으로 바뀔 수 있습니다.
    """
    account_service.ensure_not_ended(db, account.user_id)
    try:
        parsed = uuid.UUID(activity_id)
    except ValueError:
        raise NotFoundError(message=ACTIVITY_NOT_FOUND_MESSAGE) from None
    activity = activity_repo.get(db, account.user_id, parsed)
    if activity is None:
        raise NotFoundError(message=ACTIVITY_NOT_FOUND_MESSAGE)
    _ensure_open(db, account.user_id, activity.activity_date, today)
    removed = round_service.activity_update(activity, "remove")
    activity_repo.remove(db, activity)
    db.flush()
    result = UpdatesRead(
        updates=[removed, round_service.round_check_update(db, account.user_id, today)]
    )
    db.commit()
    return result
