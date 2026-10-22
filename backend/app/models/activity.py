"""activities 테이블 모델입니다. 구직활동과 구직 외 활동 기록 하나가 행 하나입니다.

날짜만 저장하고 회차는 rounds의 대상기간으로 계산합니다. 추천에서 넣은 앞으로 할 활동은 planned로
표시합니다.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._columns import CreatedAt, UuidPk, in_check, user_fk


class Activity(Base):
    """재취업활동. 날짜만 저장하고 회차는 rounds 대상기간으로 계산합니다."""

    __tablename__ = "activities"
    __table_args__ = (
        CheckConstraint(in_check("category", ("job_search", "non_job_search")), name="category"),
        Index("ix_activities_user_date", "user_id", "activity_date"),
    )

    activity_id: Mapped[UuidPk]
    user_id: Mapped[uuid.UUID] = user_fk()
    activity_date: Mapped[date] = mapped_column(Date)
    category: Mapped[str] = mapped_column(String(20))
    kind: Mapped[str] = mapped_column(String(40))
    route: Mapped[str | None] = mapped_column(String(40))
    org_name: Mapped[str | None] = mapped_column(String(100))
    job_title: Mapped[str | None] = mapped_column(String(100))
    search_method: Mapped[str | None] = mapped_column(String(40))
    apply_method: Mapped[str | None] = mapped_column(String(40))
    contact_dept: Mapped[str | None] = mapped_column(String(100))
    result: Mapped[str | None] = mapped_column(String(100))
    hours: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    source: Mapped[str] = mapped_column(String(20))
    planned: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[CreatedAt]
