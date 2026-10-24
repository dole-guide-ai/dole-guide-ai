from copy import deepcopy
from datetime import date
from typing import Any

from app.agent.schemas import AgentOutput, AgentState
from app.core.config import get_settings
from app.rules import situation
from app.rules.dates import normalize_day, normalize_month


def apply_updates(state: AgentState) -> AgentState:
    """모델이 뽑은 값을 서류에 합치고, 활동이 바뀌었으면 회차 점검을 다시 계산합니다.

    상태값(회차·절차 날짜)은 바꾸지 않습니다. 쓰는 곳은 이력서와 활동 목록뿐입니다.
    DATE_PARSING이 code면 모델이 옮긴 날짜 표현을 규칙 코드로 바꾸고, 못 바꾸면 비워 둡니다.
    """
    output = state["output"]
    if get_settings().date_parsing == "code":
        output = _normalize_dates(output, state["state"])
    data = deepcopy(state["data"])
    for activity in output.activities:
        data["activities"].append(situation.complete_activity(activity.model_dump()))
    _merge_resume(data["resume"], output)
    context = dict(state["situation"])
    if output.activities and context["derived"]["current_round"]:
        context["round"], statuses = situation.check_round(
            state["state"], context["derived"], data["activities"]
        )
        # 새로 넣은 활동에만 회차 점검 상태(counted·same_day·out_of_period 등)를 붙입니다.
        new = len(output.activities)
        for activity, status in zip(data["activities"][-new:], statuses[-new:], strict=True):
            activity["status"] = status
    return {"data": data, "situation": context}


def _normalize_dates(output: AgentOutput, procedure: dict[str, Any]) -> AgentOutput:
    """날짜 표현("작년 3월", "지난주 금요일")을 칸 값으로. 날짜를 못 정한 활동은 넣지 않습니다."""
    today = date.fromisoformat(procedure["demo_today"])
    separation = date.fromisoformat(procedure["separation_date"])
    age = procedure.get("age_at_separation")

    def month(expr: str | None, *, year_only: bool = False) -> str | None:
        return normalize_month(expr, today, separation, age, allow_year_only=year_only)

    activities = []
    for activity in output.activities:
        if day := normalize_day(activity.date, today):
            activities.append(activity.model_copy(update={"date": day}))
    careers = [
        c.model_copy(update={"start_date": month(c.start_date), "end_date": month(c.end_date)})
        for c in output.careers
    ]
    certifications = [
        c.model_copy(update={"acquired_date": month(c.acquired_date, year_only=True)})
        for c in output.certifications
    ]
    education = [
        e.model_copy(update={"end_date": month(e.end_date, year_only=True)})
        for e in output.education
    ]
    return output.model_copy(
        update={
            "activities": activities,
            "careers": careers,
            "certifications": certifications,
            "education": education,
        }
    )


def _merge_resume(resume: dict[str, Any], output: AgentOutput) -> None:
    careers = resume["competencies"]["careers"]
    for draft in output.careers:
        values = {k: v for k, v in draft.model_dump().items() if v is not None}
        if not values:
            # 날짜를 못 정해 비운 경력처럼 알게 된 값이 없으면 빈 줄을 만들지 않습니다.
            continue
        target = _find_career(careers, draft.company_name)
        if target is None:
            careers.append({**_empty_career(), **values})
        else:
            target.update(values)
    certifications = resume["competencies"]["certifications"]
    for cert in output.certifications:
        names = [c.get("certificate_name") for c in certifications]
        if cert.certificate_name not in names:
            certifications.append(cert.model_dump())
    for school in output.education:
        resume["education"].append(school.model_dump())
    preferences = resume["job_preferences"]
    for name in output.desired_occupations:
        preferences["desired_occupations"].append({"name": name})
    preferences["desired_regions"].extend(output.desired_regions)


def _find_career(careers: list[dict[str, Any]], company: str | None) -> dict[str, Any] | None:
    """회사 이름이 같으면 그 경력, 이름 없이 말했으면 가장 최근 경력에 합칩니다."""
    if company is None:
        return careers[-1] if careers else None
    return next((c for c in careers if c.get("company_name") == company), None)


def _empty_career() -> dict[str, Any]:
    return dict.fromkeys(
        ("company_name", "start_date", "end_date", "position", "main_duties", "monthly_salary")
    )
