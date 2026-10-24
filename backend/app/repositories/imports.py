"""고용24 불러오기 항목(work24_imports) 레포지토리입니다. 모든 조회는 user_id로 거릅니다."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Work24Import


def list_kind(db: Session, user_id: uuid.UUID, kind: str) -> list[Work24Import]:
    return list(
        db.scalars(
            select(Work24Import)
            .where(Work24Import.user_id == user_id, Work24Import.kind == kind)
            .order_by(Work24Import.position)
        )
    )


def get_many(db: Session, user_id: uuid.UUID, source_ids: list[str]) -> list[Work24Import]:
    """고른 항목을 같이 잠가 두 요청이 같은 항목을 두 번 넣지 않게 합니다."""
    return list(
        db.scalars(
            select(Work24Import)
            .where(Work24Import.user_id == user_id, Work24Import.source_id.in_(source_ids))
            .with_for_update()
        )
    )


def has_any(db: Session, user_id: uuid.UUID) -> bool:
    return (
        db.scalar(select(Work24Import.user_id).where(Work24Import.user_id == user_id).limit(1))
        is not None
    )
