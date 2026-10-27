"""검색 한 그룹의 순위·임계값 처리 (services/knowledge.py). DB 대신 레포지토리를 바꿔 끼웁니다."""

from types import SimpleNamespace

import pytest

from app.schemas.knowledge import KnowledgeKind
from app.services import knowledge as knowledge_service
from app.services.knowledge import SearchOptions

# 단어 검색 순위와 각 행의 코사인 유사도
BM25_ORDER = ["a", "b", "c", "d", "e"]
SIMILARITY = {"a": 0.9, "b": 0.2, "c": 0.8, "d": 0.7, "e": 0.6}


@pytest.fixture
def fake_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    def get_many(_db, ids, _vector=None):
        chunk = lambda i: SimpleNamespace(  # noqa: E731
            chunk_id=i, kind=KnowledgeKind.RULE_CARD, title=i, text=i, meta={}
        )
        return {i: (chunk(i), SIMILARITY[i]) for i in ids}

    monkeypatch.setattr(knowledge_service.knowledge_repo, "get_many", get_many)


def _search(limit: int, min_similarity: float | None) -> list[str]:
    options = SearchOptions(vector=False, min_similarity=min_similarity)
    hits = knowledge_service._search_group(
        None, "질문", [0.0], (KnowledgeKind.RULE_CARD,), lambda _q, n: BM25_ORDER[:n],
        lambda _c: True, limit, options,
    )  # fmt: skip
    return [h.chunk_id for h in hits]


def test_threshold_refills_dropped_slot_from_next_rank(fake_repo: None) -> None:
    # b(0.2)가 빠진 자리를 d가 채워 3장을 그대로 붙입니다.
    assert _search(3, 0.5) == ["a", "c", "d"]


def test_without_threshold_keeps_rrf_order(fake_repo: None) -> None:
    assert _search(3, None) == ["a", "b", "c"]
