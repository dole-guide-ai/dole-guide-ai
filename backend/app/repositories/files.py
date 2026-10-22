"""업로드 파일(files) 행 조회·저장 레포지토리입니다. 파일 실물은 서비스가 다룹니다.

모든 조회는 user_id로 거릅니다. 지운 파일(deleted_at)은 찾지 않습니다. commit은 서비스가 합니다.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import File


def add(db: Session, file: File) -> File:
    db.add(file)
    db.flush()
    return file


def get_for_user(db: Session, user_id: uuid.UUID, file_id: uuid.UUID) -> File | None:
    return db.scalar(
        select(File).where(
            File.file_id == file_id, File.user_id == user_id, File.deleted_at.is_(None)
        )
    )
