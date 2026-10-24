"""user_profiles 테이블 모델입니다. 이력서 맨 위와 신청서에 보일 기본정보와 지급계좌를 담습니다.

값은 seed의 가상 값으로 고정이고, 계좌는 암호화해 저장하며 끝 4자리를 따로 둡니다.
이 테이블의 값은 LLM 입력, 로그, 트레이스에 넣지 않습니다.
"""

import uuid

from sqlalchemy import ForeignKey, Integer, LargeBinary, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class UserProfile(Base):
    """기본정보·계좌 (seed 고정 가상 값). LLM 입력·로그·트레이스에 넣지 않습니다."""

    __tablename__ = "user_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True
    )
    name: Mapped[str] = mapped_column(String(50))
    birth_year: Mapped[int | None] = mapped_column(Integer)
    gender: Mapped[str | None] = mapped_column(String(10))
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(100))
    address: Mapped[str | None] = mapped_column(String(200))
    bank_name: Mapped[str | None] = mapped_column(String(30))
    account_number_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    account_last4: Mapped[str | None] = mapped_column(String(4))
