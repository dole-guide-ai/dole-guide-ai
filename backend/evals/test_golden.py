"""골든셋 실행. 루트에서 `pnpm eval:golden`(실제 AI) · `pnpm eval:golden:selftest`(채점 코드 점검)
· `pnpm eval:golden:setup`(모델 없이 문항 시작 상태 점검).

문항은 golden/golden_set.csv가 원본이고,
`pnpm golden:build`가 만든 scenarios/golden/*.json을 읽습니다.
"""

import json

import pytest
from langchain_core.callbacks import BaseCallbackHandler
from langsmith import testing as ls

from app.agent import gateway
from evals.golden import grading
from evals.golden.adapter import (
    AgentNotReadyError,
    CaseSetupError,
    run_agent,
    run_selftest,
    run_setup,
)
from evals.golden.judge import Verdict, judge
from evals.golden.schema import OUT_DIR
from evals.golden.tracking import LANGSMITH_SUITE, experiment_metadata

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


@pytest.fixture
def golden_db(golden_options, request: pytest.FixtureRequest):
    """실제 실행·시작 상태 점검만 테스트 DB를 씁니다(끝나면 롤백). selftest는 DB 없이 돕니다."""
    uses_db = golden_options.agent in ("real", "setup")
    return request.getfixturevalue("db_session") if uses_db else None


@pytest.mark.skipif(not CASES, reason=NO_CASES)
@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
# 실제 실행은 LangSmith 실험으로도 남습니다(문항 = 데이터셋 예제). selftest는 끔(evals/conftest.py).
@pytest.mark.langsmith(test_suite_name=LANGSMITH_SUITE, metadata=experiment_metadata())
def test_golden(case, golden_options, golden_report, model_inputs, golden_db) -> None:
    record = golden_report.start(case)
    if case["review"] == "보류":
        record.skip("검수 보류")
        pytest.skip("검수 보류")
    if golden_options.area not in ("all", case["area"]):
        record.skip("영역 선택에서 빠짐")
        pytest.skip("영역 선택에서 빠짐")

    mode = golden_options.agent
    # 예상 못 한 예외는 보고서에 '건너뜀'이 아니라 오류로 남깁니다.
    # 예외 메시지에는 입력값이 섞일 수 있어 종류 이름만 적습니다.
    if mode == "setup":
        try:
            run_setup(case, golden_db)
        except CaseSetupError as error:
            record.broken(str(error))
            pytest.fail(f"문항 오류: {error}", pytrace=False)
        record.finish([], True)
        return
    try:
        if mode == "real":
            result = run_agent(case, golden_db)
        else:
            result = run_selftest(case, broken=mode == "broken")
        if not result.model_inputs:
            result.model_inputs = list(model_inputs)
        failures = grading.check(case, result)
        ls.log_inputs({"id": case["id"], "area": case["area"], "input": case["input"]})
        ls.log_reference_outputs(case["expected"])
        ls.log_outputs(
            {"replies": result.replies, "cites": result.cites, "next_action": result.next_action}
        )
    except AgentNotReadyError as error:
        record.skip(str(error))
        pytest.skip(str(error))
    except CaseSetupError as error:
        # AI 실력이 아니라 문항·러너가 고장 난 것이라 실패와 따로 셉니다.
        record.broken(str(error))
        pytest.fail(f"문항 오류: {error}", pytrace=False)
    except Exception as error:
        record.finish([f"실행 오류: {type(error).__name__}"], None)
        raise
    try:
        verdict = (
            judge(case, result.replies, mode)
            if golden_options.judge
            else Verdict(passed=None, reason="--golden-judge off")
        )
    except Exception as error:
        record.finish([*failures, f"LLM 판정 오류: {type(error).__name__}"], None)
        raise
    if verdict.passed is False:
        failures.append(f"LLM 판정: {verdict.reason}")
    record.finish(failures, verdict.passed)
    # 규칙 채점(통과 여부·실패 수)과 LLM 판정 점수를 따로 남겨 실험끼리 비교합니다.
    ls.log_feedback(key="rule_pass", score=int(not [f for f in failures if "LLM 판정" not in f]))
    ls.log_feedback(key="failures", score=len(failures))
    if verdict.score is not None:
        ls.log_feedback(key="judge", score=verdict.score)
    if failures:
        message = "\n".join(failures)
        if case["review"] == "확인필요":
            pytest.xfail(f"검수 확인필요 문항\n{message}")
        pytest.fail(message, pytrace=False)
