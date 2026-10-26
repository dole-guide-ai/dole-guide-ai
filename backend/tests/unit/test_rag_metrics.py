"""RAG 검색 지표 계산."""

import pytest

from evals.rag.metrics import mrr_at_k, ndcg_at_k, recall_at_k


def test_metrics_with_multiple_gold_chunks() -> None:
    ranked = ["x", "a", "y", "b"]
    gold = {"a", "b"}

    assert recall_at_k(ranked, gold, 1) == 0.0
    assert recall_at_k(ranked, gold, 5) == 1.0
    assert mrr_at_k(ranked, gold, 10) == 0.5
    assert 0 < ndcg_at_k(ranked, gold, 10) < 1
    assert ndcg_at_k(["a", "b"], gold, 10) == pytest.approx(1.0)
