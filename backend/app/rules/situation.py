"""대화 한 턴에서 AI에게 넘길 '지금 상황'을 계산하는 규칙 함수입니다.

수급자 유형·이번 회차·필요 활동 수·인정 건수처럼 틀리면 안 되는 값은 여기서 정하고,
AI는 이 결과를 설명만 합니다(설계 초안 결정 ②). DB·LLM을 모르는 순수 함수입니다.
"""

from datetime import date, timedelta
from typing import Any

from app.rules import application, periods

OUT_OF_PERIOD = "out_of_period"
COUNTED = "counted"
# 구직활동으로 세는 종류. 시연 데이터는 job_search, AI가 뽑은 활동은 세부 종류를 씁니다.
JOB_SEARCH_KINDS = ("job_search", "job_application", "interview")

# 활동 종류(kind) → 신청서에 보이는 이름
CATEGORY_LABELS = {
    "job_application": "입사지원",
    "interview": "면접",
    "lecture": "취업특강",
    "training": "직업훈련",
    "counseling": "직업상담",
    "job_fair": "채용박람회",
}
# 경로(route) → 제출할 증빙 (상세기획 2-2.4). 고용24 지원은 기록이 남아 증빙이 필요 없습니다.
EVIDENCE_BY_ROUTE: dict[str, list[str]] = {
    "work24": [],
    "step_online": [],
    "company_site": ["채용공고", "지원 완료 화면 캡처(날짜가 보이게)"],
    "portal": ["취업포털 지원 내역 캡처 또는 취업활동증명서"],
    "email": ["채용공고", "보낸 메일 화면 캡처"],
    "interview": ["면접확인서", "명함"],
}
DEFAULT_EVIDENCE = ["지원 사실을 보여 주는 자료(공고·접수증 등)"]


def _day(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def derive(state: dict[str, Any]) -> dict[str, Any]:
    """상태값에서 화면의 DerivedState와 같은 모양의 계산값을 만듭니다."""
    today = date.fromisoformat(state["demo_today"])
    is_repeat = state.get("recipient_type") == "repeat"
    group = periods.recipient_group(
        state["age_at_separation"], state.get("has_disability", False), is_repeat
    )
    # 반복수급자도 회차 규칙은 일반을 따릅니다.
    rule_group = "general" if group == "repeat" else group
    recognition = _day(state.get("next_recognition_date"))
    current_round = (
        state.get("completed_rounds", 0) + 1
        if state.get("stage") == "recognition" and recognition
        else None
    )
    required = required_job_search = None
    period = None
    if current_round:
        required, required_job_search = application.required_activities(group, current_round)
        last = _day(state.get("last_recognition_date"))
        applied = _day(state.get("eligibility_applied_date"))
        # 1차 대상기간은 대기기간(신청일부터 7일) 다음 날부터입니다.
        start = last + timedelta(days=1) if last else (applied or today) + timedelta(days=7)
        period = {"start": start.isoformat(), "end": recognition.isoformat()}
    return {
        "rule_group": rule_group,
        "current_round": current_round,
        "d_day": (recognition - today).days if recognition else None,
        "period": period,
        "is_attendance_round": bool(current_round)
        and periods.is_attendance_round(rule_group, current_round),
        "required": required,
        "required_job_search": required_job_search,
        "can_presubmit_online": state["age_at_separation"] < 65,
    }


def activity_status(activity: dict[str, Any], period: dict[str, str] | None) -> str:
    if not period or not period["start"] <= activity["date"] <= period["end"]:
        return OUT_OF_PERIOD
    return COUNTED


def check_round(derived: dict[str, Any], activities: list[dict[str, Any]]) -> dict[str, Any]:
    """이번 회차 인정 건수와 부족한 건수. 같은 날 활동은 1건만 인정합니다(설계 6.4)."""
    period = derived["period"]
    in_period = [a for a in activities if activity_status(a, period) == COUNTED]
    counted = len({a["date"] for a in in_period})
    job_search = len({a["date"] for a in in_period if a.get("kind") in JOB_SEARCH_KINDS})
    required = derived["required"] or 0
    return {
        "round": derived["current_round"],
        "required": required,
        "required_job_search": derived["required_job_search"] or 0,
        "counted": counted,
        "counted_job_search": job_search,
        "shortfall": max(required - counted, 0),
    }


def complete_activity(activity: dict[str, Any], period: dict[str, str] | None) -> dict[str, Any]:
    """AI가 뽑은 활동(날짜·종류·경로·기관)에 이름·증빙·인정 여부를 채웁니다."""
    kind = activity.get("kind") or "job_application"
    route = activity.get("route")
    return {
        **activity,
        "category": CATEGORY_LABELS.get(kind, "기타"),
        "evidence": {"required": list(EVIDENCE_BY_ROUTE.get(route or "", DEFAULT_EVIDENCE))},
        "status": activity_status(activity, period),
    }
