"""RAG 근거 자료(knowledge 스키마)를 조회 · 저장하는 레포지토리입니다. commit은 하지 않습니다."""

from collections.abc import Iterable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import ChunkEmbedding, KnowledgeChunk

__all__ = ["ChunkEmbedding", "KnowledgeChunk"]


def all_chunks(db: Session) -> list[KnowledgeChunk]:
    return list(db.scalars(select(KnowledgeChunk).order_by(KnowledgeChunk.chunk_id)))


def chunks_by_id(db: Session, chunk_ids: Iterable[str]) -> dict[str, KnowledgeChunk]:
    ids = list(chunk_ids)
    if not ids:
        return {}
    rows = db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.chunk_id.in_(ids)))
    return {row.chunk_id: row for row in rows}


def nearest(db: Session, model: str, vector: list[float], limit: int) -> list[tuple[str, float]]:
    """코사인 거리가 가까운 청크 (정확 검색). (chunk_id, 거리) 목록."""
    distance = ChunkEmbedding.embedding.cosine_distance(vector)
    rows = db.execute(
        select(ChunkEmbedding.chunk_id, distance.label("distance"))
        .where(ChunkEmbedding.model == model)
        .order_by(distance)
        .limit(limit)
    )
    return [(row.chunk_id, float(row.distance)) for row in rows]


def embedding_hashes(db: Session, model: str) -> dict[str, str]:
    rows = db.execute(
        select(ChunkEmbedding.chunk_id, ChunkEmbedding.content_hash).where(
            ChunkEmbedding.model == model
        )
    )
    return {row.chunk_id: row.content_hash for row in rows}


def upsert_chunk(db: Session, chunk: KnowledgeChunk) -> None:
    db.merge(chunk)


def upsert_embedding(db: Session, embedding: ChunkEmbedding) -> None:
    db.merge(embedding)


def delete_chunks_except(db: Session, keep: set[str]) -> int:
    """파일에서 사라진 청크를 지웁니다(임베딩은 CASCADE)."""
    result = db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.chunk_id.not_in(keep)))
    return result.rowcount or 0
