"""대화 한 턴에서 AI에게 넘길 '지금 상황'을 계산하는 규칙 함수입니다.

수급자 유형·이번 회차·필요 활동 수·인정 건수처럼 틀리면 안 되는 값은 여기서 정하고,
AI는 이 결과를 설명만 합니다(설계 초안 결정 ②). DB·LLM을 모르는 순수 함수입니다.

회차 점검은 팀 공용 `rounds.check_round`(같은 날 1건·기간 밖·한도·허용 종류), 활동 종류 이름과
증빙은 활동 규칙 표(`activity_table`)를 그대로 씁니다. 여기서는 대화 상태값(dict)을 그 입력·출력
모양으로 바꾸기만 합니다.
"""

from datetime import date, timedelta
from typing import Any

from app.rules import periods, rounds
from app.rules.activity_table import load_rules, required_evidence
from app.rules.application import ActivityInput
from app.schemas.activities import ActivityCategory
from app.schemas.rounds import WarningId

# 시연·골든셋 데이터의 옛 종류 이름 → 활동 규칙 표의 종류
LEGACY_KINDS = {"job_search": "job_application"}
DEFAULT_KIND = "job_application"
# 증빙 표에 없는 경로
UNKNOWN_EVIDENCE = ["필요한 증빙은 관할 고용센터에 확인"]


def _day(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def derive(state: dict[str, Any]) -> dict[str, Any]:
    """상태값에서 화면의 DerivedState와 같은 모양의 계산값을 만듭니다."""
    today = date.fromisoformat(state["demo_today"])
    is_repeat = state.get("recipient_type") == "repeat"
    group = periods.recipient_group(
        state["age_at_separation"], state.get("has_disability", False), is_repeat
    )
    # 반복수급자도 출석 회차는 일반을 따릅니다.
    rule_group = "general" if group == "repeat" else group
    recognition = _day(state.get("next_recognition_date"))
    current_round = (
        state.get("completed_rounds", 0) + 1
        if state.get("stage") == "recognition" and recognition
        else None
    )
    required = required_job_search = interval_days = None
    period = None
    if current_round:
        last = _day(state.get("last_recognition_date"))
        applied = _day(state.get("eligibility_applied_date"))
        # 1차 대상기간은 대기기간(신청일부터 7일) 다음 날부터입니다.
        start = last + timedelta(days=1) if last else (applied or today) + timedelta(days=7)
        period = {"start": start.isoformat(), "end": recognition.isoformat()}
        # 필요 건수는 활동 규칙 표(data/rules/activities.json). 표에 없는 유형은 None.
        # "N일마다 1건" 규칙(일반 8차부터 7일마다 구직활동, 반복수급자 14일마다)은
        # 기간을 나눠 셉니다.
        if row := load_rules().required_row(group, current_round):
            required, required_job_search = row.total, row.job_search
            if row.weekly_job_search or row.every_days:
                interval_days = row.every_days or rounds.DAYS_PER_WEEK
                required = len(rounds.period_slices(start, recognition, interval_days))
                required_job_search = required if row.weekly_job_search else 0
    return {
        "rule_group": rule_group,
        "group": group,
        "current_round": current_round,
        "d_day": (recognition - today).days if recognition else None,
        "period": period,
        "is_attendance_round": bool(current_round)
        and periods.is_attendance_round(rule_group, current_round),
        "required": required,
        "required_job_search": required_job_search,
        "interval_days": interval_days,  # N일마다 1건 규칙일 때만 (7 또는 14)
        "can_presubmit_online": state["age_at_separation"] < 65,
    }


def _to_input(index: int, activity: dict[str, Any]) -> ActivityInput:
    kind = LEGACY_KINDS.get(activity.get("kind") or "", activity.get("kind") or DEFAULT_KIND)
    rule = load_rules().kind(kind)
    return ActivityInput(
        activity_id=str(index),
        activity_date=date.fromisoformat(activity["date"]),
        category=rule.category if rule else ActivityCategory.NON_JOB_SEARCH,
        kind=kind,
        route=activity.get("route"),
        org_name=activity.get("org_name"),
        job_title=activity.get("job_title"),
    )


def check_round(
    state: dict[str, Any], derived: dict[str, Any], activities: list[dict[str, Any]]
) -> tuple[dict[str, Any], list[str]]:
    """이번 회차 점검 요약과, 활동마다의 상태(counted·same_day·out_of_period 등)를 돌려줍니다."""
    period = derived["period"]
    result = rounds.check_round(
        round_no=derived["current_round"],
        group=derived["group"],
        period_start=date.fromisoformat(period["start"]),
        period_end=date.fromisoformat(period["end"]),
        standard_period=True,
        activities=[_to_input(i, a) for i, a in enumerate(activities)],
        history=[],
        today=date.fromisoformat(state["demo_today"]),
    )
    statuses = {check.activity_id: check.status for check in result.activities}
    summary = {
        "round": derived["current_round"],
        "required": result.required,
        "required_job_search": result.required_job_search,
        "counted": result.counted,
        "counted_job_search": result.counted_job_search,
        # 필요 건수를 모르는 유형(규칙 표에 없음)은 부족 건수도 None입니다.
        "shortfall": None if result.required is None else result.remaining,
        "same_day_messages": [w.message for w in result.warnings if w.id == WarningId.SAME_DAY],
    }
    return summary, [str(statuses.get(str(i), "")) for i in range(len(activities))]


def complete_activity(activity: dict[str, Any]) -> dict[str, Any]:
    """AI가 뽑은 활동(날짜·종류·경로·기관)에 종류 이름과 필요 증빙을 채웁니다."""
    kind = activity.get("kind") or DEFAULT_KIND
    rule = load_rules().kind(kind)
    evidence = required_evidence(activity.get("route"))
    return {
        **activity,
        "kind": kind,
        "category": rule.label if rule else "확인 필요",
        "evidence": {"required": list(evidence) if evidence is not None else UNKNOWN_EVIDENCE},
    }
