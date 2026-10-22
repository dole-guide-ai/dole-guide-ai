"""personas 테이블 모델입니다. 시연 계정 카드에 보일 값과 계정을 만들 때 복사할 seed를 담습니다.

서버가 시작할 때 backend/data/seeds/personas.json을 읽어 이 테이블에 맞춰 넣습니다.
"""

from typing import Any

from sqlalchemy import Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Persona(Base):
    """시연 계정 seed. `data/seeds/personas.json`을 서버 시작 때 적재합니다."""

    __tablename__ = "personas"

    persona_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    display: Mapped[dict[str, Any]] = mapped_column(JSONB)
    seed: Mapped[dict[str, Any]] = mapped_column(JSONB)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
