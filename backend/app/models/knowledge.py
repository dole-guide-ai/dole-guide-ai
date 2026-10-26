"""RAG 근거 자료 테이블 (knowledge 스키마, 노션 「RAG 설계 (복사본)」 7.5).

계정과 무관한 공용 자료입니다. 팀원이 수집 · 청킹한 data/knowledge/chunks/*.jsonl을
scripts/ingest/load_chunks.py가 적재합니다. 문서 테이블은 두지 않고 청크마다 출처 정보를 둡니다.

임베딩은 모델마다 한 행입니다. 비교 실험 후보마다 벡터 길이가 달라(1,024 · 1,536 등) 길이를
고정하지 않은 vector로 두고 `model`로 걸러 검색합니다. 916건이라 인덱스 없이 정확 검색합니다.
"""

from datetime import date

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._columns import CreatedAt

KNOWLEDGE_SCHEMA = "knowledge"


class KnowledgeChunk(Base):
    __tablename__ = "chunks"
    __table_args__ = {"schema": KNOWLEDGE_SCHEMA}

    chunk_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    # 출처 ID (근거 줄 rule_refs): KB-{source}-{doc_id}
    source_id: Mapped[str] = mapped_column(String(120), index=True)
    source: Mapped[str] = mapped_column(String(30))  # work24 · moel_1350
    doc_id: Mapped[str] = mapped_column(String(60))
    chunk_scope: Mapped[str] = mapped_column(String(20))  # faq · catalog · content
    chunk_type: Mapped[str] = mapped_column(String(20))
    section_type: Mapped[str | None] = mapped_column(String(30))
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str] = mapped_column(String(300))
    content: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    updated_on: Mapped[date | None] = mapped_column(Date)
    priority: Mapped[str] = mapped_column(String(20))  # primary · secondary
    needs_verification: Mapped[bool] = mapped_column(Boolean, default=False)
    content_hash: Mapped[str] = mapped_column(String(64))
    # BM25 검색용 Kiwi 형태소 (앱 시작 때 메모리 인덱스를 만듦)
    tokens: Mapped[list[str]] = mapped_column(ARRAY(Text))
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[CreatedAt]


class ChunkEmbedding(Base):
    __tablename__ = "chunk_embeddings"
    __table_args__ = {"schema": KNOWLEDGE_SCHEMA}

    chunk_id: Mapped[str] = mapped_column(
        String(80),
        ForeignKey(f"{KNOWLEDGE_SCHEMA}.chunks.chunk_id", ondelete="CASCADE"),
        primary_key=True,
    )
    model: Mapped[str] = mapped_column(String(120), primary_key=True)
    dim: Mapped[int] = mapped_column(Integer)
    embedding: Mapped[list[float]] = mapped_column(Vector())
    content_hash: Mapped[str] = mapped_column(String(64))
