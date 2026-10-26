"""가상 사용자. 판정 모델(JUDGE_MODEL)이 시나리오의 사실·말투대로 다음 말을 만듭니다.

에이전트와 다른 모델을 써서, 에이전트가 자기 질문에 유리하게 답을 만들지 않게 합니다.
"""

from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agent import gateway
from evals.interview.scenarios import Scenario

PROMPT = (Path(__file__).parent / "user_prompt.md").read_text(encoding="utf-8")
END = "[끝]"


def facts_text(s: Scenario) -> str:
    lines = []
    for i, c in enumerate(s.careers, 1):
        start, end = _ym(c.start), _ym(c.end)
        when = f"{start}부터 {end}까지" + (f" (처음엔 '{c.vague}'라고 말함)" if c.vague else "")
        lines.append(
            f"- 경력 {i}: {c.company}, {when}, 하던 일: {', '.join(c.duties)}, "
            f"직급·직책: {c.position or '없었음'}, 직종: {c.occupation or '모름'}"
        )
    if s.education:
        lines.append(f"- 최종 학력: {s.education} 졸업, 학교 이름은 'OO{s.education}'")
    else:
        lines.append("- 최종 학력: 모름")
    lines.append(f"- 자격증·면허: {', '.join(s.certifications) or '없음'}")
    lines.append(f"- 하고 싶은 일: {s.desired_job or '아직 모름'}")
    lines.append(f"- 일하고 싶은 지역: {s.region or '상관없음'}")
    lines += [f"- {x}" for x in s.extra]
    return "\n".join(lines)


def _ym(value: str) -> str:
    year, month = value.split("-")
    return f"{year}년 {int(month)}월"


def next_user_message(s: Scenario, transcript: list[tuple[str, str]]) -> str:
    """transcript: [(user, agent), ...]. 마지막 에이전트 말에 대한 사용자 답."""
    system = PROMPT.format(facts=facts_text(s), style=s.style)
    # 모델 입장에서는 도우미가 상대(Human), 자기 말이 AI입니다.
    messages: list = [SystemMessage(system)]
    for user, agent in transcript:
        messages += [AIMessage(user), HumanMessage(agent or "(대답 없음)")]
    reply = gateway.get_chat_model("judge").invoke(messages)
    return str(reply.text).strip().strip('"')
