"""files 테이블과 활동-파일 연결표(activity_files) 모델입니다.

파일 실물은 UPLOAD_DIR 아래 계정 폴더에 저장하고, 이 테이블에는 이름·형식·크기·저장 위치만 둡니다.
이력서 서류는 판독 후 지우고 삭제 시각을 남기며, 구직활동 증빙은 활동에 연결해 보관합니다.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._columns import CreatedAt, UuidPk, in_check, user_fk


class File(Base):
    """업로드 파일. 실물은 UPLOAD_DIR/{user_id}/{file_id}. 이력서 서류는 판독 후 지웁니다."""

    __tablename__ = "files"
    __table_args__ = (
        CheckConstraint(in_check("purpose", ("evidence", "resume_doc")), name="purpose"),
    )

    file_id: Mapped[UuidPk]
    user_id: Mapped[uuid.UUID] = user_fk(index=True)
    purpose: Mapped[str] = mapped_column(String(20))
    file_name: Mapped[str] = mapped_column(String(200))
    mime_type: Mapped[str] = mapped_column(String(100))
    size: Mapped[int] = mapped_column(Integer)
    storage_key: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[CreatedAt]
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


activity_files = Table(
    "activity_files",
    Base.metadata,
    Column(
        "activity_id",
        UUID(as_uuid=True),
        ForeignKey("activities.activity_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "file_id",
        UUID(as_uuid=True),
        ForeignKey("files.file_id", ondelete="CASCADE"),
        primary_key=True,
    ),
)
