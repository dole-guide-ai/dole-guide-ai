"""화면용 대화 기록(messages)과 대화 턴 잠금 레포지토리입니다.

모든 조회는 user_id로 거릅니다. commit은 서비스가 합니다.
"""

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.models import Message, User


def try_lock_turn(db: Session, user_id: uuid.UUID) -> bool:
    """계정 행을 잠급니다(SELECT … FOR UPDATE NOWAIT). 다른 턴이 잡고 있으면 False.

    잠금은 이 세션의 트랜잭션이 끝날 때(commit·rollback) 풀립니다.
    """
    try:
        with db.begin_nested():
            db.execute(
                select(User.user_id).where(User.user_id == user_id).with_for_update(nowait=True)
            )
    except OperationalError:
        return False
    return True


def list_after(db: Session, user_id: uuid.UUID, cursor: int, limit: int) -> list[Message]:
    """seq가 cursor보다 큰 말풍선을 순서대로 limit개까지 돌려줍니다."""
    return list(
        db.scalars(
            select(Message)
            .where(Message.user_id == user_id, Message.seq > cursor)
            .order_by(Message.seq)
            .limit(limit)
        )
    )


def count(db: Session, user_id: uuid.UUID) -> int:
    return db.scalar(select(func.count()).where(Message.user_id == user_id)) or 0


def last(db: Session, user_id: uuid.UUID) -> Message | None:
    return db.scalar(
        select(Message).where(Message.user_id == user_id).order_by(Message.seq.desc()).limit(1)
    )


def next_seq(db: Session, user_id: uuid.UUID) -> int:
    current = db.scalar(select(func.max(Message.seq)).where(Message.user_id == user_id))
    return (current or 0) + 1


def add(
    db: Session,
    user_id: uuid.UUID,
    seq: int,
    role: str,
    kind: str,
    text: str | None,
    payload: dict[str, Any] | None,
) -> Message:
    message = Message(user_id=user_id, seq=seq, role=role, kind=kind, text=text, payload=payload)
    db.add(message)
    db.flush()
    return message
