"""근거 검색(RAG): 지식 자료 조각에서 질문과 관련 있는 것을 찾습니다 (설계 초안 결정 ④).

자료는 `data/knowledge/<날짜>/chunks/*.jsonl`(1350 FAQ·고용24 정책, 조각 916개)입니다.
통째로 넣기엔 커서(약 28만 자) 검색합니다. 방식은 설정 RETRIEVAL_MODE로 고릅니다.

- keyword: BM25. 한글은 띄어쓰기·조사가 달라도 맞도록 두 글자씩 쪼갠 조각(bigram)으로 셉니다.
- vector: 임베딩 코사인 유사도. 조각 임베딩은 한 번 만들어 `backend/.cache/`에 둡니다.
  (운영에서는 pgvector 테이블에 두는 것이 맞습니다. 실험에서는 파일로 재사용합니다.)
- hybrid: 두 순위를 RRF(순위 역수 합)로 합칩니다.
"""

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from app.agent import gateway
from app.core.config import get_settings

BACKEND_DIR = Path(__file__).resolve().parents[2]
CHUNK_DIR = BACKEND_DIR / "data" / "knowledge" / "2026-10-20" / "chunks"
CACHE_DIR = BACKEND_DIR / ".cache" / "knowledge"
# AI에게 넘기는 조각 하나의 최대 글자 수 (토큰 비용을 묶어 둡니다)
MAX_CHARS = 600
# BM25 기본값과 RRF 상수
BM25_K1, BM25_B = 1.5, 0.75
RRF_K = 60
WORD = re.compile(r"[0-9A-Za-z]+|[가-힣]+")


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    title: str
    text: str
    cite: str  # 답의 근거 줄에 쓰는 출처 이름


def _cite(meta: dict) -> tuple[str, str]:
    if meta.get("source") == "moel_1350":
        title = meta.get("title") or ""
        return title, f"고용노동부 1350 FAQ: {title}"
    name = meta.get("policy_name") or ""
    section = meta.get("original_title")
    title = f"{name} - {section}" if section else name
    return title, f"고용24 정책 안내: {name}"


@cache
def load_chunks() -> tuple[Chunk, ...]:
    chunks = []
    for path in sorted(CHUNK_DIR.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            title, cite = _cite(row.get("metadata") or {})
            chunks.append(Chunk(row["chunk_id"], title, row["content"], cite))
    return tuple(chunks)


def tokenize(text: str) -> list[str]:
    """영문·숫자는 단어 그대로, 한글은 두 글자 조각으로 나눕니다(한 글자 단어는 그대로)."""
    tokens: list[str] = []
    for word in WORD.findall(text.lower()):
        if word[0].isascii() or len(word) == 1:
            tokens.append(word)
        else:
            tokens.extend(word[i : i + 2] for i in range(len(word) - 1))
    return tokens


class _Bm25:
    def __init__(self, docs: list[list[str]]) -> None:
        self.docs = [Counter(doc) for doc in docs]
        self.lengths = [len(doc) for doc in docs]
        self.avg = sum(self.lengths) / max(len(docs), 1)
        df = Counter(term for doc in self.docs for term in doc)
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, query: list[str]) -> list[float]:
        out = []
        for doc, length in zip(self.docs, self.lengths, strict=True):
            norm = BM25_K1 * (1 - BM25_B + BM25_B * length / self.avg)
            out.append(
                sum(
                    self.idf[t] * doc[t] * (BM25_K1 + 1) / (doc[t] + norm)
                    for t in set(query)
                    if t in doc
                )
            )
        return out


@cache
def _bm25() -> _Bm25:
    return _Bm25([tokenize(f"{c.title} {c.text}") for c in load_chunks()])


def _cache_path(model: str) -> Path:
    return CACHE_DIR / f"{re.sub(r'[^0-9A-Za-z._-]', '_', model)}.json"


@cache
def _vectors(model: str) -> tuple[tuple[float, ...], ...]:
    """조각 임베딩. 파일이 있으면 읽고, 없으면 한 번 만들어 저장합니다."""
    chunks = load_chunks()
    path = _cache_path(model)
    if path.exists():
        saved = json.loads(path.read_text(encoding="utf-8"))
        if saved.get("ids") == [c.chunk_id for c in chunks]:
            return tuple(tuple(v) for v in saved["vectors"])
    vectors = gateway.get_embeddings().embed_documents([f"{c.title}\n{c.text}" for c in chunks])
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"ids": [c.chunk_id for c in chunks], "vectors": vectors}
    path.write_text(json.dumps(payload), encoding="utf-8")
    return tuple(tuple(v) for v in vectors)


def _cosine(a: tuple[float, ...] | list[float], b: tuple[float, ...]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)) or 1)


def _ranking(scores: list[float]) -> list[int]:
    return sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)


def _keyword_rank(query: str) -> list[int]:
    scores = _bm25().scores(tokenize(query))
    return [i for i in _ranking(scores) if scores[i] > 0]


def _vector_rank(query: str) -> list[int]:
    model = get_settings().embedding_model
    vectors = _vectors(model)
    q = gateway.get_embeddings().embed_query(query)
    return _ranking([_cosine(q, v) for v in vectors])


def _rrf(*rankings: list[int]) -> list[int]:
    score: Counter[int] = Counter()
    for ranking in rankings:
        for rank, index in enumerate(ranking):
            score[index] += 1 / (RRF_K + rank + 1)
    return [index for index, _ in score.most_common()]


def search(query: str, mode: str | None = None, k: int | None = None) -> list[Chunk]:
    """질문과 관련 있는 조각 k개. mode가 none이거나 질문이 비면 빈 목록입니다."""
    settings = get_settings()
    mode = mode or settings.retrieval_mode
    k = k or settings.retrieval_top_k
    if mode == "none" or not query.strip():
        return []
    if mode == "keyword":
        order = _keyword_rank(query)
    elif mode == "vector":
        order = _vector_rank(query)
    else:
        order = _rrf(_keyword_rank(query), _vector_rank(query))
    chunks = load_chunks()
    return [chunks[i] for i in order[:k]]


def as_references(chunks: list[Chunk]) -> list[dict[str, str]]:
    """AI에게 넘기는 참고 자료 모양. 글은 MAX_CHARS로 자릅니다."""
    return [{"title": c.title, "text": c.text[:MAX_CHARS], "cite": c.cite} for c in chunks]
