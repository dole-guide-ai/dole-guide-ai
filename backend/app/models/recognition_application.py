"""recognition_applications 테이블 모델입니다. 회차마다 실업인정 신청서 하나를 담습니다.

사용자가 답한 칸은 data jsonb에 두고, 구직활동 칸은 activities에서 매번 만들기 때문에 여기에
복사하지 않습니다.
제출은 status를 submitted로 바꾸고 제출 방식과 시각을 남기는 것입니다.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._columns import UpdatedAt, UuidPk, in_check, user_fk

SUBMIT_MODES = ("attend", "preview", "send", "visit_today", "change")


class RecognitionApplication(Base):
    """회차당 실업인정 신청서 한 건. 구직활동 칸은 activities에서 만들고 복사하지 않습니다."""

    __tablename__ = "recognition_applications"
    __table_args__ = (
        CheckConstraint(in_check("status", ("draft", "submitted")), name="status"),
        CheckConstraint(
            f"submit_mode IS NULL OR {in_check('submit_mode', SUBMIT_MODES)}", name="submit_mode"
        ),
    )

    application_id: Mapped[UuidPk]
    round_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rounds.round_id", ondelete="CASCADE"), unique=True
    )
    user_id: Mapped[uuid.UUID] = user_fk(index=True)
    status: Mapped[str] = mapped_column(String(10), default="draft")
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    submit_mode: Mapped[str | None] = mapped_column(String(15))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lock_version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[UpdatedAt]
