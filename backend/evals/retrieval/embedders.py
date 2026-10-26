"""검색 평가에서 임베딩 모델을 바꿔 견줍니다(run.py --embedding).

서버 색인(knowledge_chunks)은 그대로 두고, 같은 문서를 다른 모델로 임베딩해 메모리에서 찾습니다.
문서 벡터는 reports/cache/docvec-<이름>.json에 두어 다시 돌릴 때 임베딩하지 않습니다.
"""

import json
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from langchain_core.embeddings import Embeddings
from sqlalchemy.orm import Session

from app.agent import gateway
from app.models import KnowledgeChunk
from app.repositories import knowledge as knowledge_repo
from app.schemas.knowledge import KnowledgeKind
from app.services import knowledge as knowledge_service
from scripts.ingest.index import chunk_documents

ALL_KINDS = tuple(KnowledgeKind)
# 서버 색인과 같은 차원으로 줄여 견줍니다(EMBEDDING_DIM).
DIMENSIONS = 1024


@dataclass(frozen=True)
class Embedder:
    name: str
    make: Callable[[], Embeddings]
    # 질문 앞에 붙이는 말(e5 계열처럼 질문·문서를 구분하는 모델). 없으면 빈 글자.
    query_prefix: str = ""


EMBEDDERS: dict[str, Embedder] = {
    e.name: e
    for e in [
        Embedder(
            "upstage-solar2",
            lambda: gateway.get_embeddings_for(
                "upstage", "solar-embedding-2-passage", "solar-embedding-2-query"
            ),
        ),
        Embedder(
            "openai-3-small",
            lambda: gateway.get_embeddings_for("openai", "text-embedding-3-small", "", DIMENSIONS),
        ),
        Embedder(
            "openai-3-large",
            lambda: gateway.get_embeddings_for("openai", "text-embedding-3-large", "", DIMENSIONS),
        ),
    ]
}


def documents() -> dict[str, str]:
    """색인과 같은 문서(규칙 카드 + 정책·FAQ 청크)의 임베딩 글."""
    docs = knowledge_service.rule_card_documents() + (chunk_documents() or [])
    return {d.chunk_id: d.text for d in docs}


def _normalize(rows: Sequence[Sequence[float]]) -> np.ndarray:
    matrix = np.asarray(rows, dtype=np.float32)
    return matrix / np.linalg.norm(matrix, axis=1, keepdims=True).clip(min=1e-12)


class MemoryIndex:
    """문서 벡터를 메모리에 두고 코사인 유사도로 찾습니다(pgvector nearest·get_many 대신)."""

    def __init__(self, embedder: Embedder, cache_dir: Path, batch: int = 100) -> None:
        self.embedder = embedder
        self.model = embedder.make()
        path = cache_dir / f"docvec-{embedder.name}.json"
        cache: dict[str, list[float]] = (
            json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        )
        docs = documents()
        todo = [i for i in docs if i not in cache]
        for start in range(0, len(todo), batch):
            ids = todo[start : start + batch]
            cache |= dict(zip(ids, self.model.embed_documents([docs[i] for i in ids]), strict=True))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cache), encoding="utf-8")
        self.ids = list(docs)
        self.matrix = _normalize([cache[i] for i in self.ids])
        self.position = {chunk_id: n for n, chunk_id in enumerate(self.ids)}

    def embed_queries(self, texts: list[str]) -> list[list[float]]:
        texts = [self.embedder.query_prefix + t for t in texts]
        if hasattr(self.model, "query"):  # 질문용 모델이 따로 있는 공급자
            return self.model.query.embed_documents(texts)
        return self.model.embed_documents(texts)

    def similarities(self, vector: Sequence[float]) -> np.ndarray:
        return self.matrix @ _normalize([vector])[0]


@contextmanager
def use_memory_index(db: Session, index: MemoryIndex) -> Iterator[None]:
    """이 블록 안의 검색이 DB 벡터 대신 메모리 색인을 쓰게 레포지토리 함수를 바꿔 끼웁니다."""
    rows = {c.chunk_id: c for c in knowledge_repo.list_kinds(db, ALL_KINDS)}
    nearest, get_many = knowledge_repo.nearest, knowledge_repo.get_many

    def memory_nearest(_db, vector, kinds, limit) -> list[tuple[KnowledgeChunk, float]]:
        sims = index.similarities(vector)
        wanted = {k.value if isinstance(k, KnowledgeKind) else k for k in kinds}
        found = []
        for n in np.argsort(-sims):
            chunk = rows.get(index.ids[n])
            if chunk is not None and chunk.kind in wanted:
                found.append((chunk, float(sims[n])))
                if len(found) == limit:
                    break
        return found

    def memory_get_many(_db, chunk_ids, vector=None):
        sims = index.similarities(vector) if vector is not None else None
        return {
            i: (rows[i], float(sims[index.position[i]]) if sims is not None else None)
            for i in chunk_ids
            if i in rows and i in index.position
        }

    knowledge_repo.nearest, knowledge_repo.get_many = memory_nearest, memory_get_many
    try:
        yield
    finally:
        knowledge_repo.nearest, knowledge_repo.get_many = nearest, get_many
