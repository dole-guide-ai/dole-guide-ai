"""구직활동 기록 조회 레포지토리입니다. 모든 조회는 user_id로 거릅니다."""

import uuid
from datetime import date

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from app.models import Activity, activity_files


def list_between(db: Session, user_id: uuid.UUID, start: date, end: date) -> list[Activity]:
    """대상기간 안의 활동을 날짜·기록 순서대로 돌려줍니다.

    같은 날 대표가 동점이면 먼저 기록한 것을 고르므로, 기록 시각까지 같을 때도 순서가 바뀌지 않게
    활동 ID를 마지막 기준으로 둡니다.
    """
    return list(
        db.scalars(
            select(Activity)
            .where(
                Activity.user_id == user_id,
                Activity.activity_date >= start,
                Activity.activity_date <= end,
            )
            .order_by(Activity.activity_date, Activity.created_at, Activity.activity_id)
        )
    )


def list_done_org_names(db: Session, user_id: uuid.UUID, route: str) -> set[str]:
    """이미 한(예정이 아닌) 활동 중 그 경로로 지원한 회사 이름들. 불러오기 '이미 넣음'에 씁니다."""
    return set(
        db.scalars(
            select(Activity.org_name).where(
                Activity.user_id == user_id,
                Activity.route == route,
                Activity.org_name.is_not(None),
                Activity.planned.is_(False),
            )
        )
    )


def get(db: Session, user_id: uuid.UUID, activity_id: uuid.UUID) -> Activity | None:
    return db.scalar(
        select(Activity).where(Activity.user_id == user_id, Activity.activity_id == activity_id)
    )


def add(db: Session, activity: Activity) -> Activity:
    db.add(activity)
    db.flush()
    return activity


def list_all(db: Session, user_id: uuid.UUID) -> list[Activity]:
    """계정의 모든 활동을 날짜·기록 순서대로. 회차는 대상기간으로 나눠 씁니다."""
    return list(
        db.scalars(
            select(Activity)
            .where(Activity.user_id == user_id)
            .order_by(Activity.activity_date, Activity.created_at, Activity.activity_id)
        )
    )


def file_ids_by_activity(
    db: Session, activity_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[uuid.UUID]]:
    """활동마다 연결한 증빙 파일 ID. 활동 ID는 이미 user_id로 거른 것만 받습니다."""
    if not activity_ids:
        return {}
    rows = db.execute(
        select(activity_files.c.activity_id, activity_files.c.file_id).where(
            activity_files.c.activity_id.in_(activity_ids)
        )
    )
    found: dict[uuid.UUID, list[uuid.UUID]] = {}
    for activity_id, file_id in rows:
        found.setdefault(activity_id, []).append(file_id)
    return found


def link_files(db: Session, activity_id: uuid.UUID, file_ids: list[uuid.UUID]) -> None:
    if file_ids:
        db.execute(
            insert(activity_files),
            [{"activity_id": activity_id, "file_id": file_id} for file_id in file_ids],
        )


def remove(db: Session, activity: Activity) -> None:
    """활동을 지웁니다. 증빙 연결(activity_files)도 같이 지워집니다(CASCADE)."""
    db.execute(delete(Activity).where(Activity.activity_id == activity.activity_id))


def unlink_file(db: Session, activity_id: uuid.UUID, file_id: uuid.UUID) -> None:
    db.execute(
        delete(activity_files).where(
            activity_files.c.activity_id == activity_id, activity_files.c.file_id == file_id
        )
    )
