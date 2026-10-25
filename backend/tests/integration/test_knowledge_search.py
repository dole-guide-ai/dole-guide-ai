"""검색 색인 채우기와 하이브리드 검색 (services/knowledge.py). 모델 대신 해시 벡터를 씁니다."""

import math
import zlib
from collections.abc import Callable, Iterator
from datetime import datetime, time

import pytest
from langchain_core.embeddings import Embeddings
from langchain_core.messages import HumanMessage
from sqlalchemy.orm import Session

from app.agent.graph import TOOL_CONTEXT_KEY
from app.agent.nodes.context import attach_knowledge
from app.agent.tools import ToolContext
from app.core.clock import KST
from app.models.knowledge_chunk import EMBEDDING_DIM
from app.rules.ranking import bigrams
from app.schemas.knowledge import KnowledgeKind
from app.services import knowledge as knowledge_service
from app.services.accounts import AccountContext
from app.services.knowledge import SearchOptions, SourceDoc
from conftest import TEST_TODAY

pytestmark = pytest.mark.integration

NOW = datetime.combine(TEST_TODAY, time(9), KST)


class HashEmbeddings(Embeddings):
    """글자 묶음이 겹칠수록 가까운 결정적 벡터. 실제 모델 호출 없이 벡터 검색 경로를 확인합니다."""

    def __init__(self) -> None:
        self.calls = 0

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * EMBEDDING_DIM
        for gram in bigrams(text):
            vector[zlib.crc32(gram.encode()) % EMBEDDING_DIM] += 1
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls += len(texts)
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


GUIDES = [
    SourceDoc("FAQ-1", KnowledgeKind.FAQ, "실업인정일 변경", "질의: 실업인정일을 바꿀 수 있나요"),
    SourceDoc(
        "POL-1",
        KnowledgeKind.POLICY,
        "조기재취업수당",
        "정책: 조기재취업수당 지급 요건",
        {"source": "work24", "last_modified": "2025-07-10"},
    ),  # fmt: skip
    SourceDoc(
        "POL-ART",
        KnowledgeKind.POLICY,
        "예술인 실업급여",
        "정책: 예술인 조기재취업수당",
        {"employment_type": "artist"},
    ),  # fmt: skip
]


@pytest.fixture
def indexed(db_session: Session) -> Iterator[HashEmbeddings]:
    embeddings = HashEmbeddings()
    docs = knowledge_service.rule_card_documents() + GUIDES
    knowledge_service.sync_index(db_session, docs, embeddings)
    yield embeddings
    knowledge_service.reset_guide_index()


def test_sync_reembeds_only_changed_rows(db_session: Session, indexed: HashEmbeddings) -> None:
    changed = SourceDoc("FAQ-1", KnowledgeKind.FAQ, "실업인정일 변경", "질의: 인정일 변경 방법")
    docs = knowledge_service.rule_card_documents() + [changed, *GUIDES[1:]]
    embeddings = HashEmbeddings()

    result = knowledge_service.sync_index(db_session, docs, embeddings)

    assert (result.embedded, embeddings.calls, result.deleted) == (1, 1, 0)


def test_search_returns_rule_cards_and_guides_without_other_employment(
    db_session: Session, indexed: HashEmbeddings
) -> None:
    query = "조기재취업수당 받는 조건"

    found = knowledge_service.search(
        db_session, query, options=SearchOptions(), query_vector=indexed.embed_query(query)
    )

    assert found.rules and all(h.kind == KnowledgeKind.RULE_CARD for h in found.rules)
    assert found.guides[0].chunk_id == "POL-1"
    assert "POL-ART" not in [h.chunk_id for h in found.guides]
    assert all(h.similarity is not None for h in found.rules + found.guides)


def test_threshold_drops_unrelated_results(db_session: Session, indexed: HashEmbeddings) -> None:
    query = "점심 메뉴 추천"
    options = SearchOptions(min_similarity=0.5)

    found = knowledge_service.search(
        db_session, query, options=options, query_vector=indexed.embed_query(query)
    )

    assert found.rules == [] and found.guides == []


@pytest.mark.parametrize(("panel", "has_guides"), [("guide", True), ("round", False)])
def test_attach_knowledge_adds_guides_only_on_guide_panel(
    db_session: Session,
    indexed: HashEmbeddings,
    entered_account: Callable[[str], AccountContext],
    monkeypatch: pytest.MonkeyPatch,
    panel: str,
    has_guides: bool,
) -> None:
    monkeypatch.setattr(knowledge_service, "embed_query", indexed.embed_query)
    monkeypatch.setattr(
        knowledge_service, "options_from_settings", lambda: SearchOptions(min_similarity=0.3)
    )
    ctx = ToolContext(db_session, entered_account("lee"), TEST_TODAY, NOW)
    state = {"messages": [HumanMessage("조기재취업수당 지급 요건")], "panel": panel, "facts": {}}

    update = attach_knowledge(state, {"configurable": {TOOL_CONTEXT_KEY: ctx}})

    assert update["cited"]  # 규칙 카드는 패널과 관계없이 붙음
    assert ("guides" in update["facts"]) is has_guides
    assert bool(update["cited_sources"]) is has_guides
