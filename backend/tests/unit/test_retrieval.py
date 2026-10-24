import pytest

from app.agent import retrieval
from app.agent.input.images import as_image_part
from app.core.config import Settings
from app.rules import situation
from app.rules.rule_cards import build_rule_cards


def test_tokenize_splits_hangul_into_bigrams() -> None:
    assert retrieval.tokenize("실업급여 STEP 1") == ["실업", "업급", "급여", "step", "1"]


# 지식 자료(data/knowledge)는 크롤링 결과라 커밋하지 않습니다.
# 자료가 있는 곳에서만 검색을 확인합니다.
needs_chunks = pytest.mark.skipif(
    not any(retrieval.CHUNK_DIR.glob("*.jsonl")), reason="지식 자료(data/knowledge)가 없음"
)


@needs_chunks
def test_keyword_search_finds_waiting_period_faq() -> None:
    results = retrieval.search("대기기간 동안 돈이 나오나요", mode="keyword", k=3)

    assert results
    assert any("대기" in chunk.text for chunk in results)
    assert all(chunk.cite for chunk in results)


def test_none_mode_and_empty_query_search_nothing() -> None:
    assert retrieval.search("실업급여", mode="none") == []
    assert retrieval.search("   ", mode="keyword") == []


def test_references_are_trimmed() -> None:
    chunk = retrieval.Chunk("c1", "제목", "가" * 2000, "출처")

    (ref,) = retrieval.as_references([chunk])

    assert len(ref["text"]) == retrieval.MAX_CHARS
    assert ref["cite"] == "출처"


@pytest.mark.parametrize(
    ("group", "volunteer_allowed"), [("general", False), ("age65_or_disabled", True)]
)
def test_rule_cards_follow_round_rules(group: str, volunteer_allowed: bool) -> None:
    derived = {**situation.derive({
        "age_at_separation": 58, "stage": "recognition", "completed_rounds": 3,
        "next_recognition_date": "2026-12-22", "last_recognition_date": "2026-11-24",
        "demo_today": "2026-12-16",
    }), "group": group}  # fmt: skip

    allowed = build_rule_cards(derived)[0]["text"]

    assert ("자원봉사" in allowed) is volunteer_allowed
    assert any("취업활동증명서" in card["text"] for card in build_rule_cards(derived))


def test_missing_chunks_fail_loudly(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """코드래빗 지적: 자료가 없으면 검색이 조용히 빈 목록을 돌려주던 문제."""
    monkeypatch.setattr(retrieval, "CHUNK_DIR", tmp_path)
    retrieval.load_chunks.cache_clear()
    retrieval._bm25.cache_clear()

    with pytest.raises(FileNotFoundError):
        retrieval.search("대기기간", mode="keyword")
    retrieval.load_chunks.cache_clear()
    retrieval._bm25.cache_clear()


def test_vector_mode_needs_embedding_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """코드래빗 지적: 임베딩 모델 없이 vector 검색을 켜도 서버가 뜨던 문제."""
    monkeypatch.setenv("RETRIEVAL_MODE", "vector")
    monkeypatch.setenv("EMBEDDING_MODEL", "")

    with pytest.raises(ValueError, match="EMBEDDING_MODEL"):
        Settings()


def test_image_part_uses_file_content_and_rejects_unknown(tmp_path) -> None:
    """코드래빗 지적: 모르는 형식을 PNG로 꾸며 보내던 문제."""
    jpeg = tmp_path / "photo"  # 확장자 없음
    jpeg.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 10)
    text = tmp_path / "note.png"
    text.write_bytes(b"not an image")

    assert as_image_part(str(jpeg))["image_url"]["url"].startswith("data:image/jpeg;")
    with pytest.raises(ValueError):
        as_image_part(str(text))
