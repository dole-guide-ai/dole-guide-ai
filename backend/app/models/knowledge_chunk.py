"""knowledge_chunks 테이블 모델입니다. RAG 검색 색인 한 조각이 행 하나입니다.

색인이지 원본이 아닙니다. 원본은 규칙 카드 CSV(data/rules/rule_table)와 지식 청크
(data/knowledge/chunks, 저장소에 올리지 않음)이고 scripts/index_knowledge.py가 채웁니다.
서버는 이 테이블만 읽습니다(단어 검색 색인도 여기 행으로 만듦).
"""

from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._columns import UpdatedAt, enum_values, in_check
from app.schemas.knowledge import KnowledgeKind

# solar-embedding-2의 차원(ADR 0002). 모델을 바꿔 차원이 달라지면 마이그레이션으로 바꿉니다.
EMBEDDING_DIM = 1024


class KnowledgeChunk(Base):
    """검색 조각. 행이 1,500개 남짓이라 근사 색인(HNSW) 없이 전부 비교합니다."""

    __tablename__ = "knowledge_chunks"
    __table_args__ = (CheckConstraint(in_check("kind", enum_values(KnowledgeKind)), name="kind"),)

    # 규칙 카드는 "rule:DUE-009", 지식 청크는 원본 chunk_id
    chunk_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), index=True)
    title: Mapped[str] = mapped_column(String(300))
    text: Mapped[str] = mapped_column(Text)
    # 규칙 카드는 rule_id·target, 청크는 출처 주소·정책 이름 등
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    # 임베딩한 글(title + text)의 sha256. 바뀐 행만 다시 임베딩합니다.
    content_hash: Mapped[str] = mapped_column(String(64))
    embedding_model: Mapped[str] = mapped_column(String(80))
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    updated_at: Mapped[UpdatedAt]
