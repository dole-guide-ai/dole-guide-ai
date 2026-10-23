"""고용24 공통코드(지역·직종) 테이블 모델입니다 (데이터 설계 10.5).

계정과 무관한 기준정보라 work24_api 스키마에 두고, API 원본 필드명(camelCase)을 그대로 씁니다.
직종은 같은 코드가 다른 상위 아래 나올 수 있어 코드 경로(code_path)로 행을 구분합니다.
"""

from datetime import datetime

from sqlalchemy import ARRAY, BigInteger, DateTime, ForeignKey, SmallInteger, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

SCHEMA = "work24_api"


class CmcdRegion(Base):
    __tablename__ = "cmcdRegion"
    __table_args__ = {"schema": SCHEMA}

    regionCd: Mapped[str] = mapped_column(Text, primary_key=True)  # noqa: N815
    regionNm: Mapped[str] = mapped_column(Text)  # noqa: N815
    superCd: Mapped[str | None] = mapped_column(  # noqa: N815
        Text, ForeignKey(f"{SCHEMA}.cmcdRegion.regionCd")
    )
    depth: Mapped[int] = mapped_column(SmallInteger)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CmcdJobs(Base):
    __tablename__ = "cmcdJobs"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    jobsCd: Mapped[str] = mapped_column(Text)  # noqa: N815
    jobsNm: Mapped[str] = mapped_column(Text)  # noqa: N815
    superCd: Mapped[str | None] = mapped_column(Text)  # noqa: N815
    parent_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey(f"{SCHEMA}.cmcdJobs.id"))
    depth: Mapped[int] = mapped_column(SmallInteger)
    code_path: Mapped[list[str]] = mapped_column(ARRAY(Text), unique=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
