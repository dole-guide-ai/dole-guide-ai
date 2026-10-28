"""RAG 검색 색인 채우기와 검색.

색인(knowledge_chunks)에는 규칙 카드와 정책·FAQ 청크가 한 테이블에 들어갑니다. 종류(kind)로 걸러
규칙 카드를 먼저 씁니다. 원본은 규칙 카드 CSV와 지식 청크 파일이고, 서버는 색인만 읽습니다.
"""

import hashlib
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from langchain_core.embeddings import Embeddings
from sqlalchemy.orm import Session

from app.agent import gateway
from app.core.config import get_settings
from app.models import KnowledgeChunk
from app.repositories import knowledge as knowledge_repo
from app.rules.ranking import Bm25Index, rrf
from app.rules.rule_cards import (
    PROFILE_OVERFETCH,
    Profile,
    RuleCard,
    applies_to,
    card_questions,
    cards_by_id,
    is_other_employment,
    load_cards,
    search_card_ids,
)
from app.rules.synonyms import expand_query
from app.schemas.knowledge import KnowledgeHit, KnowledgeKind

logger = logging.getLogger(__name__)

RULE_ID_PREFIX = "rule:"
GUIDE_KINDS = (KnowledgeKind.FAQ, KnowledgeKind.POLICY)
# 우리 사용자는 상용직입니다. 다른 고용 형태 전용 정책 조각은 찾지 않습니다(규칙 카드와 같은 기준).
OTHER_EMPLOYMENT_TYPES = frozenset({"self_employed", "daily", "labor_provider", "artist"})
# 단어·벡터 검색이 각각 합치기 전에 내놓는 후보 수
CANDIDATES = 20
# 정책·FAQ 단어 검색 가중치: 제목은 본문 첫 줄에도 있어 합치면 제목 글자는 3배입니다.
_GUIDE_FIELD_WEIGHTS = {"title": 2, "text": 1}
# 규칙 카드에서 임베딩할 칸과 이름. 모델이 읽는 for_model과 같은 이름을 씁니다.
_RULE_TEXT_FIELDS = (
    ("분류", "category"),
    ("대상", "target"),
    ("내용", "body"),
    ("수치", "number"),
    ("기준일·마감", "deadline"),
    ("증빙·경로", "evidence"),
    ("예외·주의", "caution"),
)


@dataclass(frozen=True)
class SourceDoc:
    """색인에 넣을 원본 한 조각. text가 임베딩하는 글입니다."""

    chunk_id: str
    kind: KnowledgeKind
    title: str
    text: str
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SyncResult:
    embedded: int
    unchanged: int
    deleted: int


def rule_card_id(rule_id: str) -> str:
    return RULE_ID_PREFIX + rule_id


def rule_card_doc(card: RuleCard) -> SourceDoc:
    lines = [f"규칙: {card.name}"]
    lines += [
        f"{label}: {getattr(card, attr)}"
        for label, attr in _RULE_TEXT_FIELDS
        if getattr(card, attr)
    ]
    if questions := card_questions(card):
        lines.append("예상 질문: " + " / ".join(questions))
    return SourceDoc(
        chunk_id=rule_card_id(card.rule_id),
        kind=KnowledgeKind.RULE_CARD,
        title=card.name,
        text="\n".join(lines),
        meta={"rule_id": card.rule_id, "target": card.target, "category": card.category},
    )


def rule_card_documents() -> list[SourceDoc]:
    return [rule_card_doc(card) for card in load_cards()]


def indexed_ids(db: Session) -> list[str]:
    return list(knowledge_repo.hashes(db))


def sync_index(
    db: Session,
    docs: Sequence[SourceDoc],
    embeddings: Embeddings | None = None,
    keep_extra: Sequence[str] = (),
) -> SyncResult:
    """원본과 색인을 맞춥니다. 글이 바뀌었거나 임베딩 모델이 바뀐 행만 다시 임베딩합니다.

    docs에 없는 행은 지웁니다. 원본 일부만 넘길 때는 남길 행을 keep_extra로 줍니다.
    """
    model = get_settings().embedding_model
    existing = knowledge_repo.hashes(db)
    stale = [d for d in docs if existing.get(d.chunk_id) != (d.content_hash, model)]
    fresh = [d for d in docs if existing.get(d.chunk_id) == (d.content_hash, model)]
    if stale:
        vectors = (embeddings or gateway.get_embeddings()).embed_documents([d.text for d in stale])
        knowledge_repo.upsert(
            db,
            [
                {
                    "chunk_id": d.chunk_id,
                    "kind": d.kind.value,
                    "title": d.title,
                    "text": d.text,
                    "meta": d.meta,
                    "content_hash": d.content_hash,
                    "embedding_model": model,
                    "embedding": vector,
                }
                for d, vector in zip(stale, vectors, strict=True)
            ],
        )
    knowledge_repo.update_fields(
        db, [{"chunk_id": d.chunk_id, "title": d.title, "meta": d.meta} for d in fresh]
    )
    deleted = knowledge_repo.delete_missing(db, [d.chunk_id for d in docs] + list(keep_extra))
    db.commit()
    reset_guide_index()
    return SyncResult(embedded=len(stale), unchanged=len(fresh), deleted=deleted)


# ── 검색 ─────────────────────────────────────────────────


@dataclass(frozen=True)
class SearchOptions:
    """검색 방식 조합. 평가에서 하나씩 켜고 끄며 비교합니다."""

    bm25: bool = True
    vector: bool = True
    synonyms: bool = False  # 구어 사전으로 단어 검색 질문 넓히기
    min_similarity: float | None = None  # 거절 임계값: 코사인 유사도가 이보다 낮으면 버림
    candidates: int = CANDIDATES
    # 사용자 조건(수급자 유형·회차)을 규칙 카드 단어 검색 질문에 덧붙이기(맞지 않는 카드는 늘 뺌)
    profile_query: bool = True

    @property
    def needs_vector(self) -> bool:
        return self.vector or self.min_similarity is not None


@dataclass(frozen=True)
class SearchResult:
    rules: list[KnowledgeHit]
    guides: list[KnowledgeHit]


def options_from_settings() -> SearchOptions:
    settings = get_settings()
    return SearchOptions(
        synonyms=settings.retrieval_synonyms, min_similarity=settings.retrieval_min_similarity
    )


def rule_cards_of(hits: Sequence[KnowledgeHit]) -> list[RuleCard]:
    cards = cards_by_id()
    return [cards[h.meta["rule_id"]] for h in hits if h.meta.get("rule_id") in cards]


_SOURCE_NAMES = {"work24": "고용24", "moel_1350": "1350 FAQ"}


def guide_for_model(hit: KnowledgeHit) -> dict[str, str]:
    # 출처는 근거 줄을 만들 때 씁니다(모델은 출처를 쓰지 않음, base.md).
    label = guide_source_label(hit)
    return {"id": hit.chunk_id, "제목": hit.title, "내용": hit.text, "출처": label}


def guide_source_label(hit: KnowledgeHit) -> str:
    """정책·FAQ 조각의 근거 줄 표시. 예: "고용24 「조기재취업수당」 · 2025-07-10"."""
    source = _SOURCE_NAMES.get(str(hit.meta.get("source")), "")
    date = hit.meta.get("last_modified") or hit.meta.get("published_at")
    label = f"{source} 「{hit.title}」".strip()
    return f"{label} · {date}" if date else label


def embed_query(text: str) -> list[float]:
    return gateway.get_embeddings().embed_query(text)


_guide_index: Bm25Index | None = None


def reset_guide_index() -> None:
    """색인을 다시 채운 뒤나 테스트에서 메모리의 단어 검색 색인을 버립니다."""
    global _guide_index
    _guide_index = None


def _is_guide_allowed(chunk: KnowledgeChunk) -> bool:
    return chunk.meta.get("employment_type") not in OTHER_EMPLOYMENT_TYPES


def _guide_bm25(db: Session) -> Bm25Index:
    """정책·FAQ 단어 검색 색인. 서버에는 원본 파일이 없어 색인 테이블의 행으로 만듭니다."""
    global _guide_index
    if _guide_index is None:
        rows = [c for c in knowledge_repo.list_kinds(db, GUIDE_KINDS) if _is_guide_allowed(c)]
        docs = ((c.chunk_id, {"title": c.title, "text": c.text}) for c in rows)
        _guide_index = Bm25Index(docs, _GUIDE_FIELD_WEIGHTS)
    return _guide_index


def _rule_bm25(profile: Profile | None, add_terms: bool) -> Callable[[str, int], list[str]]:
    def find(query: str, limit: int) -> list[str]:
        ids = search_card_ids(query, limit, profile, add_terms)
        return [rule_card_id(rule_id) for rule_id in ids]

    return find


def _search_group(
    db: Session,
    query: str,
    vector: list[float] | None,
    kinds: Sequence[KnowledgeKind],
    bm25: Callable[[str, int], list[str]],
    allowed: Callable[[KnowledgeChunk], bool],
    limit: int,
    options: SearchOptions,
) -> list[KnowledgeHit]:
    if limit <= 0:
        return []
    rankings: list[list[str]] = []
    if options.bm25:
        words = expand_query(query) if options.synonyms else query
        rankings.append(bm25(words, options.candidates))
    if options.vector and vector is not None:
        # 다른 고용 형태·수급자 유형을 거른 뒤에도 후보 수가 남게 넉넉히 받습니다.
        near = knowledge_repo.nearest(db, vector, kinds, options.candidates * PROFILE_OVERFETCH)
        rankings.append([c.chunk_id for c, _ in near if allowed(c)][: options.candidates])
    # 임계값으로 버린 자리는 RRF 다음 순위로 채웁니다(버린 만큼 덜 붙지 않게).
    ranked = [chunk_id for chunk_id, _ in rrf(rankings)]
    top = ranked if options.min_similarity is not None else ranked[:limit]
    found = knowledge_repo.get_many(db, top, vector)
    if missing := len(set(top) - found.keys()):
        # 규칙표는 바뀌었는데 색인을 다시 채우지 않은 경우(scripts.ingest.index를 돌려야 함)
        logger.warning("knowledge_index_missing_rows", extra={"count": missing})
    hits: list[KnowledgeHit] = []
    for chunk_id in (c for c in top if c in found):
        if len(hits) == limit:
            break
        chunk, similarity = found[chunk_id]
        if options.min_similarity is not None and (similarity or 0) < options.min_similarity:
            continue
        hits.append(
            KnowledgeHit(
                chunk_id=chunk.chunk_id,
                kind=KnowledgeKind(chunk.kind),
                title=chunk.title,
                text=chunk.text,
                meta=chunk.meta,
                similarity=similarity,
            )
        )
    return hits


def search(
    db: Session,
    query: str,
    rule_limit: int = 3,
    guide_limit: int = 3,
    options: SearchOptions | None = None,
    query_vector: list[float] | None = None,
    profile: Profile | None = None,
) -> SearchResult:
    """규칙 카드와 정책·FAQ를 따로 찾습니다. 규칙 카드를 먼저 쓰고 정책·FAQ는 보충으로 씁니다.

    query_vector를 주면 질문을 다시 임베딩하지 않습니다(평가에서 같은 질문을 여러 방식으로 잴 때).
    profile(수급자 유형·회차)을 주면 그 사용자에게 맞지 않는 규칙 카드는 빼고, 단어 검색 질문에
    "반복수급자 3차" 같은 말을 덧붙입니다. 질문에 "4차"가 있으면 그 회차로 고릅니다.
    """
    options = options or options_from_settings()
    vector = query_vector
    if vector is None and options.needs_vector:
        try:
            vector = embed_query(query)
        except Exception as exc:  # noqa: BLE001 — 임베딩이 안 되면 단어 검색만으로 찾습니다
            logger.warning("query_embedding_failed", extra={"code": gateway.to_app_error(exc).code})
            options = replace(options, vector=False, min_similarity=None)

    profile = profile.for_query(query) if profile else None
    cards = cards_by_id()

    def rule_allowed(chunk: KnowledgeChunk) -> bool:
        if is_other_employment(chunk.meta.get("target", "")):
            return False
        card = cards.get(chunk.meta.get("rule_id", ""))
        return profile is None or card is None or applies_to(card, profile)

    rule_bm25 = _rule_bm25(profile, options.profile_query)
    rules = _search_group(
        db, query, vector, (KnowledgeKind.RULE_CARD,), rule_bm25, rule_allowed, rule_limit,
        options,
    )  # fmt: skip
    guides = _search_group(
        db, query, vector, GUIDE_KINDS, lambda q, n: [i for i, _ in _guide_bm25(db).search(q, n)],
        _is_guide_allowed, guide_limit, options,
    )  # fmt: skip
    return SearchResult(rules=rules, guides=guides)
