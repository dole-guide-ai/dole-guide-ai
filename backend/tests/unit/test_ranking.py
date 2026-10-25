"""검색 순위 부품(rules/ranking.py)과 구어 사전(rules/synonyms.py)."""

from app.rules.ranking import Bm25Index, bigrams, rrf
from app.rules.synonyms import expand_query


def test_bigrams_ignore_spacing_and_particles() -> None:
    assert bigrams("이메일 증빙") == ["이메", "메일", "증빙"]
    assert set(bigrams("이메일로")) >= set(bigrams("이메일"))


def test_bm25_ranks_rarer_overlap_higher_and_drops_no_overlap() -> None:
    index = Bm25Index(
        [
            ("email", {"name": "이메일 증빙", "body": "보낸편지함 캡처"}),
            ("portal", {"name": "취업포털 증빙", "body": "취업활동증명서"}),
            ("other", {"name": "계좌 변경", "body": "통장 사본"}),
        ],
        {"name": 3, "body": 1},
    )

    ranked = [doc_id for doc_id, _ in index.search("이메일로 지원한 증빙", 3)]

    assert ranked[0] == "email"
    assert "other" not in ranked


def test_rrf_merges_by_rank_and_keeps_one_sided_hits() -> None:
    merged = [doc_id for doc_id, _ in rrf([["a", "b", "c"], ["b", "d"]])]

    assert merged[0] == "b"  # 두 목록 모두 위쪽
    assert set(merged) == {"a", "b", "c", "d"}


def test_expand_query_adds_admin_terms_ignoring_spaces() -> None:
    expanded = expand_query("회사에서 나가 달라고 해서 나왔어요")

    assert expanded.startswith("회사에서 나가 달라고 해서 나왔어요")
    assert "권고사직" in expanded
    assert expand_query("오늘 날씨 어때요") == "오늘 날씨 어때요"
