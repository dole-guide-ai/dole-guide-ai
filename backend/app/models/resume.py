"""resumes 테이블 모델입니다. 계정당 이력서 하나를 담습니다.

버전 없이 최신이 최종이고, 저장(saved)과 다시 고치기(draft) 두 상태만 있습니다.
칸마다 값과 상태(출처·확인 여부)를 data jsonb 안에 같이 두며, lock_version은 두 탭에서 동시에 고칠
때 충돌을 막는 숫자입니다.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._columns import UpdatedAt, UuidPk, in_check, user_fk


class Resume(Base):
    """이력서. 계정당 하나, 버전 없이 최신이 최종. 칸마다 값과 상태를 data에 둡니다."""

    __tablename__ = "resumes"
    __table_args__ = (CheckConstraint(in_check("status", ("draft", "saved")), name="status"),)

    resume_id: Mapped[UuidPk]
    user_id: Mapped[uuid.UUID] = user_fk(unique=True)
    schema_version: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(10), default="draft")
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    saved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lock_version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[UpdatedAt]
