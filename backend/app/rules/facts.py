"""규칙 계산 결과를 사람이 읽는 '사실 문장'으로 바꿉니다 (실험 B).

AI가 숫자·날짜를 직접 말하게 하지 않고, 이 문장을 그대로 쓰게 합니다. 문장마다 출처를 달아
답의 근거 줄로 씁니다. DB·LLM을 모르는 순수 함수입니다.
"""

from collections import Counter
from datetime import date, datetime, time
from typing import Any

from app.rules import application

WEEKDAYS = "월화수목금토일"
CITE_ROUNDS = "고용노동부 1350 상담 답변(재취업활동 의무 횟수)"
CITE_EVIDENCE = "고용노동부 1350 상담 답변(재취업활동 인정·증빙)"
CITE_ONLINE = "고용노동부 1350 FAQ(인터넷 실업인정)"
CITE_WORK24 = "고용24 실업급여 안내"


def _md(value: str) -> str:
    day = date.fromisoformat(value)
    return f"{day.month}월 {day.day}일({WEEKDAYS[day.weekday()]})"


def build_facts(
    state: dict[str, Any], derived: dict[str, Any], round_check: dict[str, Any] | None,
    activities: list[dict[str, Any]],
) -> list[dict[str, str]]:  # fmt: skip
    """지금 상황에서 사용자에게 말해도 되는 사실 문장 목록 [{text, cite}]."""
    facts: list[dict[str, str]] = []
    age = state["age_at_separation"]
    if derived["current_round"] is None:
        if derived["can_presubmit_online"]:
            text = (
                f"이직 당시 만 {age}세라 인터넷 사전제출 대상이 될 수 있어요(나이는 이직일 기준). "
                "다른 조건도 맞아야 하고, 제출한 뒤에도 고용센터 방문이 필요해요."
            )
        else:
            text = (
                f"이직 당시 만 {age}세(만 65세 이상)라 인터넷 사전제출 대상이 아니에요. "
                "관할 고용센터에 방문해 수급자격을 신청해요."
            )
        facts.append({"text": text, "cite": CITE_WORK24})
        return facts

    n = derived["current_round"]
    end = derived["period"]["end"]
    facts.append({"text": f"이번 {n}차 실업인정일은 {_md(end)}이에요.", "cite": CITE_ROUNDS})
    if round_check and round_check["required"] is None:
        text = (
            "이번 회차에 필요한 활동 수는 여기서 계산할 수 없어요. 관할 고용센터에 확인해 주세요."
        )
        facts.append({"text": text, "cite": CITE_ROUNDS})
    elif round_check:
        need = f"이번 회차에 필요한 활동은 {round_check['required']}건"
        if round_check["required_job_search"]:
            need += f"(그중 구직활동 {round_check['required_job_search']}건)"
        counted, short = round_check["counted"], round_check["shortfall"]
        need += f"이고, 지금 인정된 활동은 {counted}건이에요."
        need += f" {short}건 더 해야 해요." if short else " 필요한 건수는 채웠어요."
        facts.append({"text": need, "cite": CITE_ROUNDS})
    period = derived["period"]
    same_day = Counter(
        a["date"] for a in activities if period["start"] <= a["date"] <= period["end"]
    )
    for day, count in sorted(same_day.items()):
        if count > 1:
            facts.append({
                "text": f"{_md(day)}에 한 활동 {count}건은 같은 날이라 1건만 인정돼요. "
                "더 할 활동은 다른 날 해야 해요.",
                "cite": CITE_EVIDENCE,
            })  # fmt: skip
    if derived["is_attendance_round"]:
        text = f"이번 {n}차는 고용센터에 직접 출석하는 회차예요. 인터넷으로 보내지 않아요."
        facts.append({"text": text, "cite": CITE_ROUNDS})
    else:
        facts.append({"text": _submit_text(state, end), "cite": CITE_ONLINE})
    return facts


def _submit_text(state: dict[str, Any], recognition: str) -> str:
    hour, minute = (int(part) for part in state.get("demo_time", "10:00").split(":"))
    now = datetime.combine(date.fromisoformat(state["demo_today"]), time(hour, minute))
    mode = application.submit_mode(now, date.fromisoformat(recognition), False)
    texts = {
        application.PREVIEW: (
            f"신청서는 인정일인 {_md(recognition)} 0시부터 17시까지 인터넷으로 보낼 수 있어요."
        ),
        application.SEND: "오늘이 인정일이라 17시까지 인터넷으로 보낼 수 있어요. 지금 보내면 돼요.",
        application.VISIT_TODAY: (
            "오늘 17시가 지나 인터넷으로는 보낼 수 없어요. "
            "18시까지 고용센터에 방문해 신청해야 해요."
        ),
        application.CHANGE: "인정일이 지났어요. 고용센터에 실업인정일 변경을 신청해야 해요.",
    }
    return texts[mode]
