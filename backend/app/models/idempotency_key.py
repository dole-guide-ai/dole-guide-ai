"""idempotency_keys 테이블 모델입니다.

메시지·활동·파일을 만드는 POST 요청이 버튼 두 번 클릭이나 재시도로 두 번 오면, 같은 키에 처음
결과를 돌려주려고 둡니다.
24시간이 지나면 정리 작업이 지웁니다.
"""

import uuid
from typing import Any

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._columns import CreatedAt


class IdempotencyKey(Base):
    """POST 재시도 중복 방지. 같은 키면 처음 응답을 돌려줍니다. 24시간 뒤 정리합니다."""

    __tablename__ = "idempotency_keys"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True
    )
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    status_code: Mapped[int] = mapped_column(Integer)
    response: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[CreatedAt]
