"""검색 지표 (노션 「RAG 설계 (복사본)」 7.2 · 7.4). 정답 청크가 여러 개일 수 있습니다."""

import math


def recall_at_k(ranked: list[str], gold: set[str], k: int) -> float:
    """상위 k개 안에 정답이 하나라도 있으면 1."""
    return 1.0 if gold & set(ranked[:k]) else 0.0


def mrr_at_k(ranked: list[str], gold: set[str], k: int) -> float:
    for rank, chunk_id in enumerate(ranked[:k], start=1):
        if chunk_id in gold:
            return 1 / rank
    return 0.0


def ndcg_at_k(ranked: list[str], gold: set[str], k: int) -> float:
    dcg = sum(1 / math.log2(rank + 1) for rank, c in enumerate(ranked[:k], start=1) if c in gold)
    ideal = sum(1 / math.log2(rank + 1) for rank in range(1, min(len(gold), k) + 1))
    return dcg / ideal if ideal else 0.0


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0
