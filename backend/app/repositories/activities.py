"""구직활동 기록 조회 레포지토리입니다. 모든 조회는 user_id로 거릅니다."""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Activity


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


def count_done_kind(db: Session, user_id: uuid.UUID, kind: str) -> int:
    """이미 한(예정이 아닌) 활동 중 그 종류의 수. 누적 한도(특강 2회 등) 계산에 씁니다."""
    return len(
        db.scalars(
            select(Activity.activity_id).where(
                Activity.user_id == user_id, Activity.kind == kind, Activity.planned.is_(False)
            )
        ).all()
    )


def get(db: Session, user_id: uuid.UUID, activity_id: uuid.UUID) -> Activity | None:
    return db.scalar(
        select(Activity).where(Activity.user_id == user_id, Activity.activity_id == activity_id)
    )


def add(db: Session, activity: Activity) -> Activity:
    db.add(activity)
    db.flush()
    return activity
