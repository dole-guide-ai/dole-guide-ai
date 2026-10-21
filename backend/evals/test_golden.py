"""골든셋 실행. 루트에서 `pnpm eval:golden`(실제 AI) · `pnpm eval:golden:selftest`(채점 코드 점검).

문항은 golden/golden_set.csv가 원본이고,
`pnpm golden:build`가 만든 scenarios/golden/*.json을 읽습니다.
"""

import json

import pytest
from langchain_core.callbacks import BaseCallbackHandler

from app.agent import gateway
from evals.golden import grading
from evals.golden.adapter import AgentNotReadyError, run_agent, run_selftest
from evals.golden.judge import judge
from evals.golden.schema import OUT_DIR

pytestmark = pytest.mark.eval

NO_CASES = "골든셋 JSON이 없어요. 루트에서 pnpm golden:build를 먼저 실행하세요."
AREA_ORDER = ["procedure", "form_fill", "grounding", "masking"]
CASES = sorted(
    (json.loads(p.read_text(encoding="utf-8")) for p in OUT_DIR.glob("*/*.json")),
    key=lambda case: (AREA_ORDER.index(case["area"]), case["id"]),
)


@pytest.fixture
def model_inputs(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """에이전트가 gateway로 모델에 보낸 글을 모읍니다(개인정보 '모델' 검사용).

    판정 모델(judge)은 빼고 모읍니다.
    """
    texts: list[str] = []

    class Recorder(BaseCallbackHandler):
        def on_chat_model_start(self, serialized, messages, **kwargs) -> None:
            texts.extend(str(message.content) for batch in messages for message in batch)

    original = gateway.get_chat_model

    def recording(role: str = "agent"):
        model = original(role=role)
        if role != "judge":
            model.callbacks = [*(model.callbacks or []), Recorder()]
        return model

    monkeypatch.setattr(gateway, "get_chat_model", recording)
    return texts


@pytest.mark.skipif(not CASES, reason=NO_CASES)
@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_golden(case, golden_options, golden_report, model_inputs) -> None:
    record = golden_report.start(case)
    if case["review"] == "보류":
        record.skip("검수 보류")
        pytest.skip("검수 보류")
    if golden_options.area not in ("all", case["area"]):
        record.skip("영역 선택에서 빠짐")
        pytest.skip("영역 선택에서 빠짐")

    mode = golden_options.agent
    try:
        result = run_agent(case) if mode == "real" else run_selftest(case, broken=mode == "broken")
    except AgentNotReadyError as error:
        record.skip(str(error))
        pytest.skip(str(error))
    if not result.model_inputs:
        result.model_inputs = list(model_inputs)

    failures = grading.check(case, result)
    verdict = judge(case, result.replies, mode, golden_options.threshold)
    if verdict.passed is False:
        score = f"{verdict.score or 0:.2f}점 (기준 {golden_options.threshold})"
        failures.append(f"LLM 판정: {score} {verdict.reason}")
    record.finish(failures, verdict.passed)
    if failures:
        message = "\n".join(failures)
        if case["review"] == "확인필요":
            pytest.xfail(f"검수 확인필요 문항\n{message}")
        pytest.fail(message, pytrace=False)
