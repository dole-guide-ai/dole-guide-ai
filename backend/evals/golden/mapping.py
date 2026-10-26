"""실제 API 응답을 골든셋 기대값의 데이터 이름으로 바꿉니다 (real.py가 씀).

골든셋은 예전 프론트 타입 이름(DerivedState · RoundCheckRead · ResumeValues · RoundActivity ·
RecognitionFormRead)으로 경로를 적었습니다. 지금 백엔드 응답(ProcedureRead · RoundCheck ·
ResumeRead.data · ApplicationRead.data)을 그 이름으로 옮깁니다. 칸마다 {value, status, …}인
서류 값은 value만 꺼냅니다. 기대값에 쓰인 경로만 옮기고, 나머지는 원래 이름 그대로 둡니다.
"""

from typing import Any

from app.rules.activity_table import load_rules
from app.rules.entry_text import ONLINE_PRESUBMIT_MAX_AGE

YES = "yes"


def _value(node: Any) -> Any:
    """서류 칸({value, status, …})이면 value, 아니면 그대로."""
    if isinstance(node, dict) and "value" in node and "status" in node:
        return node["value"]
    return node


def _unwrap(node: Any) -> Any:
    """서류 데이터 전체를 값만 남긴 모양으로 (칸 → value, 목록 · 묶음은 안으로)."""
    if isinstance(node, dict):
        if "value" in node and "status" in node:
            return _unwrap(node["value"])
        return {k: _unwrap(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_unwrap(item) for item in node]
    return node


def derived(procedure: dict[str, Any], round_check: dict[str, Any]) -> dict[str, Any]:
    age = procedure.get("age_at_separation") or 0
    return {
        **procedure,
        "can_presubmit_online": age < ONLINE_PRESUBMIT_MAX_AGE,
        "current_round": round_check.get("round"),
        "is_attendance_round": round_check.get("attendance_required"),
        "required": round_check.get("required"),
        "required_job_search": round_check.get("required_job_search"),
        "rule_group": round_check.get("rule_group") or procedure.get("recipient_group"),
    }


def round_values(round_check: dict[str, Any]) -> dict[str, Any]:
    return {**round_check, "shortfall": round_check.get("remaining")}


def activities(round_check: dict[str, Any]) -> list[dict[str, Any]]:
    labels = {k.kind: k.label for k in load_rules().kinds}
    out = []
    for a in round_check.get("activities", []):
        out.append(
            {
                **a,
                "date": a.get("activity_date"),
                "category": labels.get(a.get("kind"), a.get("kind")),
                "evidence": {"required": a.get("required_evidence") or []},
            }
        )
    return out


def resume(data: dict[str, Any]) -> dict[str, Any]:
    values = _unwrap(data)
    prefs = values.get("job_preferences") or {}
    occupations = [(o.get("occupation") or {}) for o in prefs.get("desired_occupations") or []]
    regions = [
        r.get("name") if isinstance(r, dict) else r for r in prefs.get("desired_regions") or []
    ]
    education = [{**e, "level": e.get("education_level")} for e in values.get("education") or []]
    return {
        **values,
        "education": education,
        "job_preferences": {
            **prefs,
            "desired_occupations": [o for o in occupations if o],
            "desired_regions": [r for r in regions if r],
        },
        "competencies": {
            **(values.get("competencies") or {}),
            "careers": values.get("careers") or [],
            "certifications": values.get("certifications") or [],
        },
    }


def recognition(application: dict[str, Any]) -> dict[str, Any]:
    data = application.get("data") or {}
    work = data.get("work") or {}
    employment = data.get("employment") or {}
    has_work = _value(work.get("has_work"))
    status = _value(employment.get("status"))
    return {
        **application,
        "work_and_employment": {
            "has_work_or_service": None if has_work is None else has_work == YES,
            "employment_status": status,
        },
    }
