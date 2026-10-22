"""화면용 대화 기록(messages) 레포지토리입니다. 모든 조회는 user_id로 거릅니다."""

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Message


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
