import pytest

from app.agent import gateway
from evals.conftest import load_scenarios

pytestmark = pytest.mark.eval


@pytest.mark.parametrize("scenario", load_scenarios("_example"), ids=lambda s: s["id"])
def test_example_scenario(scenario: dict, fake_llm) -> None:
    # 하네스 확인용: 가짜 모델로 시나리오 로딩·판정 흐름만 검증합니다.
    fake_llm(scenario["input"]["messages"])

    reply = gateway.get_chat_model().invoke(scenario["input"]["messages"][-1])

    for phrase in scenario["expected"]["must_include"]:
        assert phrase in reply.content
