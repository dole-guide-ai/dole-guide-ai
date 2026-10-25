"""모델이 뽑은 이력서 사실(ResumeFacts)을 칸 쓰기(FieldWrite)로 바꿉니다. LLM·DB 없음.

모델은 사용자가 말한 값과 날짜 표현만 넘깁니다. 어느 항목에 쓸지(새 항목·기존 항목), 항목 id,
날짜 변환, 다시 물어야 할 것은 여기서 정합니다(노션 「에이전트 구조 설계」 3단계: 추출 + 코드 적용).
"""

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from pydantic import BaseModel, Field

from app.rules.resume import DateResult, date_field, normalize_date
from app.schemas.common import FieldSource, FieldStatus
from app.schemas.forms.resume import Career, OccupationStatus, ResumeData
from app.schemas.resume import FieldWrite

MAX_REGIONS = 3
# 고등학교·대학 졸업은 보통 2월입니다. 연도만 말하면 2월로 두고 확인 필요로 남깁니다.
GRADUATION_MONTH = 2


class CareerFact(BaseModel):
    company_name: str | None = None
    start: str | None = Field(None, description="입사 시점 표현 그대로(예: 작년 3월, 2004년 3월)")
    end: str | None = Field(None, description="퇴사 시점 표현 그대로(예: 올해 9월, 지금까지)")
    position: str | None = Field(None, description="직급·직책(반장, 과장)")
    main_duties: str | None = Field(None, description="주로 한 일")


class EducationFact(BaseModel):
    school_name: str | None = None
    education_level: str | None = Field(None, description="고등학교·대학교(2,3년)·대학교(4년) 등")
    graduation_status: str | None = Field(None, description="졸업·중퇴·재학 등")
    end: str | None = Field(None, description="졸업 시점 표현 그대로(예: 1990년)")


class CertificationFact(BaseModel):
    certificate_name: str
    acquired: str | None = Field(None, description="취득 시점 표현 그대로(예: 2011년)")


class ResumeFacts(BaseModel):
    """이번 말에서 사용자가 직접 말한 이력서 사실. 말하지 않은 칸은 비웁니다."""

    careers: list[CareerFact] = []
    education: list[EducationFact] = []
    certifications: list[CertificationFact] = []
    desired_occupations: list[str] = Field(default_factory=list, description="희망 직종 이름")
    desired_regions: list[str] = Field(default_factory=list, description="일하고 싶은 지역")


@dataclass
class FactPlan:
    writes: list[FieldWrite] = field(default_factory=list)
    # 확정하지 못해 다시 물어야 할 것(모델에 돌려줌). 값은 넣지 않고 무엇이 모호한지만 씁니다.
    asks: list[str] = field(default_factory=list)


def plan_writes(
    data: ResumeData, facts: ResumeFacts, today: date, separation_date: date
) -> FactPlan:
    plan = FactPlan()
    for fact in facts.careers:
        _career(plan, data, fact, today, separation_date)
    for i, fact in enumerate(facts.education, start=len(data.education) + 1):
        _education(plan, f"e{i}", fact, today, separation_date)
    for i, fact in enumerate(facts.certifications, start=len(data.certifications) + 1):
        _certification(plan, f"q{i}", fact)
    for i, name in enumerate(
        facts.desired_occupations, start=len(data.job_preferences.desired_occupations) + 1
    ):
        value = {"code": None, "name": name, "status": OccupationStatus.NAME_ONLY.value}
        plan.writes.append(_said(f"/job_preferences/desired_occupations/o{i}/occupation", value))
    if facts.desired_regions:
        regions = [{"code": None, "name": n} for n in facts.desired_regions[:MAX_REGIONS]]
        plan.writes.append(_said("/job_preferences/desired_regions", regions))
    return plan


def _said(path: str, value: Any) -> FieldWrite:
    return FieldWrite(
        path=path, value=value, status=FieldStatus.EXTRACTED, source=FieldSource.USER_ANSWER
    )


def _dated(path: str, expr: str, result: DateResult, today: date) -> FieldWrite:
    form_field = date_field(expr, result, today)
    return FieldWrite(path=path, **form_field.model_dump(mode="json", exclude={"answered_on"}))


def _target_career(data: ResumeData, fact: CareerFact) -> tuple[str, bool]:
    """(item_id, 새 항목인지).

    같은 회사가 있으면 그 항목, 회사 없이 말하면 마지막 항목을 고칩니다.
    """
    careers = data.careers
    if fact.company_name:
        name = _norm(fact.company_name)
        for c in careers:
            if name and name in _norm(c.company_name.value):
                return c.item_id, False
    elif careers:
        return careers[-1].item_id, False
    return _new_id(careers, "c"), True


def _career(
    plan: FactPlan, data: ResumeData, fact: CareerFact, today: date, separation_date: date
) -> None:
    item_id, is_new = _target_career(data, fact)
    base = f"/careers/{item_id}"
    writes: list[FieldWrite] = []
    for key in ("company_name", "position", "main_duties"):
        if value := getattr(fact, key):
            writes.append(_said(f"{base}/{key}", value))
    for key, expr in (("start_date", fact.start), ("end_date", fact.end)):
        if not expr:
            continue
        result = normalize_date(expr, today, separation_date)
        if result.ask:
            plan.asks.append(f"경력 {key} '{expr}'은(는) 연·월이 정해지지 않아 다시 물어야 해요")
            continue
        writes.append(_dated(f"{base}/{key}", expr, result, today))
    # 새 항목인데 확정한 값이 하나도 없으면 빈 경력을 만들지 않습니다("재작년 겨울부터").
    if is_new and not writes:
        return
    plan.writes.extend(writes)


def _education(
    plan: FactPlan, item_id: str, fact: EducationFact, today: date, separation_date: date
) -> None:
    base = f"/education/{item_id}"
    writes = [
        _said(f"{base}/{key}", value)
        for key in ("school_name", "education_level", "graduation_status")
        if (value := getattr(fact, key))
    ]
    if fact.end:
        result = normalize_date(fact.end, today, separation_date)
        if result.ask and (year := re.search(r"(\d{4})\s*년?", fact.end)):
            value = f"{year[1]}-{GRADUATION_MONTH:02d}"
            note = f"'{fact.end}' → {value} (졸업은 보통 2월이라 2월로 두었어요. 확인 필요)"
            result = DateResult(value, transformed=True, note=note)
        if result.ask:
            plan.asks.append(f"졸업 시점 '{fact.end}'을(를) 다시 물어야 해요")
        else:
            writes.append(_dated(f"{base}/end_date", fact.end, result, today))
    if writes:
        plan.writes.extend(writes)


def _certification(plan: FactPlan, item_id: str, fact: CertificationFact) -> None:
    base = f"/certifications/{item_id}"
    plan.writes.append(_said(f"{base}/certificate_name", fact.certificate_name))
    if fact.acquired and (m := re.search(r"(\d{4})(?:\s*[-./년]\s*(\d{1,2}))?", fact.acquired)):
        value = f"{m[1]}-{int(m[2]):02d}-01" if m[2] else m[1]
        plan.writes.append(_said(f"{base}/acquired_date", value))


def _new_id(careers: list[Career], prefix: str) -> str:
    used = {c.item_id for c in careers}
    n = len(careers) + 1
    while f"{prefix}{n}" in used:
        n += 1
    return f"{prefix}{n}"


def _norm(value: Any) -> str:
    return re.sub(r"\s|\(주\)|주식회사", "", str(value or ""))
