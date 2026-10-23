"""화면용 대화 말풍선(messages)과 대화 턴 잠금 레포지토리입니다."""

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.models import Message, User
from app.schemas.messages import MessageKind, MessageRole


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


def next_seq(db: Session, user_id: uuid.UUID) -> int:
    last = db.scalar(select(func.max(Message.seq)).where(Message.user_id == user_id))
    return (last or 0) + 1


def add(
    db: Session,
    user_id: uuid.UUID,
    role: MessageRole,
    kind: MessageKind,
    text: str | None,
    payload: dict[str, Any] | None = None,
) -> Message:
    message = Message(
        user_id=user_id,
        seq=next_seq(db, user_id),
        role=role.value,
        kind=kind.value,
        text=text,
        payload=payload,
    )
    db.add(message)
    db.flush()
    return message


def list_after(
    db: Session, user_id: uuid.UUID, cursor: int, limit: int
) -> tuple[list[Message], int]:
    """seq가 cursor보다 큰 말풍선을 오래된 순으로 최대 limit개, 그리고 전체 개수.

    다음 페이지가 있는지 알려면 limit을 하나 크게 넘깁니다.
    """
    rows = db.scalars(
        select(Message)
        .where(Message.user_id == user_id, Message.seq > cursor)
        .order_by(Message.seq)
        .limit(limit)
    ).all()
    total = db.scalar(select(func.count()).where(Message.user_id == user_id)) or 0
    return list(rows), total


def last(db: Session, user_id: uuid.UUID) -> Message | None:
    return db.scalar(
        select(Message).where(Message.user_id == user_id).order_by(Message.seq.desc()).limit(1)
    )
