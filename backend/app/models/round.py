"""rounds 테이블 모델입니다. 실업인정 회차 하나가 행 하나입니다.

1차 인정일이 정해지면 서버가 종료 예정일까지 회차를 한꺼번에 만들고, 사용자는 회차를 바꿀 수
없습니다.
지난 회차인지 지금 회차인지는 저장하지 않고 오늘 날짜로 계산합니다.
"""

import uuid
from datetime import date

from sqlalchemy import Boolean, CheckConstraint, Date, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._columns import UuidPk, user_fk


class Round(Base):
    """실업인정 회차. 서버가 1차 인정일로 만들고 사용자는 바꿀 수 없습니다.

    상태(upcoming·current·closed)는 오늘 날짜로 계산하고 저장하지 않습니다.
    """

    __tablename__ = "rounds"
    __table_args__ = (
        UniqueConstraint("user_id", "round_no"),
        CheckConstraint("period_start <= period_end", name="period"),
    )

    round_id: Mapped[UuidPk]
    user_id: Mapped[uuid.UUID] = user_fk(index=True)
    round_no: Mapped[int] = mapped_column(Integer)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    recognition_date: Mapped[date] = mapped_column(Date)
    attendance_required: Mapped[bool] = mapped_column(Boolean, default=False)
