"""procedure_states 테이블 모델입니다. 계정의 수급 절차 상태를 담습니다.

지금 단계, 수급자 유형(이직 당시 나이로 정함), 고용보험 가입기간과 소정급여일수, 교육 이수 여부,
그리고 사용자가 고용센터에서 받아 입력하는 수급자격 신청일과 1차 인정일이 들어갑니다.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._columns import in_check

STAGES = (
    "job_registration",
    "education",
    "eligibility_application",
    "eligibility_applied",
    "recognition",
    "ended",
)
RECIPIENT_GROUPS = ("general", "age_60_64", "age65_or_disabled", "repeat")
END_REASONS = ("period_expired", "exhausted", "employed")


class ProcedureState(Base):
    """절차 상태. 사용자는 센터에서 받은 사실(신청일·1차 인정일)만 입력합니다."""

    __tablename__ = "procedure_states"
    __table_args__ = (
        CheckConstraint(in_check("stage", STAGES), name="stage"),
        CheckConstraint(in_check("recipient_group", RECIPIENT_GROUPS), name="recipient_group"),
        CheckConstraint(
            f"end_reason IS NULL OR {in_check('end_reason', END_REASONS)}", name="end_reason"
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True
    )
    stage: Mapped[str] = mapped_column(String(30))
    recipient_group: Mapped[str] = mapped_column(String(30))
    separation_date: Mapped[date] = mapped_column(Date)
    age_at_separation: Mapped[int] = mapped_column(Integer)
    has_disability: Mapped[bool] = mapped_column(Boolean, default=False)
    insured_years: Mapped[Decimal] = mapped_column(Numeric(4, 1))
    benefit_days: Mapped[int] = mapped_column(Integer)
    education_done: Mapped[bool] = mapped_column(Boolean, default=False)
    eligibility_applied_on: Mapped[date | None] = mapped_column(Date)
    first_recognition_date: Mapped[date | None] = mapped_column(Date)
    end_reason: Mapped[str | None] = mapped_column(String(20))
    lock_version: Mapped[int] = mapped_column(Integer, default=1)
