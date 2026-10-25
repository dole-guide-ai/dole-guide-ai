"""검색 색인(knowledge_chunks) 레포지토리입니다. 계정 데이터가 아니라 모두 같이 쓰는 지식입니다."""

from collections.abc import Iterable, Sequence
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import KnowledgeChunk
from app.schemas.knowledge import KnowledgeKind


def hashes(db: Session) -> dict[str, tuple[str, str]]:
    """chunk_id → (content_hash, embedding_model). 다시 임베딩할 행을 고를 때 씁니다."""
    rows = db.execute(
        select(KnowledgeChunk.chunk_id, KnowledgeChunk.content_hash, KnowledgeChunk.embedding_model)
    )
    return {chunk_id: (h, model) for chunk_id, h, model in rows}


def upsert(db: Session, rows: Sequence[dict[str, Any]]) -> None:
    if not rows:
        return
    stmt = insert(KnowledgeChunk).values(list(rows))
    columns = ("kind", "title", "text", "meta", "content_hash", "embedding_model", "embedding")
    db.execute(
        stmt.on_conflict_do_update(
            index_elements=[KnowledgeChunk.chunk_id],
            set_={c: stmt.excluded[c] for c in columns},
        )
    )
    db.flush()


def update_fields(db: Session, rows: Sequence[dict[str, Any]]) -> None:
    """임베딩한 글은 그대로이고 표시용 칸(title·meta)만 바뀐 행."""
    for row in rows:
        chunk = db.get(KnowledgeChunk, row["chunk_id"])
        if chunk is not None:
            chunk.title, chunk.meta = row["title"], row["meta"]
    db.flush()


def delete_missing(db: Session, keep: Iterable[str]) -> int:
    """원본에서 사라진 행을 지웁니다."""
    result = db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.chunk_id.not_in(list(keep))))
    db.flush()
    return result.rowcount or 0


def list_kinds(db: Session, kinds: Sequence[KnowledgeKind]) -> list[KnowledgeChunk]:
    return list(
        db.scalars(
            select(KnowledgeChunk)
            .where(KnowledgeChunk.kind.in_(kinds))
            .order_by(KnowledgeChunk.chunk_id)
        )
    )


def nearest(
    db: Session, vector: Sequence[float], kinds: Sequence[KnowledgeKind], limit: int
) -> list[tuple[KnowledgeChunk, float]]:
    """코사인 거리가 가까운 순. 돌려주는 값은 유사도(1 - 거리)입니다."""
    distance = KnowledgeChunk.embedding.cosine_distance(vector)
    rows = db.execute(
        select(KnowledgeChunk, distance)
        .where(KnowledgeChunk.kind.in_(kinds))
        .order_by(distance)
        .limit(limit)
    )
    return [(chunk, 1 - float(d)) for chunk, d in rows]


def get_many(
    db: Session, chunk_ids: Sequence[str], vector: Sequence[float] | None = None
) -> dict[str, tuple[KnowledgeChunk, float | None]]:
    """고른 행과(벡터를 주면) 코사인 유사도. 단어 검색에만 걸린 행의 유사도를 잴 때 씁니다."""
    if not chunk_ids:
        return {}
    if vector is None:
        chunks = db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.chunk_id.in_(chunk_ids)))
        return {c.chunk_id: (c, None) for c in chunks}
    distance = KnowledgeChunk.embedding.cosine_distance(vector)
    rows = db.execute(
        select(KnowledgeChunk, distance).where(KnowledgeChunk.chunk_id.in_(chunk_ids))
    )
    return {c.chunk_id: (c, 1 - float(d)) for c, d in rows}
