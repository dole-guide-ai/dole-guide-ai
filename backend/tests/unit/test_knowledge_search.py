"""RAG 검색의 순수 부품: 형태소 · 동의어 확장 · RRF."""

from app.services.knowledge import expand, rrf, tokenize


def test_tokenize_keeps_content_words_and_drops_fillers() -> None:
    tokens = tokenize("구직활동은 몇 번 해야 돼요?")

    assert {"구직", "활동"} <= set(tokens)
    assert not {"하", "되", "번"} & set(tokens)


def test_expand_adds_policy_terms_and_keeps_original() -> None:
    expanded = expand("회사에서 잘렸어요")

    assert expanded.startswith("회사에서 잘렸어요")
    assert "해고" in expanded and "비자발적 이직" in expanded


def test_rrf_sums_ranks_from_both_lists() -> None:
    scores = rrf([["a", "b"], ["b", "c"]], k=60)

    assert max(scores, key=scores.get) == "b"
    assert scores["a"] == 1 / 61
