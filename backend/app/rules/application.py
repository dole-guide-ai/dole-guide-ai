"""실업인정 신청서를 만드는 규칙 함수.

구직활동 10칸은 저장하지 않고, 그 회차 대상기간의 인정 활동에서 매번 만듭니다.
같은 날 활동이 여러 건이면 1건만 인정하고 나머지는 참고로 따로 둡니다(설계 6.4).
지난 회차에 답한 통지 방법·실업크레딧은 이번 회차가 비어 있으면 불러와 보여 줍니다.
제출 버튼 상태(submit_mode)와 제출 전 확인(checklist)도 여기서 정합니다 (F-26).
DB와 LLM을 쓰지 않는 순수 함수라 서비스와 대화 턴이 같이 씁니다.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from app.schemas.activities import ActivityRoute, ApplyMethod, SearchMethod
from app.schemas.common import FieldStatus
from app.schemas.rounds import ActivityStatus

JOB_SEARCH = "job_search"
NON_JOB_SEARCH = "non_job_search"

# 2-2 경로(route) → 고용24 응모 방식 (상세기획 2-3.4, 2026-10-19 결정).
# 회사 홈페이지·취업 사이트는 고용24 선택지에 없어 `기타`로 둡니다.
_APPLY_METHOD = {
    ActivityRoute.WORK24: ApplyMethod.WORK24,
    ActivityRoute.EMAIL: ApplyMethod.EMAIL,
    ActivityRoute.MAIL: ApplyMethod.MAIL,
    ActivityRoute.FAX: ApplyMethod.FAX,
    ActivityRoute.VISIT: ApplyMethod.VISIT,
    ActivityRoute.INTERVIEW: ApplyMethod.VISIT,
    ActivityRoute.COMPANY_SITE: ApplyMethod.OTHER,
    ActivityRoute.PORTAL: ApplyMethod.OTHER,
}
# 고용24로 지원했으면 공고도 고용24에서 찾은 것이라 구직 방법을 정할 수 있습니다.
# 그 밖에는 대화로 물어서 채웁니다 (F-25).
_SEARCH_METHOD = {ActivityRoute.WORK24: SearchMethod.WORK24}

# 지난 회차 답을 불러오는 칸 (2-3.3: 지난 답을 보여 주고 유지할지만 묻는 칸)
_CARRIED_FIELDS = ("notification_method",)
_CARRIED_GROUPS = ("credit",)


def apply_method_from_route(route: str | None) -> str | None:
    method = _APPLY_METHOD.get(route or "")  # StrEnum 키는 같은 글자로 찾을 수 있습니다
    return method.value if method else None


def search_method_from_route(route: str | None) -> str | None:
    method = _SEARCH_METHOD.get(route or "")
    return method.value if method else None


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
    hours: float | None = None
    source: str = ""
    # 증빙 파일을 하나 이상 연결했는지 (activity_files)
    has_evidence: bool = False


@dataclass
class FormActivities:
    """신청서 재취업 활동정보: 구직활동 줄, 구직 외 활동, 같은 날이라 뺀 활동."""

    job_search: list[dict[str, Any]] = field(default_factory=list)
    other: list[dict[str, Any]] = field(default_factory=list)
    excluded: list[dict[str, Any]] = field(default_factory=list)


# 신청서에 넣지 않고 참고 목록(excluded)에 이유와 함께 두는 계산 결과
_EXCLUDED = (
    ActivityStatus.SAME_DAY,
    ActivityStatus.NOT_ALLOWED,
    ActivityStatus.LIMIT_OVER,
    ActivityStatus.NEEDS_CHECK,
)


def build_form_activities(
    activities: list[ActivityInput], statuses: dict[str, ActivityStatus]
) -> FormActivities:
    """회차 점검(`check_round`) 결과대로 신청서 활동 칸을 만듭니다.

    인정 계산(`counted`)인 활동만 신청서 줄이 되고, 같은 날·불인정·한도 초과·확인 필요는 이유와
    함께 참고 목록에 둡니다. 예정·기간 밖 활동은 넣지 않습니다.
    """
    result = FormActivities()
    for activity in sorted(activities, key=lambda a: a.activity_date):
        status = statuses.get(activity.activity_id)
        if status == ActivityStatus.COUNTED and activity.category == JOB_SEARCH:
            result.job_search.append(_job_search_row(activity))
        elif status == ActivityStatus.COUNTED:
            result.other.append(
                {
                    "activity_id": activity.activity_id,
                    "activity_date": activity.activity_date,
                    "kind": activity.kind,
                    "details": activity.org_name,
                }
            )
        elif status in _EXCLUDED:
            result.excluded.append(
                {
                    "activity_id": activity.activity_id,
                    "reason": status.value,
                    "activity_date": activity.activity_date,
                    "company_name": activity.org_name,
                }
            )
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


def _withdrawn(node: Any) -> bool:
    """내 정보에서 지운 답(F-31). 지난 회차 답을 다시 불러오지 않습니다."""
    return isinstance(node, dict) and node.get("status") == FieldStatus.REJECTED


def carry_previous_answers(data: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any]:
    """이번 회차에 아직 답이 없으면 지난 회차에 답한 통지 방법·실업크레딧을 불러옵니다.

    불러온 칸은 지난 답의 출처(user_answer)와 답한 날(answered_on)을 그대로 둬서, 화면이 "지난번
    답"으로 보여 주고 유지할지만 묻게 합니다. 이번 회차 저장 값은 바꾸지 않습니다(응답에만 반영).
    """
    if not previous:
        return data
    merged = {**data}
    for key in _CARRIED_FIELDS:
        current_node = merged.get(key)
        if (
            _is_empty(current_node)
            and not _withdrawn(current_node)
            and not _is_empty(previous.get(key))
        ):
            merged[key] = previous[key]
    for group in _CARRIED_GROUPS:
        current = {**(merged.get(group) or {})}
        for key, node in (previous.get(group) or {}).items():
            if (
                _is_empty(current.get(key))
                and not _withdrawn(current.get(key))
                and not _is_empty(node)
            ):
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
    remaining: int,
    remaining_job_search: int,
    evidence_missing: int,
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
    if remaining or remaining_job_search:
        parts = [f"필요 활동 {remaining}건 부족"] if remaining else []
        if remaining_job_search:
            parts.append(f"구직활동 {remaining_job_search}건 부족")
        warnings.append({"key": "requirement_met", "text": " · ".join(parts)})
    if evidence_missing:
        warnings.append({"key": "evidence_ok", "text": f"증빙 {evidence_missing}건 없음"})
    return blocking, warnings


def can_submit(mode: str, blocking: list[dict[str, str]], locked: str | None) -> bool:
    """모의 제출·출석 준비 확인을 할 수 있는지. 경고는 막지 않습니다 (설계 3.6)."""
    return mode in (SEND, ATTEND) and not blocking and locked is None
