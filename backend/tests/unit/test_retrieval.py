"""검색 후보 재정렬 (agent/retrieval.rerank_cards). 모델은 정해진 답을 돌려주는 가짜로 바꿉니다."""

import pytest

from app.agent import gateway, retrieval
from app.agent.retrieval import ChosenCards, rerank_cards
from app.rules.rule_cards import cards_by_id

CANDIDATES = ["ELIG-182", "ELIG-183", "ELIG-184", "DUE-056"]


class FakeModel:
    def __init__(self, answer: ChosenCards | Exception) -> None:
        self.answer = answer

    def with_structured_output(self, _schema):
        return self

    def invoke(self, _messages):
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


@pytest.fixture
def cards():
    by_id = cards_by_id()
    return [by_id[i] for i in CANDIDATES]


def _use(monkeypatch: pytest.MonkeyPatch, answer: ChosenCards | Exception) -> None:
    monkeypatch.setattr(gateway, "get_chat_model", lambda role="agent": FakeModel(answer))


def _ids(found) -> list[str]:
    return [c.rule_id for c in found]


def test_keeps_model_order_and_drops_unknown_ids(monkeypatch, cards) -> None:
    _use(monkeypatch, ChosenCards(ids=["ELIG-184", "NOPE-1", "ELIG-184", "DUE-056"]))

    assert _ids(rerank_cards("2년 일했으면 며칠 받아요?", cards, 5)) == ["ELIG-184", "DUE-056"]


def test_respects_limit(monkeypatch, cards) -> None:
    _use(monkeypatch, ChosenCards(ids=CANDIDATES))

    assert _ids(rerank_cards("질문", cards, 2)) == CANDIDATES[:2]


def test_empty_choice_means_no_relevant_card(monkeypatch, cards) -> None:
    _use(monkeypatch, ChosenCards(ids=[]))

    assert rerank_cards("점심 메뉴 추천해 줘", cards, 5) == []


@pytest.mark.parametrize(
    "answer", [RuntimeError("모델 장애"), ChosenCards(ids=["NOPE-1", "NOPE-2"])]
)
def test_falls_back_to_search_order(monkeypatch, cards, answer) -> None:
    _use(monkeypatch, answer)

    assert _ids(rerank_cards("질문", cards, 2)) == CANDIDATES[:2]


def test_prompt_lists_candidates_with_target(cards) -> None:
    line = retrieval._candidate(cards[2])

    assert line.startswith("ELIG-184 | ") and "50세 이상" in line


def test_without_fallback_failure_is_raised(monkeypatch, cards) -> None:
    _use(monkeypatch, RuntimeError("모델 장애"))

    with pytest.raises(RuntimeError):
        rerank_cards("질문", cards, 2, fallback=False)
