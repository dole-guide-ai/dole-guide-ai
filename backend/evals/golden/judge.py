"""채점기준 칸의 LLM 판정 (DeepEval G-Eval).

판정 모델도 gateway를 거칩니다(JUDGE_MODEL, 비우면 AGENT_MODEL).

판정 모델 공급자 키가 없거나 `--golden-judge=off`면 판정을 건너뛰고 '판정 건너뜀'으로 기록합니다.

G-Eval은 채점기준마다 '채점 단계'를 먼저 모델로 만든 뒤 점수를 매깁니다(호출 2번). 같은 기준이면
단계도 같으므로 `backend/.cache/golden_judge_steps.json`에 두고 다시 쓰면 호출이 1번으로 줍니다.
"""

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.agent import gateway
from app.core.config import get_settings

# 평가 데이터를 외부 통계로 보내지 않음. 다른 값이 있어도 항상 끕니다.
os.environ["DEEPEVAL_TELEMETRY_OPT_OUT"] = "1"

DEFAULT_THRESHOLD = 0.7
STEPS_CACHE = Path(__file__).resolve().parents[2] / ".cache" / "golden_judge_steps.json"


@dataclass
class Verdict:
    passed: bool | None  # None = 판정 건너뜀
    score: float | None = None
    reason: str = ""


def judge(
    case: dict[str, Any], replies: list[str], mode: str, threshold: float, enabled: bool = True
) -> Verdict:
    criteria = case["expected"]["judge"]
    if not criteria:
        return Verdict(passed=True)
    if mode != "real":
        return Verdict(passed=mode == "selftest", score=1.0 if mode == "selftest" else 0.0)
    if not enabled:
        return Verdict(passed=None, reason="--golden-judge=off라 LLM 판정 건너뜀")
    if not get_settings().has_llm_key("judge"):
        return Verdict(passed=None, reason="판정 모델 공급자 키가 없어 LLM 판정 건너뜀")

    from deepeval.metrics import GEval
    from deepeval.test_case import LLMTestCase, SingleTurnParams

    metric = GEval(
        name=case["id"],
        criteria=criteria,
        evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
        model=_gateway_judge(),
        evaluation_steps=_cached_steps(criteria),
        threshold=threshold,
        async_mode=False,
        verbose_mode=False,
    )
    situation = f"상황: {case['description']}\n사용자: " + " / ".join(case["input"]["messages"])
    if not metric.evaluation_steps:
        # 처음 보는 기준: 단계를 한 번 만들어 저장하고 이번 채점에도 씁니다.
        metric.evaluation_steps = metric._generate_evaluation_steps(False)
        _save_steps(criteria, metric.evaluation_steps)
    metric.measure(LLMTestCase(input=situation, actual_output="\n".join(replies)))
    return Verdict(passed=bool(metric.success), score=metric.score, reason=metric.reason or "")


def _steps_key(criteria: str) -> str:
    """판정 모델이 바뀌면 단계도 새로 만듭니다."""
    model = get_settings().chat_target("judge")[1]
    return hashlib.sha256(f"{model}\n{criteria}".encode()).hexdigest()


def _load_steps() -> dict[str, list[str]]:
    if not STEPS_CACHE.exists():
        return {}
    return json.loads(STEPS_CACHE.read_text(encoding="utf-8"))


def _cached_steps(criteria: str) -> list[str] | None:
    return _load_steps().get(_steps_key(criteria))


def _save_steps(criteria: str, steps: list[str]) -> None:
    saved = _load_steps()
    saved[_steps_key(criteria)] = steps
    STEPS_CACHE.parent.mkdir(parents=True, exist_ok=True)
    STEPS_CACHE.write_text(json.dumps(saved, ensure_ascii=False, indent=1), encoding="utf-8")


def _gateway_judge() -> Any:
    from deepeval.models import DeepEvalBaseLLM

    class GatewayJudge(DeepEvalBaseLLM):
        def load_model(self) -> Any:
            return gateway.get_chat_model(role="judge")

        def generate(self, prompt: str) -> str:
            return str(self.model.invoke(prompt).content)

        async def a_generate(self, prompt: str) -> str:
            return str((await self.model.ainvoke(prompt)).content)

        def get_model_name(self) -> str:
            return "gateway:judge"

    return GatewayJudge()
