import json

import pytest

from app.agent.nodes import classify_intent as node
from app.core.config import get_settings


@pytest.mark.parametrize(
    ("message", "intent"),
    [
        ("이메일로 지원했으면 증빙은 뭐예요?", node.RULE_QUESTION),
        ("학원 다니는 것도 활동으로 돼요?", node.RULE_QUESTION),
        ("취업특강은 몇 번까지 돼요?", node.RULE_QUESTION),
        ("어제 OO기획 홈페이지에서 지원했어요", node.OTHER),
        ("취업특강 들었어요", node.OTHER),
        ("다음 주에 뭐 해야 돼요?", node.OTHER),
    ],
)
def test_by_keyword(message: str, intent: str) -> None:
    assert node.by_keyword(message) == intent


def test_by_llm_reads_json_and_falls_back(fake_llm) -> None:
    fake_llm([json.dumps({"intent": "rule_question"}), "JSON이 아님", '{"intent": "모름"}'])

    assert node.by_llm("학원도 돼요?") == node.RULE_QUESTION
    assert node.by_llm("학원도 돼요?") == node.OTHER
    assert node.by_llm("학원도 돼요?") == node.OTHER


def test_off_mode_does_not_classify(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RULE_CARDS_MODE", "off")
    get_settings.cache_clear()
    try:
        assert node.classify_intent({"message": "증빙은 뭐예요?"}) == {"intent": node.OTHER}
    finally:
        get_settings.cache_clear()
