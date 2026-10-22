"""users 테이블 모델입니다. 방문자 한 명이 고른 시연 계정 하나가 행 하나입니다.

같은 방문자는 같은 계정을 하나만 가질 수 있어, 카드를 다시 고르면 기존 행으로 이어서 진행합니다.
anchor_date는 seed의 상대 날짜를 실제 날짜로 바꿀 때 기준이 된 입장일입니다.
이력서·회차·활동 등 모든 계정 데이터가 user_id로 이 행에 묶입니다.
"""

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._columns import CreatedAt, UuidPk


class User(Base):
    """방문자 한 명이 고른 시연 계정 하나. 모든 계정 데이터가 user_id로 묶입니다."""

    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("visitor_id", "persona_id"),)

    user_id: Mapped[UuidPk]
    visitor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("visitors.visitor_id", ondelete="CASCADE")
    )
    persona_id: Mapped[str] = mapped_column(String(32), ForeignKey("personas.persona_id"))
    # seed의 상대 날짜(T±n일)를 실제 날짜로 바꾼 기준일 = 입장일
    anchor_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[CreatedAt]
