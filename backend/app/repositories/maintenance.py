"""정리 작업에 쓰는 쿼리를 모은 레포지토리입니다.

만료된 방문자와 그 계정 찾기·삭제, 24시간 지난 멱등성 키 삭제,
그리고 정리 작업이 여러 프로세스에서 겹쳐 돌지 않게 하는 Postgres advisory lock이 있습니다.
"""

import uuid
from datetime import datetime

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.models import IdempotencyKey, User, Visitor

# 정리 작업이 여러 프로세스에서 동시에 돌지 않게 잡는 Postgres advisory lock 번호
CLEANUP_LOCK_ID = 7_210_001


def try_lock(db: Session) -> bool:
    return bool(db.scalar(text("SELECT pg_try_advisory_xact_lock(:id)"), {"id": CLEANUP_LOCK_ID}))


def expired_user_ids(db: Session, now: datetime) -> list[uuid.UUID]:
    stmt = select(User.user_id).join(Visitor).where(Visitor.expires_at <= now)
    return list(db.scalars(stmt))


def delete_expired_visitors(db: Session, now: datetime) -> int:
    result = db.execute(delete(Visitor).where(Visitor.expires_at <= now))
    return result.rowcount or 0


def delete_old_idempotency_keys(db: Session, before: datetime) -> int:
    result = db.execute(delete(IdempotencyKey).where(IdempotencyKey.created_at < before))
    return result.rowcount or 0
