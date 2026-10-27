"""채점기준 칸의 LLM 판정. 기준마다 판정 모델을 따로 불러 예·아니오·모름 중 하나로 답하게 합니다.

점수(0~1)와 통과 기준 대신 이진 판정을 씁니다. 점수는 실행마다 흔들리고, 여러 조건을 한 번에
물으면 어느 조건에서 떨어졌는지 알 수 없기 때문입니다(#261). 모든 기준이 '예'여야 통과이고,
'모름'은 판단할 정보가 없다는 뜻이라 통과로 치지 않습니다.

판정 모델도 gateway를 거칩니다(JUDGE_MODEL, 비우면 AGENT_MODEL).
판정 모델 공급자 키가 없으면 판정을 건너뛰고 '판정 건너뜀'으로 기록합니다.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.agent import gateway
from app.core.config import get_settings
from app.rules import periods

PROMPT = (Path(__file__).parent / "judge_prompt.md").read_text(encoding="utf-8")
YES = "예"


class CriterionVerdict(BaseModel):
    answer: Literal["예", "아니오", "모름"]
    reason: str = Field(description="판정 근거 한 문장")


@dataclass
class Verdict:
    passed: bool | None  # None = 판정 건너뜀
    score: float | None = None  # '예'인 기준의 비율(실험 비교용)
    reason: str = ""


def judge(case: dict[str, Any], replies: list[str], mode: str) -> Verdict:
    criteria = case["expected"]["judge"]
    if not criteria:
        return Verdict(passed=True)
    if mode != "real":
        return Verdict(passed=mode == "selftest", score=1.0 if mode == "selftest" else 0.0)
    if not get_settings().has_llm_key("judge"):
        return Verdict(passed=None, reason="판정 모델 공급자 키가 없어 LLM 판정 건너뜀")

    model = gateway.get_chat_model(role="judge").with_structured_output(CriterionVerdict)
    conversation = _conversation(case, replies)
    misses = []
    for n, criterion in enumerate(criteria, 1):
        verdict = model.invoke(
            [
                SystemMessage(PROMPT),
                HumanMessage(f"{conversation}\n\n<기준>\n{criterion}\n</기준>"),
            ]
        )
        if verdict.answer != YES:
            misses.append(f"기준{n} {verdict.answer}: {verdict.reason}")
    yes = len(criteria) - len(misses)
    return Verdict(passed=not misses, score=yes / len(criteria), reason=" / ".join(misses))


def _start_state(case: dict[str, Any]) -> str:
    """대화 전 시작 상태 요약(판정 모델이 "모름"으로 빠지지 않게). 합성 값이라 개인정보 없음."""
    state = case["input"].get("state")
    if not state:
        return ""
    # 수급자 유형은 러너가 계정을 만들 때와 같은 계산으로 보여 줍니다(67세 일반 → 65세 이상).
    group = periods.recipient_group(
        state.get("age_at_separation") or 0,
        bool(state.get("has_disability")),
        state.get("recipient_type") == "repeat",
    )
    parts = [f"단계 {state.get('stage')}", f"수급자 유형 {group}"]
    if state.get("stage") == "recognition" and state.get("completed_rounds") is not None:
        parts.append(f"지금 {state['completed_rounds'] + 1}차")
    parts.append(f"오늘 {state.get('demo_today')} {state.get('demo_time')}")
    if activities := case["input"].get("activities") or []:
        # 같은 날 여러 건이면 날짜도 건수만큼 적습니다(같은 날 활동 문항).
        days = ", ".join(sorted(a["date"] for a in activities))
        parts.append(f"이미 기록된 활동 {len(activities)}건({days})")
    return "시작 상태: " + " · ".join(parts)


def _conversation(case: dict[str, Any], replies: list[str]) -> str:
    """판정 모델에 보이는 대화. 턴마다 사용자 말과 챗봇 답을 짝지어 보여 줍니다."""
    situation = "\n".join(filter(None, [case["description"], _start_state(case)]))
    lines = [f"<상황>\n{situation}\n</상황>", "<대화>"]
    for n, (said, reply) in enumerate(zip(case["input"]["messages"], replies, strict=False), 1):
        lines += [f"[{n}] 사용자: {said}", f"[{n}] 챗봇: {reply}"]
    lines.append("</대화>")
    return "\n".join(lines)
