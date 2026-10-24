"""work24_imports 테이블 모델입니다. 고용24 불러오기(모의) 항목 하나가 행 하나입니다.

계정에 입장할 때 seed의 imports를 복사하고, 사용자가 고른 항목을 넣으면 is_recorded가 true가
됩니다. 실제 고용24에는 연결하지 않습니다(설계 3.7, 모의).
"""

import uuid
from datetime import date

from sqlalchemy import Boolean, CheckConstraint, Date, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._columns import CreatedAt, UuidPk, enum_values, in_check, user_fk
from app.schemas.imports import ImportCategory, ImportKind


class Work24Import(Base):
    """고용24 불러오기 항목. 목록 순서는 seed 순서(position)입니다."""

    __tablename__ = "work24_imports"
    __table_args__ = (
        UniqueConstraint("user_id", "source_id"),
        CheckConstraint(in_check("kind", enum_values(ImportKind)), name="kind"),
        CheckConstraint(in_check("category", enum_values(ImportCategory)), name="category"),
    )

    import_pk: Mapped[UuidPk]
    user_id: Mapped[uuid.UUID] = user_fk(index=True)
    # seed의 import_id (화면·대화가 고를 때 쓰는 값)
    source_id: Mapped[str] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(30))
    category: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(200))
    detail: Mapped[str] = mapped_column(String(200))
    item_date: Mapped[date | None] = mapped_column(Date)
    position: Mapped[int] = mapped_column(default=0)
    is_recorded: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[CreatedAt]
