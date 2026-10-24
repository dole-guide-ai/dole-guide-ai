import pytest

from app.agent import retrieval
from app.rules import situation
from app.rules.rule_cards import build_rule_cards


def test_tokenize_splits_hangul_into_bigrams() -> None:
    assert retrieval.tokenize("실업급여 STEP 1") == ["실업", "업급", "급여", "step", "1"]


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
