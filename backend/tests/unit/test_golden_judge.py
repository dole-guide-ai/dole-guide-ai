"""골든셋 LLM 판정(evals/golden/judge): 기준마다 따로 묻고, 모두 '예'여야 통과합니다(#261)."""

from types import SimpleNamespace

import pytest

from app.agent import gateway
from app.core.config import get_settings
from evals.golden import judge as judge_module
from evals.golden.judge import CriterionVerdict, judge

CASE = {
    "description": "합성 상황",
    "input": {"messages": ["첫 말", "둘째 말"]},
    "expected": {"judge": ["날짜를 되묻는가", "기록하지 않는가"]},
}


@pytest.fixture
def answers(monkeypatch: pytest.MonkeyPatch):
    """기준 글 → 판정 답. 판정 모델에 보낸 글도 모읍니다."""
    table: dict[str, str] = {}
    sent: list[str] = []

    def invoke(messages):
        prompt = messages[-1].content
        sent.append(prompt)
        criterion = prompt.split("<기준>\n")[1].split("\n</기준>")[0]
        return CriterionVerdict(answer=table[criterion], reason=f"{criterion} 근거")

    model = SimpleNamespace(with_structured_output=lambda schema: SimpleNamespace(invoke=invoke))
    monkeypatch.setattr(gateway, "get_chat_model", lambda role="agent": model)
    monkeypatch.setattr(get_settings(), "openai_api_key", "test-key")
    monkeypatch.setattr(get_settings(), "judge_provider", "openai")
    return SimpleNamespace(table=table, sent=sent)


def test_all_yes_passes_and_each_criterion_is_asked_alone(answers) -> None:
    answers.table.update({"날짜를 되묻는가": "예", "기록하지 않는가": "예"})

    verdict = judge(CASE, ["첫 답", "둘째 답"], "real")

    assert verdict.passed is True and verdict.score == 1.0
    assert len(answers.sent) == 2
    assert all(prompt.count("<기준>") == 1 for prompt in answers.sent)
    assert "[2] 챗봇: 둘째 답" in answers.sent[0]


@pytest.mark.parametrize("answer", ["아니오", "모름"])
def test_no_or_unknown_fails_with_the_criterion_named(answers, answer: str) -> None:
    answers.table.update({"날짜를 되묻는가": "예", "기록하지 않는가": answer})

    verdict = judge(CASE, ["첫 답", "둘째 답"], "real")

    assert verdict.passed is False and verdict.score == 0.5
    assert verdict.reason == f"기준2 {answer}: 기록하지 않는가 근거"


def test_selftest_and_missing_key_do_not_call_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gateway, "get_chat_model", lambda role="agent": pytest.fail("호출됨"))
    assert judge(CASE, [], "selftest").passed is True
    assert judge(CASE, [], "broken").passed is False
    monkeypatch.setattr(
        judge_module, "get_settings", lambda: SimpleNamespace(has_llm_key=lambda role: False)
    )
    assert judge(CASE, [], "real").passed is None
