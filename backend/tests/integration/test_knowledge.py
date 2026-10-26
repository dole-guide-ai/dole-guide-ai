"""RAG 하이브리드 검색과 search_guide → 근거 줄 (노션 「RAG 설계 (복사본)」 7.5 · 7.7)."""

import hashlib
from collections.abc import Callable

import pytest
from langchain_core.embeddings import Embeddings
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.agent import gateway
from app.agent.responder import TurnInput, graph_responder
from app.repositories import knowledge as repo
from app.services import knowledge as knowledge_service
from app.services.accounts import AccountContext
from conftest import TEST_TODAY

pytestmark = pytest.mark.integration

MODEL = "fake-embed"
DIM = 16


class HashEmbeddings(Embeddings):
    """낱말 해시로 만든 가짜 임베딩: 같은 낱말이 많을수록 가깝습니다."""

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * DIM
        for word in knowledge_service.tokenize(text):
            vector[int(hashlib.md5(word.encode()).hexdigest(), 16) % DIM] += 1.0  # noqa: S324
        return vector if any(vector) else [1.0] + [0.0] * (DIM - 1)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


ROWS = [
    (
        "C1",
        "work24",
        "SI1",
        "primary",
        "실업급여 수급 중 재취업활동은 구직활동과 직업훈련 참여로 인정됩니다.",
    ),
    (
        "C2",
        "moel_1350",
        "F1",
        "secondary",
        "자원봉사는 60세 이상만 재취업활동으로 한 번 인정됩니다.",
    ),
    (
        "C3",
        "work24",
        "SI2",
        "primary",
        "국민내일배움카드는 고용24에서 신청하고 훈련비를 지원받습니다.",
    ),
]


@pytest.fixture
def chunks(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    embedder = HashEmbeddings()
    # 평가가 테스트 DB에 적재한 실제 자료가 있어도 이 테스트는 합성 자료만 봅니다(롤백됨).
    db_session.execute(delete(repo.KnowledgeChunk))
    for chunk_id, source, doc, priority, text in ROWS:
        repo.upsert_chunk(
            db_session,
            repo.KnowledgeChunk(
                chunk_id=chunk_id,
                source_id=f"KB-{source}-{doc}",
                source=source,
                doc_id=doc,
                chunk_scope="content",
                chunk_type="section",
                title=f"합성 자료 {doc}",
                content=text,
                source_url=f"https://example.test/{doc}",
                priority=priority,
                needs_verification=False,
                content_hash=chunk_id,
                tokens=knowledge_service.tokenize(text),
                metadata_json={},
            ),
        )
        db_session.flush()
        repo.upsert_embedding(
            db_session,
            repo.ChunkEmbedding(
                chunk_id=chunk_id,
                model=MODEL,
                dim=DIM,
                embedding=embedder.embed_query(text),
                content_hash=chunk_id,
            ),
        )
    db_session.flush()
    knowledge_service.reset_index()
    monkeypatch.setattr(knowledge_service, "embedding_model", lambda: MODEL)
    monkeypatch.setattr(gateway, "get_embeddings", lambda *a, **k: embedder)
    yield
    knowledge_service.reset_index()


def test_hybrid_search_finds_related_chunk_first(db_session: Session, chunks) -> None:
    found = knowledge_service.search(db_session, "자원봉사도 재취업활동으로 인정돼요?")

    assert found[0]["chunk_id"] == "C2"
    assert found[0]["source_id"] == "KB-moel_1350-F1"
    assert found[0]["source_name"] == "고용노동부 1350 FAQ"


def test_unrelated_question_is_not_found(db_session: Session, chunks, monkeypatch) -> None:
    """벡터 없이 키워드만 쓸 때도, 질문 낱말을 덮는 자료가 없으면 찾지 못함입니다."""
    monkeypatch.setattr(knowledge_service, "embedding_model", lambda: "")

    assert knowledge_service.search(db_session, "비트코인 시세 알려 줘") == []
    assert knowledge_service.search(db_session, "국민내일배움카드 신청")[0]["chunk_id"] == "C3"


def test_search_guide_reply_gets_cite_from_used_chunk(
    db_session: Session,
    chunks,
    entered_account: Callable[[str], AccountContext],
    scripted_llm,
) -> None:
    account = entered_account("lee")
    scripted_llm(
        [
            AIMessage(
                "",
                tool_calls=[
                    {"name": "search_guide", "args": {"query": "자원봉사 인정"}, "id": "s1"}
                ],
            ),
            AIMessage("자원봉사는 60세 이상만 한 번 인정돼요 [1]."),
        ]
    )
    turn = TurnInput(
        account.user_id,
        "lee",
        "자원봉사도 재취업활동으로 인정돼요?",
        "text",
        TEST_TODAY,
        db=db_session,
        anchor_date=account.anchor_date,
    )

    events = list(graph_responder(turn, InMemorySaver()))
    done = next(e.data for e in events if e.name == "done")
    text = "".join(e.data.text for e in events if e.name == "token")

    assert "[1]" not in text and "60세" in text
    assert done.rule_refs and done.rule_refs[0].startswith("KB-")
    assert done.cite_links and done.cite_links[0].url
