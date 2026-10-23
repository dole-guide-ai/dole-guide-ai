"""화면용 대화 기록 조회·저장과 멈춘 질문 복원 (F-03).

대화 턴(F-07)이 끝날 때 `save_turn`으로 그 턴의 말풍선을 저장하고, 새로고침하면
`GET /messages`로 대화를, `AccountRead.pending_ask`로 답을 기다리던 질문과 선택지를 되살립니다.
LangGraph 체크포인터와는 따로 둡니다.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.repositories import messages as repo
from app.schemas.messages import AskUserEvent, MessageKind, MessageList, MessageRead, MessageRole

PAGE_SIZE = 100


@dataclass
class TurnMessage:
    """턴 하나에서 화면에 남길 말풍선.

    `ask_user`면 payload에 question_id·choices·import_kind·accepts_file을 둡니다.
    """

    role: MessageRole
    kind: MessageKind
    text: str | None
    payload: dict[str, Any] | None = field(default=None)


def list_messages(db: Session, user_id: uuid.UUID, cursor: int | None) -> MessageList:
    after = cursor or 0
    rows = repo.list_after(db, user_id, after, PAGE_SIZE + 1)
    has_more = len(rows) > PAGE_SIZE
    rows = rows[:PAGE_SIZE]
    return MessageList(
        items=[MessageRead.model_validate(row, from_attributes=True) for row in rows],
        total=repo.count(db, user_id),
        next_cursor=rows[-1].seq if has_more else None,
    )


def pending_ask(db: Session, user_id: uuid.UUID) -> AskUserEvent | None:
    """마지막 말풍선이 질문(ask_user)이면 아직 답하지 않은 것이므로 그 질문을 돌려줍니다.

    질문 말풍선의 payload는 ask_user 이벤트를 그대로 담은 것이라 같은 모양으로 되살립니다.
    """
    last = repo.last(db, user_id)
    if last is None or last.kind != MessageKind.ASK_USER or not last.payload:
        return None
    # 질문 글은 말풍선 text에 있으므로 payload와 합쳐 되살립니다.
    return AskUserEvent.model_validate({**last.payload, "text": last.text or ""})


def save_turn(db: Session, user_id: uuid.UUID, messages: list[TurnMessage]) -> None:
    """턴이 끝날 때 그 턴의 말풍선을 이어서 저장합니다(commit은 턴을 마치는 쪽이 합니다)."""
    seq = repo.next_seq(db, user_id)
    for offset, message in enumerate(messages):
        repo.add(
            db,
            user_id,
            seq + offset,
            MessageRole(message.role).value,
            MessageKind(message.kind).value,
            message.text,
            message.payload,
        )
