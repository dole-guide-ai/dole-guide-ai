"""여러 모델이 같이 쓰는 컬럼 정의.

UUID 기본키, 생성·수정 시각, 계정이 지워지면 같이 지워지는 user_id 외래키, 허용 값 CHECK 문을
만드는 함수.
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Annotated

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import mapped_column

UuidPk = Annotated[
    uuid.UUID, mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
]
CreatedAt = Annotated[
    datetime, mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
]
UpdatedAt = Annotated[
    datetime,
    mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    ),
]


def user_fk(**kwargs: object) -> object:
    """계정이 지워지면 같이 지워지는 user_id FK."""
    return mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), **kwargs
    )


def enum_values(enum: type[StrEnum]) -> tuple[str, ...]:
    """enum 값 목록. CHECK 제약을 스키마 enum과 같은 값으로 만들 때 씁니다."""
    return tuple(member.value for member in enum)


def in_check(column: str, values: tuple[str, ...]) -> str:
    joined = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({joined})"
