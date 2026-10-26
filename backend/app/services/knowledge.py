"""RAG 하이브리드 검색 (노션 「RAG 설계 (복사본)」, 「AI 설계」 3절).

질문 → Kiwi 형태소 + 동의어 확장 → BM25S Top N ┐
     → 임베딩 → pgvector 코사인 Top N ────────┴→ RRF(k) → (리랭커, 설정) → 상위 N개 + 출처

- 점수가 비슷하면 고용24 정책(primary)을 1350 FAQ(secondary)보다 앞에 둡니다.
- 가장 가까운 자료도 기준보다 멀면 '찾지 못함'으로 돌려줍니다(지어낸 답을 막기 위해).
- 임베딩 모델이 없거나 호출이 실패하면 BM25만으로 찾습니다.
- BM25 인덱스는 처음 검색할 때 DB의 형태소로 메모리에 만듭니다. 적재가 바뀌면 `reset_index()`.
"""

import json
import logging
import threading
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.agent import gateway
from app.core.config import get_settings
from app.repositories import knowledge as repo

logger = logging.getLogger(__name__)

SYNONYMS = Path(__file__).resolve().parents[2] / "data" / "reference" / "synonyms.json"
# 형태소 중 검색에 쓰는 품사 (명사 · 동사 · 형용사 어근 · 외국어 · 숫자)
KEEP_TAGS = ("NNG", "NNP", "NNB", "NR", "VV", "VA", "XR", "SL", "SN", "SH")
# 어디에나 나와 검색을 흐리는 말 (하다 · 되다 · 있다 · 수 · 것 등)
STOP_FORMS = frozenset({"하", "되", "있", "없", "수", "것", "번", "등", "때", "보", "주", "같"})
PRIMARY = "primary"
# 같은 점수면 고용24 정책을 앞에 두는 작은 가산점 (RRF 점수 한 칸보다 작게)
PRIMARY_BONUS = 1e-4
SOURCE_NAMES = {"work24": "고용24", "moel_1350": "고용노동부 1350 FAQ"}


# ── 형태소 · 동의어 ──────────────────────────────────


@lru_cache(maxsize=1)
def _kiwi() -> Any:
    from kiwipiepy import Kiwi

    return Kiwi()


def tokenize(text: str) -> list[str]:
    return [
        t.form.lower()
        for t in _kiwi().tokenize(text)
        if t.tag.startswith(KEEP_TAGS) and t.form not in STOP_FORMS
    ]


@lru_cache(maxsize=1)
def _synonyms() -> dict[str, list[str]]:
    return json.loads(SYNONYMS.read_text(encoding="utf-8"))["synonyms"]


def expand(query: str) -> str:
    """원래 질문에 관련 정책 용어를 덧붙입니다."""
    extra = [term for key, terms in _synonyms().items() if key in query for term in terms]
    return " ".join([query, *dict.fromkeys(extra)])


# ── 인덱스 ─────────────────────────────────────────


@dataclass
class _Index:
    retriever: Any
    chunk_ids: list[str]


_index: _Index | None = None
_lock = threading.Lock()


def reset_index() -> None:
    global _index
    with _lock:
        _index = None


def _bm25_index(db: Session) -> _Index | None:
    global _index
    with _lock:
        if _index is None:
            import bm25s

            chunks = repo.all_chunks(db)
            if not chunks:
                return None
            retriever = bm25s.BM25()
            retriever.index([c.tokens or ["_"] for c in chunks], show_progress=False)
            _index = _Index(retriever, [c.chunk_id for c in chunks])
        return _index


def _bm25(db: Session, query: str, top_k: int) -> list[tuple[str, float]]:
    index = _bm25_index(db)
    tokens = tokenize(expand(query))
    if index is None or not tokens:
        return []
    k = min(top_k, len(index.chunk_ids))
    docs, scores = index.retriever.retrieve([tokens], k=k, show_progress=False)
    return [
        (index.chunk_ids[int(d)], float(s))
        for d, s in zip(docs[0], scores[0], strict=True)
        if float(s) > 0
    ]


def embedding_model() -> str:
    return get_settings().embedding_model


def _vector(db: Session, query: str, top_k: int) -> list[tuple[str, float]]:
    """(chunk_id, 유사도) 목록. 임베딩을 못 쓰면 빈 목록."""
    model = embedding_model()
    if not model:
        return []
    try:
        vector = gateway.get_embeddings().embed_query(query)
    except Exception as exc:  # noqa: BLE001 - 임베딩 실패는 BM25만으로 찾습니다
        logger.warning("embedding failed type=%s", type(exc).__name__)
        return []
    return [(cid, 1 - distance) for cid, distance in repo.nearest(db, model, vector, top_k)]


def rrf(rankings: list[list[str]], k: int) -> dict[str, float]:
    """Reciprocal Rank Fusion: 순위마다 1/(k+순위)를 더합니다(중복은 합쳐짐)."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1 / (k + rank)
    return scores


@lru_cache(maxsize=1)
def _reranker() -> Any:
    try:
        from sentence_transformers import CrossEncoder  # 선택 의존성 (uv sync --extra rerank)
    except ImportError:
        logger.warning("reranker unavailable reason=not_installed")
        return None
    return CrossEncoder(get_settings().reranker_model)


def _rerank(query: str, ordered: list[str], chunks: dict[str, Any]) -> list[str]:
    model = _reranker()
    if model is None:
        return ordered
    pairs = [(query, chunks[cid].content) for cid in ordered]
    scores = model.predict(pairs)
    return [cid for cid, _ in sorted(zip(ordered, scores, strict=True), key=lambda x: -x[1])]


# ── 검색 ─────────────────────────────────────────


def source_name(source: str, title: str) -> str:
    if source == "work24":
        return f"{SOURCE_NAMES[source]} {title}"
    return SOURCE_NAMES.get(source, source)


def _as_result(chunk: Any, score: float) -> dict[str, Any]:
    updated: date | None = chunk.updated_on
    return {
        "chunk_id": chunk.chunk_id,
        "source_id": chunk.source_id,
        "title": chunk.title,
        "text": chunk.content,
        "source_name": source_name(chunk.source, chunk.title),
        "updated_on": updated.isoformat() if updated else None,
        "url": chunk.source_url,
        "needs_verification": chunk.needs_verification,
        "score": round(score, 6),
    }


def search(db: Session, query: str, *, use_reranker: bool | None = None) -> list[dict[str, Any]]:
    """질문과 가까운 자료 상위 N개. 기준보다 먼 자료뿐이면 빈 목록(찾지 못함)."""
    settings = get_settings()
    lexical = _bm25(db, query, settings.rag_bm25_top_k)
    semantic = _vector(db, query, settings.rag_vector_top_k)
    fused = rrf([[c for c, _ in lexical], [c for c, _ in semantic]], settings.rag_rrf_k)
    chunks = repo.chunks_by_id(db, fused)
    if not _relevant(query, lexical, semantic, chunks):
        return []
    for cid, chunk in chunks.items():
        if chunk.priority == PRIMARY:
            fused[cid] += PRIMARY_BONUS
    ordered = [cid for cid in sorted(fused, key=lambda c: -fused[c]) if cid in chunks]
    rerank = settings.reranker_enabled if use_reranker is None else use_reranker
    if rerank:
        ordered = _rerank(query, ordered[: settings.reranker_top_n], chunks)
    top = ordered[: settings.rag_result_top_n]
    return [_as_result(chunks[cid], fused[cid]) for cid in top]


def _relevant(
    query: str,
    lexical: list[tuple[str, float]],
    semantic: list[tuple[str, float]],
    chunks: dict[str, Any],
) -> bool:
    """가장 가까운 자료가 기준을 넘는지.

    벡터가 있으면 코사인 유사도로 봅니다. 벡터가 없으면 BM25 점수는 질문마다 크기가 달라 기준으로
    쓰기 어려워, 가장 높은 자료가 질문 낱말을 얼마나 덮는지(coverage)로 봅니다.
    """
    settings = get_settings()
    if semantic:
        return semantic[0][1] >= settings.rag_min_similarity
    if not lexical:
        return False
    words = set(tokenize(query))
    top = chunks.get(lexical[0][0])
    if not words or top is None:
        return False
    covered = len(words & set(top.tokens or [])) / len(words)
    return covered >= settings.rag_min_bm25_coverage
