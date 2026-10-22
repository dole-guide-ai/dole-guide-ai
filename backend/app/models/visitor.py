"""visitors 테이블 모델입니다. 브라우저 하나가 방문자 하나입니다.

토큰 원문은 저장하지 않고 해시만 두며, 마지막 접속 시각과 만료 시각으로 7일 뒤 정리 대상을
고릅니다.
방문자를 지우면 그 방문자의 계정과 모든 데이터가 함께 지워집니다.
"""

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._columns import CreatedAt, UuidPk


class Visitor(Base):
    """브라우저 하나. 토큰 원문은 저장하지 않고 해시만 둡니다."""

    __tablename__ = "visitors"

    visitor_id: Mapped[UuidPk]
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[CreatedAt]
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    def __repr__(self) -> str:
        return f"Visitor({self.visitor_id})"
