"""채점기준 칸의 LLM 판정 (DeepEval G-Eval).

판정 모델도 gateway를 거칩니다(JUDGE_MODEL, 비우면 AGENT_MODEL).

LLM_API_KEY가 없으면 판정을 건너뛰고 '판정 건너뜀'으로 기록합니다.
"""

import os
from dataclasses import dataclass
from typing import Any

from app.agent import gateway
from app.core.config import get_settings

# 평가 데이터를 외부 통계로 보내지 않음. 다른 값이 있어도 항상 끕니다.
os.environ["DEEPEVAL_TELEMETRY_OPT_OUT"] = "1"

DEFAULT_THRESHOLD = 0.7


@dataclass
class Verdict:
    passed: bool | None  # None = 판정 건너뜀
    score: float | None = None
    reason: str = ""


def judge(case: dict[str, Any], replies: list[str], mode: str, threshold: float) -> Verdict:
    criteria = case["expected"]["judge"]
    if not criteria:
        return Verdict(passed=True)
    if mode != "real":
        return Verdict(passed=mode == "selftest", score=1.0 if mode == "selftest" else 0.0)
    if not get_settings().llm_api_key:
        return Verdict(passed=None, reason="LLM_API_KEY가 없어 LLM 판정 건너뜀")

    from deepeval.metrics import GEval
    from deepeval.test_case import LLMTestCase, SingleTurnParams

    metric = GEval(
        name=case["id"],
        criteria=criteria,
        evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
        model=_gateway_judge(),
        threshold=threshold,
        async_mode=False,
        verbose_mode=False,
    )
    situation = f"상황: {case['description']}\n사용자: " + " / ".join(case["input"]["messages"])
    metric.measure(LLMTestCase(input=situation, actual_output="\n".join(replies)))
    return Verdict(passed=bool(metric.success), score=metric.score, reason=metric.reason or "")


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
