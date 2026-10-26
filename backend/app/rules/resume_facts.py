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
CERTIFICATIONS_STATUS = "/certifications_status"
COMPETENCIES_STATUS = "/competencies_status"
# 고등학교·대학 졸업은 보통 2월입니다. 연도만 말하면 2월로 두고 확인 필요로 남깁니다.
GRADUATION_MONTH = 2
# 입학은 보통 3월입니다. 연도만 말하면 3월로 두고 확인 필요로 남깁니다.
ENTRANCE_MONTH = 3
# 이보다 짧은 "하던 일"(예: "포장")은 이력서로 쓰기에 부족해 구체적으로 다시 묻습니다.
DUTY_MIN_CHARS = 8
# 직급 칸에 들어온 직종 이름(생산직·사무직 등). 모델이 칸을 헷갈려도 코드가 직종으로 옮깁니다.
OCCUPATION_LIKE = re.compile(r"(생산|사무|기술|영업|서비스|판매|관리|운전|경비|청소|조리|현장)직$")


class CareerFact(BaseModel):
    company_name: str | None = None
    start: str | None = Field(None, description="입사 시점 표현 그대로(예: 작년 3월, 2004년 3월)")
    end: str | None = Field(None, description="퇴사 시점 표현 그대로(예: 올해 9월, 지금까지)")
    position: str | None = Field(
        None,
        description="직급·직책(반장, 과장). 없었다고 하면 '없음'. "
        "생산직·사무직 같은 직종은 occupation에 넣는다",
    )
    occupation: str | None = Field(None, description="직종(생산직, 물류 사무, 경비)")
    main_duties: str | None = Field(None, description="주로 한 일")


class EducationFact(BaseModel):
    school_name: str | None = None
    education_level: str | None = Field(None, description="고등학교·대학교(2,3년)·대학교(4년) 등")
    graduation_status: str | None = Field(None, description="졸업·중퇴·재학 등")
    start: str | None = Field(None, description="입학 시점 표현 그대로(예: 1987년)")
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
    no_certifications: bool = Field(False, description="자격증·면허가 없다고 했으면 true")


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
        path = f"/job_preferences/desired_occupations/o{i}/occupation"
        plan.writes.append(_said(path, _occupation(name)))
    if facts.no_certifications and not data.certifications:
        plan.writes.append(not_applicable(CERTIFICATIONS_STATUS))
    if facts.desired_regions:
        regions = [{"code": None, "name": n} for n in facts.desired_regions[:MAX_REGIONS]]
        plan.writes.append(_said("/job_preferences/desired_regions", regions))
    return plan


def _fix_position(fact: CareerFact) -> CareerFact:
    """직급 칸에 "생산직" 같은 직종이 오면 직종 칸으로 옮깁니다(직종이 이미 있으면 직급만 비움)."""
    if not (fact.position and OCCUPATION_LIKE.search(fact.position.strip())):
        return fact
    return fact.model_copy(
        update={"position": None, "occupation": fact.occupation or fact.position.strip()}
    )


def not_applicable(path: str) -> FieldWrite:
    """섹션을 "없어요"로 저장합니다(예: 자격증 없음 → /certifications_status)."""
    return FieldWrite(path=path, status=FieldStatus.NOT_APPLICABLE, source=FieldSource.USER_ANSWER)


def _occupation(name: str) -> dict[str, Any]:
    """직종은 이름만 받습니다. 고용24 직종 코드는 아직 고르지 않은 상태(name_only)입니다."""
    return {"code": None, "name": name, "status": OccupationStatus.NAME_ONLY.value}


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
    fact = _fix_position(fact)
    item_id, is_new = _target_career(data, fact)
    if fact.main_duties and len(re.sub(r"\s", "", fact.main_duties)) < DUTY_MIN_CHARS:
        plan.asks.append(
            f"하던 일 '{fact.main_duties}'이(가) 짧아요. 다룬 물건·장비, 맡은 범위, 처리량처럼 "
            "구체적으로 한 가지만 더 물어보면 좋아요"
        )
    base = f"/careers/{item_id}"
    writes: list[FieldWrite] = []
    for key in ("company_name", "position", "main_duties"):
        if value := getattr(fact, key):
            writes.append(_said(f"{base}/{key}", value))
    if fact.occupation:
        writes.append(_said(f"{base}/occupation", _occupation(fact.occupation)))
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
    for key, expr, month, label in (
        ("start_date", fact.start, ENTRANCE_MONTH, "입학"),
        ("end_date", fact.end, GRADUATION_MONTH, "졸업"),
    ):
        if not expr:
            continue
        result = normalize_date(expr, today, separation_date)
        if result.ask and (year := re.search(r"(\d{4})\s*년?", expr)):
            value = f"{year[1]}-{month:02d}"
            note = (
                f"'{expr}' → {value} ({label}은 보통 {month}월이라 {month}월로 두었어요. 확인 필요)"
            )
            result = DateResult(value, transformed=True, note=note)
        if result.ask:
            plan.asks.append(f"{label} 시점 '{expr}'을(를) 다시 물어야 해요")
        else:
            writes.append(_dated(f"{base}/{key}", expr, result, today))
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
