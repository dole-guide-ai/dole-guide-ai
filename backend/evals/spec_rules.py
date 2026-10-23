"""상세기획 평가 시나리오(resume-·round-·form-)를 규칙 함수로 돌리는 연결부입니다 (N-12).

시나리오 JSON의 `rule` 이름으로 아래 함수를 골라 `args`를 넣고,
돌려준 dict를 `expected`와 비교합니다.
JSON에는 날짜를 문자열로 적고, 여기서 규칙 함수가 받는 타입으로 바꿉니다.
규칙 함수가 아직 없으면(다른 기능에서 구현 전) `RuleNotReadyError`를 던져 테스트가 건너뜁니다.
"""

import importlib
from collections.abc import Callable
from datetime import date, datetime
from typing import Any


class RuleNotReadyError(Exception):
    """시나리오가 쓰는 규칙 함수가 아직 없습니다."""


def _rule(module: str, name: str) -> Callable[..., Any]:
    """규칙 모듈·함수가 아직 없을 때만 건너뜁니다.

    모듈 안의 다른 import 오류는 건너뛰지 않고 그대로 실패로 둡니다.
    """
    path = f"app.rules.{module}"
    try:
        loaded = importlib.import_module(path)
    except ModuleNotFoundError as error:
        if error.name != path:
            raise
        raise RuleNotReadyError(path) from error
    found = getattr(loaded, name, None)
    if found is None:
        raise RuleNotReadyError(f"app.rules.{module}.{name}")
    return found


def _activities(rows: list[dict[str, Any]]) -> list[Any]:
    activity_input = _rule("application", "ActivityInput")
    return [
        activity_input(
            activity_id=row.get("activity_id", f"a{index}"),
            activity_date=date.fromisoformat(row["date"]),
            category=row.get("category", "job_search"),
            kind=row.get("kind", "job_application"),
            route=row.get("route"),
            org_name=row.get("org_name"),
            planned=row.get("planned", False),
        )
        for index, row in enumerate(rows, start=1)
    ]


def _form_activities(args: dict[str, Any]) -> dict[str, Any]:
    result = _rule("application", "build_form_activities")(
        _activities(args["activities"]),
        date.fromisoformat(args["period_start"]),
        date.fromisoformat(args["period_end"]),
    )
    required, required_job = _rule("application", "required_activities")(
        args.get("group", "general"), args.get("round", 4)
    )
    counted = len(result.job_search) + len(result.other)
    return {
        "job_search": [row["company_name"] for row in result.job_search],
        "other": [row["details"] for row in result.other],
        "excluded": [(row["company_name"], row["reason"]) for row in result.excluded],
        "counted": counted,
        "shortfall": max(required - counted, 0),
        "shortfall_job_search": max(required_job - len(result.job_search), 0),
    }


def _submit_mode(args: dict[str, Any]) -> dict[str, Any]:
    group, round_no = args.get("group"), args.get("round")
    attendance = (
        _rule("periods", "is_attendance_round")(group, round_no)
        if group and round_no
        else args["attendance_required"]
    )
    mode = _rule("application", "submit_mode")(
        datetime.fromisoformat(args["now"]),
        date.fromisoformat(args["recognition_date"]),
        attendance,
    )
    return {"attendance_required": attendance, "submit_mode": mode}


def _checklist(args: dict[str, Any]) -> dict[str, Any]:
    blocking, warnings = _rule("application", "checklist")(
        args["data"],
        args.get("job_search_rows", []),
        counted=args.get("counted", 0),
        required=args.get("required", 0),
        evidence_missing=args.get("evidence_missing", 0),
    )
    locked = _rule("application", "locked_reason")(args["data"])
    return {
        "blocking": [item["key"] for item in blocking],
        "warnings": [item["key"] for item in warnings],
        "locked_reason": locked,
        "can_submit": _rule("application", "can_submit")(
            args.get("submit_mode", "send"), blocking, locked
        ),
    }


def _recommend(args: dict[str, Any]) -> dict[str, Any]:
    picks = _rule("recommend", "recommend_activities")(
        shortfall=args["shortfall"],
        shortfall_job_search=args["shortfall_job_search"],
        group=args.get("group", "general"),
        round_no=args.get("round", 4),
        lectures_used=args.get("lectures_used", 0),
        desired_occupation=args.get("desired_occupation"),
    )
    result: dict[str, Any] = {"keys": [pick.candidate.key for pick in picks]}
    if "recognition_date" in args:
        result["deadline_text"] = _rule("recommend", "deadline_text")(
            date.fromisoformat(args["recognition_date"]),
            [date.fromisoformat(day) for day in args.get("busy_dates", [])],
        )
    return result


RULES: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "form_activities": _form_activities,
    "submit_mode": _submit_mode,
    "checklist": _checklist,
    "recommend": _recommend,
}


def run_rule(name: str, args: dict[str, Any]) -> dict[str, Any]:
    return RULES[name](args)
