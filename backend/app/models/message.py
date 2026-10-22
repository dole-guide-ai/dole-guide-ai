"""messages 테이블 모델입니다. 화면에 보일 대화 말풍선을 순서(seq)대로 담습니다.

대화 턴이 끝날 때 저장해서 새로고침해도 대화가 그대로 보이게 합니다. LangGraph 체크포인터와는 따로
둡니다.
"""

import uuid
from typing import Any

from sqlalchemy import Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._columns import CreatedAt, UuidPk, user_fk


class Message(Base):
    """화면용 대화 기록. 턴이 끝날 때 저장해 새로고침 때 복원합니다(체크포인터와 분리)."""

    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_user_seq", "user_id", "seq", unique=True),)

    message_id: Mapped[UuidPk]
    user_id: Mapped[uuid.UUID] = user_fk()
    seq: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(10))
    kind: Mapped[str] = mapped_column(String(20))
    text: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[CreatedAt]
