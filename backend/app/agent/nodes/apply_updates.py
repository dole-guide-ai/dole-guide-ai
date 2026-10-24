from copy import deepcopy
from typing import Any

from app.agent.schemas import AgentOutput, AgentState
from app.rules import situation


def apply_updates(state: AgentState) -> AgentState:
    """모델이 뽑은 값을 서류에 합치고, 활동이 바뀌었으면 회차 점검을 다시 계산합니다.

    상태값(회차·절차 날짜)은 바꾸지 않습니다. 쓰는 곳은 이력서와 활동 목록뿐입니다.
    """
    output = state["output"]
    data = deepcopy(state["data"])
    period = state["situation"]["derived"]["period"]
    for activity in output.activities:
        data["activities"].append(situation.complete_activity(activity.model_dump(), period))
    _merge_resume(data["resume"], output)
    context = dict(state["situation"])
    if output.activities and context["derived"]["current_round"]:
        context["round"] = situation.check_round(context["derived"], data["activities"])
    return {"data": data, "situation": context}


def _merge_resume(resume: dict[str, Any], output: AgentOutput) -> None:
    careers = resume["competencies"]["careers"]
    for draft in output.careers:
        values = {k: v for k, v in draft.model_dump().items() if v is not None}
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
