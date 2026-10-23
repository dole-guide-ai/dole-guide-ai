"""실업인정 신청서를 만드는 규칙 함수입니다 (설계 6.7·7절, 상세기획 2-3.2·2-3.4).

구직활동 10칸은 저장하지 않고, 그 회차 대상기간의 인정 활동에서 매번 만듭니다.
같은 날 활동이 여러 건이면 1건만 인정하고 나머지는 참고로 따로 둡니다(설계 6.4).
지난 회차에 답한 통지 방법·실업크레딧은 이번 회차가 비어 있으면 불러와 보여 줍니다.
제출 버튼 상태(submit_mode)와 제출 전 확인(checklist)도 여기서 정합니다 (F-26).
DB와 LLM을 쓰지 않는 순수 함수라 서비스와 대화 턴이 같이 씁니다.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

JOB_SEARCH = "job_search"
NON_JOB_SEARCH = "non_job_search"

# 2-2 경로(route) → 고용24 응모 방식 (상세기획 2-3.4, 2026-10-19 결정).
# 회사 홈페이지·취업 사이트는 고용24 선택지에 없어 `기타`로 둡니다.
_APPLY_METHOD = {
    "work24": "고용24(워크넷)",
    "email": "전자메일",
    "mail": "우편",
    "fax": "FAX",
    "visit": "직접방문",
    "interview": "직접방문",
    "company_site": "기타",
    "job_site": "기타",
}
# 고용24로 지원했으면 공고도 고용24에서 찾은 것이라 구직 방법을 정할 수 있습니다.
# 그 밖에는 대화로 물어서 채웁니다 (F-25).
_SEARCH_METHOD = {"work24": "고용24(워크넷)"}

# 지난 회차 답을 불러오는 칸 (2-3.3: 지난 답을 보여 주고 유지할지만 묻는 칸)
_CARRIED_FIELDS = ("notification_method",)
_CARRIED_GROUPS = ("credit",)


def apply_method_from_route(route: str | None) -> str | None:
    return _APPLY_METHOD.get(route or "")


def search_method_from_route(route: str | None) -> str | None:
    return _SEARCH_METHOD.get(route or "")


@dataclass(frozen=True)
class ActivityInput:
    """규칙 함수가 읽는 활동 한 건 (activities 테이블 값)."""

    activity_id: str
    activity_date: date
    category: str
    kind: str
    route: str | None = None
    org_name: str | None = None
    job_title: str | None = None
    search_method: str | None = None
    apply_method: str | None = None
    contact_dept: str | None = None
    result: str | None = None
    planned: bool = False


@dataclass
class FormActivities:
    """신청서 재취업 활동정보: 구직활동 줄, 구직 외 활동, 같은 날이라 뺀 활동."""

    job_search: list[dict[str, Any]] = field(default_factory=list)
    other: list[dict[str, Any]] = field(default_factory=list)
    excluded: list[dict[str, Any]] = field(default_factory=list)


def _representative_rank(activity: ActivityInput) -> tuple[bool, bool]:
    """같은 날 활동 중 대표로 인정할 순서: 구직활동 먼저, 그다음 증빙이 필요 없는 고용24 경로."""
    return (activity.category != JOB_SEARCH, activity.route != "work24")


def build_form_activities(
    activities: list[ActivityInput], period_start: date, period_end: date
) -> FormActivities:
    """대상기간 안의 실제 활동으로 신청서 활동 칸을 만듭니다. 예정 활동은 넣지 않습니다.

    같은 날 활동은 1건만 인정합니다(설계 6.4).
    대표는 구직활동·고용24 경로(증빙 불필요)를 먼저 고르고,
    같으면 먼저 기록한 것입니다. 나머지는 `same_day`로 참고 목록에 둡니다.
    """
    result = FormActivities()
    by_day: dict[date, list[ActivityInput]] = {}
    for activity in activities:
        if activity.planned or not period_start <= activity.activity_date <= period_end:
            continue
        by_day.setdefault(activity.activity_date, []).append(activity)
    for day in sorted(by_day):
        first, *rest = sorted(by_day[day], key=_representative_rank)
        if first.category == JOB_SEARCH:
            result.job_search.append(_job_search_row(first))
        else:
            result.other.append(
                {
                    "activity_id": first.activity_id,
                    "activity_date": first.activity_date,
                    "kind": first.kind,
                    "details": first.org_name,
                }
            )
        result.excluded += [
            {
                "activity_id": other.activity_id,
                "reason": "same_day",
                "activity_date": other.activity_date,
                "company_name": other.org_name,
            }
            for other in rest
        ]
    return result


def _job_search_row(activity: ActivityInput) -> dict[str, Any]:
    return {
        "activity_id": activity.activity_id,
        "activity_date": activity.activity_date,
        "company_name": activity.org_name,
        "recruitment_contact": activity.contact_dept,
        "recruitment_occupation": activity.job_title,
        "salary_level": None,
        "job_search_method": activity.search_method or search_method_from_route(activity.route),
        "application_method": activity.apply_method or apply_method_from_route(activity.route),
        "activity_result": activity.result,
        # 응답 칸은 아니지만 증빙 필요 여부(F-26)를 판단하려고 경로를 같이 둡니다.
        "route": activity.route,
    }


def _is_empty(node: Any) -> bool:
    return not isinstance(node, dict) or node.get("value") in (None, "", [])


def carry_previous_answers(data: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any]:
    """이번 회차에 아직 답이 없으면 지난 회차에 답한 통지 방법·실업크레딧을 불러옵니다.

    불러온 칸은 지난 답의 출처(user_answer)와 답한 날(answered_on)을 그대로 둬서, 화면이 "지난번
    답"으로 보여 주고 유지할지만 묻게 합니다. 이번 회차 저장 값은 바꾸지 않습니다(응답에만 반영).
    """
    if not previous:
        return data
    merged = {**data}
    for key in _CARRIED_FIELDS:
        if _is_empty(merged.get(key)) and not _is_empty(previous.get(key)):
            merged[key] = previous[key]
    for group in _CARRIED_GROUPS:
        current = {**(merged.get(group) or {})}
        for key, node in (previous.get(group) or {}).items():
            if _is_empty(current.get(key)) and not _is_empty(node):
                current[key] = node
        merged[group] = current
    return merged


def locked_reason(data: dict[str, Any]) -> str | None:
    """취업·개인 사업이나 산재 휴업급여가 있으면 신청서를 잠급니다 (설계 6.7)."""
    employment = (data.get("employment") or {}).get("status") or {}
    if employment.get("value") in ("employed", "self_employed"):
        return "employed"
    accident = (data.get("industrial_accident") or {}).get("receiving") or {}
    if accident.get("value") == "yes":
        return "industrial_accident"
    return None


# 일반 수급자 규칙(4차부터 4주 2회)을 따르는 그룹. 반복수급자도 일반 규칙입니다.
GENERAL_RULE_GROUPS = ("general", "repeat")


def required_activities(recipient_group: str, round_no: int) -> tuple[int, int]:
    """회차별 필요 재취업활동 (전체 건수, 그중 구직활동 건수) (설계 6.2).

    1차는 실업인정 교육이라 활동 1건으로 셉니다. 4차부터 일반 수급자는 4주 2회(구직활동 1회 포함),
    60세 이상·장애인은 4주 1회(자율)입니다. 반복수급자는 일반 규칙을 따릅니다.
    8차 이후 일반의 "1주 1회 구직활동"은 회차 점검(F-18)이 주 단위로 셉니다.
    """
    if round_no <= 3 or recipient_group not in GENERAL_RULE_GROUPS:
        return (1, 0)
    return (2, 1)


# ── 제출 방식 · 체크리스트 (F-26, 상세기획 2-3.6) ─────────────────────────────

SEND_DEADLINE_HOUR = 17  # 인정일 당일 인터넷 제출 마감
VISIT_DEADLINE_HOUR = 18  # 인정일 당일 센터 방문 신청 마감

ATTEND = "attend"
PREVIEW = "preview"
SEND = "send"
VISIT_TODAY = "visit_today"
CHANGE = "change"


def submit_mode(now: datetime, recognition_date: date, attendance_required: bool) -> str:
    """지금 시각(KST)에 맞는 제출 버튼 상태 5종 (설계 3.6).

    - attend: 출석 회차 → 출석 준비 확인 (인터넷으로 내지 않음)
    - preview: 인정일 전 → 미리 보기·임시저장 (제출 불가)
    - send: 인정일 당일 17시 전 → 모의 제출
    - visit_today: 인정일 당일 17~18시 → 오늘 센터 방문 안내
    - change: 인정일이 지남(당일 18시 이후 포함) → 변경 신청 안내
    """
    today = now.date()
    if today > recognition_date or (today == recognition_date and now.hour >= VISIT_DEADLINE_HOUR):
        return CHANGE
    if attendance_required:
        return ATTEND
    if today < recognition_date:
        return PREVIEW
    return SEND if now.hour < SEND_DEADLINE_HOUR else VISIT_TODAY


_JOB_SEARCH_REQUIRED = (
    "company_name",
    "recruitment_contact",
    "recruitment_occupation",
    "job_search_method",
    "application_method",
    "activity_result",
)


def _answered(node: Any) -> bool:
    return not _is_empty(node)


def checklist(
    data: dict[str, Any],
    job_search: list[dict[str, Any]],
    counted: int,
    required: int,
    evidence_missing: int,
    required_job_search: int = 0,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """제출을 막는 항목(blocking)과 경고(warnings)를 나눕니다 (상세기획 2-3.6).

    막는 항목: 본인 답변(근로·취업·산재), 구직활동 필수 칸, 통지 방법, 다음 출석일까지 활동.
    경고(제출은 가능): 실업크레딧 미답변, 필요 활동 부족(전체 건수 또는 그중 구직활동), 증빙 없음.
    """
    blocking: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    self_answers = (
        (data.get("work") or {}).get("has_work"),
        (data.get("employment") or {}).get("status"),
        (data.get("industrial_accident") or {}).get("receiving"),
    )
    if not all(_answered(node) for node in self_answers):
        blocking.append({"key": "self_answers", "text": "근로·취업·산재 본인 답변"})
    if any(not row.get(key) for row in job_search for key in _JOB_SEARCH_REQUIRED):
        blocking.append({"key": "job_search_fields", "text": "구직활동 필수 칸"})
    if not _answered(data.get("notification_method")):
        blocking.append({"key": "notification", "text": "지급 결정 통지 방법"})
    if not _answered(data.get("next_plan")):
        blocking.append({"key": "next_activity", "text": "다음 출석일까지 활동"})

    credit = (data.get("credit") or {}).get("application")
    if not _answered(credit):
        warnings.append({"key": "unemployment_credit", "text": "실업크레딧 답"})
    short_by = max(required - counted, 0)
    short_job_search = max(required_job_search - len(job_search), 0)
    if short_by or short_job_search:
        parts = [f"필요 활동 {short_by}건 부족"] if short_by else []
        if short_job_search:
            parts.append(f"구직활동 {short_job_search}건 부족")
        warnings.append({"key": "requirement_met", "text": " · ".join(parts)})
    if evidence_missing:
        warnings.append({"key": "evidence_ok", "text": f"증빙 {evidence_missing}건 없음"})
    return blocking, warnings


def needs_evidence(route: str | None) -> bool:
    """고용24 지원은 고용24에 기록이 남아 증빙이 필요 없고, 그 밖의 경로는 필요합니다 (2-2.4)."""
    return route != "work24"


def can_submit(mode: str, blocking: list[dict[str, str]], locked: str | None) -> bool:
    """모의 제출·출석 준비 확인을 할 수 있는지. 경고는 막지 않습니다 (설계 3.6)."""
    return mode in (SEND, ATTEND) and not blocking and locked is None
