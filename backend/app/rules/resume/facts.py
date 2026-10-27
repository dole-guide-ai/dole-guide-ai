"""모델이 뽑은 이력서 사실(ResumeFacts)을 칸 쓰기(FieldWrite)로 바꿉니다. LLM·DB 없음.

모델은 이력서 스키마에 맞춘 값을 넘깁니다. 선택 칸(학력·졸업 여부)은 스키마의 선택지 중 하나로,
기존 항목을 고치면 그 항목의 item_id로 넘깁니다(말을 알아듣는 일은 모델이 합니다).
여기서는 날짜 계산(오늘 기준 "작년 3월" → YYYY-MM), 새 항목 id 만들기, 맞지 않는 값 거절만 합니다.
거절한 것은 asks로 모델에 돌려줘 사용자에게 다시 묻게 합니다.
"""

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from pydantic import BaseModel, Field

from app.rules.resume.check import MAX_PICKS
from app.rules.resume.dates import DateResult, date_field, normalize_date
from app.rules.resume.fields import CERTIFICATIONS_STATUS, not_applicable, occupation, said
from app.rules.resume.items import ItemPicker
from app.schemas.forms.resume import EducationLevel, GraduationStatus, ResumeData, choices_of
from app.schemas.resume import FieldWrite

# 고등학교·대학 졸업은 보통 2월입니다. 연도만 말하면 2월로 두고 확인 필요로 남깁니다.
GRADUATION_MONTH = 2
# 입학은 보통 3월입니다. 연도만 말하면 3월로 두고 확인 필요로 남깁니다.
ENTRANCE_MONTH = 3
# 이보다 짧은 "하던 일"(예: "포장")은 이력서로 쓰기에 부족해 구체적으로 다시 묻습니다.
DUTY_MIN_CHARS = 8
ITEM_ID_HINT = "기존 항목을 고치면 진행표·resume_items의 item_id. 새 항목이면 비움"


class CareerFact(BaseModel):
    item_id: str | None = Field(None, description=ITEM_ID_HINT)
    company_name: str | None = None
    start: str | None = Field(None, description="입사 시점 표현 그대로(예: 작년 3월, 2004년 3월)")
    end: str | None = Field(None, description="퇴사 시점 표현 그대로(예: 올해 9월, 지금까지)")
    position: str | None = Field(
        None,
        description="직급·직책(반장, 과장, 대리). 없었다고 하면 '없음'. "
        "생산직·사무직처럼 '~직'으로 끝나는 말은 직급이 아니라 occupation에 넣는다",
    )
    occupation: str | None = Field(None, description="직종(생산직, 물류 사무, 경비)")
    main_duties: str | None = Field(None, description="주로 한 일")


class EducationFact(BaseModel):
    item_id: str | None = Field(None, description=ITEM_ID_HINT)
    school_name: str | None = None
    education_level: EducationLevel | None = Field(
        None,
        description="고용24 학력 선택지 중 하나(예: '고졸' → 고등학교, '전문대' → 대학교(2/3년제))",
    )
    graduation_status: GraduationStatus | None = Field(
        None, description="고용24 졸업 여부 선택지 중 하나(예: '나왔어요' → 졸업)"
    )
    start: str | None = Field(None, description="입학 시점 표현 그대로(예: 1987년)")
    end: str | None = Field(None, description="졸업 시점 표현 그대로(예: 1990년)")


class CertificationFact(BaseModel):
    item_id: str | None = Field(None, description=ITEM_ID_HINT)
    certificate_name: str
    acquired: str | None = Field(None, description="취득 시점 표현 그대로(예: 2011년, 2011.05.20)")
    issuing_organization: str | None = Field(
        None, description="발급 기관(예: 한국산업인력공단). 말하거나 서류에 있을 때만"
    )


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
    # 스키마 선택지 밖이라 저장하지 않은 칸("경로: 고를 수 있는 값")
    rejected: list[str] = field(default_factory=list)


def plan_writes(
    data: ResumeData, facts: ResumeFacts, today: date, separation_date: date
) -> FactPlan:
    """같은 회사·학교·자격증·직종을 다시 말하면 그 항목을 고칩니다(rules/resume/items)."""
    plan = FactPlan()
    picker = ItemPicker(data)
    for fact in facts.careers:
        _career(plan, picker, fact, today, separation_date)
    for fact in facts.education:
        _education(plan, picker, fact, today, separation_date)
    for fact in facts.certifications:
        _certification(plan, picker, fact)
    for name in facts.desired_occupations:
        _desired_occupation(plan, picker, name)
    if facts.no_certifications and not data.certifications:
        plan.writes.append(not_applicable(CERTIFICATIONS_STATUS))
    if facts.desired_regions:
        regions = [{"code": None, "name": n} for n in facts.desired_regions[:MAX_PICKS]]
        plan.writes.append(said("/job_preferences/desired_regions", regions))
    return plan


def _dated(path: str, expr: str, result: DateResult, today: date) -> FieldWrite:
    form_field = date_field(expr, result, today)
    return FieldWrite(path=path, **form_field.model_dump(mode="json", exclude={"answered_on"}))


def _career(
    plan: FactPlan, picker: ItemPicker, fact: CareerFact, today: date, separation_date: date
) -> None:
    if not fact.item_id and not fact.company_name:
        # 회사 이름 없이 직급·하던 일만 오면 기존 경력에 덧붙이는 말입니다. 어느 경력인지 모르면
        # 추측하지 않고 모델에 item_id를 다시 넣게 합니다.
        plan.asks.append("어느 경력인지 item_id를 넣어 다시 저장하세요(resume_items 참고)")
        return
    item_id, is_new = _picked(plan, picker, "careers", fact.item_id, (fact.company_name,), "경력")
    if item_id is None:
        return
    if fact.main_duties and len(re.sub(r"\s", "", fact.main_duties)) < DUTY_MIN_CHARS:
        plan.asks.append(
            f"하던 일 '{fact.main_duties}'이(가) 짧아요. 다룬 물건·장비, 맡은 범위, 처리량처럼 "
            "구체적으로 한 가지만 더 물어보면 좋아요"
        )
    base = f"/careers/{item_id}"
    writes: list[FieldWrite] = []
    for key in ("company_name", "position", "main_duties"):
        if value := getattr(fact, key):
            writes.append(said(f"{base}/{key}", value))
    if fact.occupation:
        writes.append(said(f"{base}/occupation", occupation(fact.occupation)))
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
    plan: FactPlan, picker: ItemPicker, fact: EducationFact, today: date, separation_date: date
) -> None:
    values = (fact.school_name, fact.education_level)
    item_id, is_new = _picked(plan, picker, "education", fact.item_id, values, "학력")
    if item_id is None:
        return
    if is_new and picker.data.education and fact.education_level is None:
        # 다른 학교 이름·연도만 오면 기존 학력에 덧붙이는 말인지 새 학력인지 알 수 없습니다.
        plan.asks.append("어느 학력인지 item_id를 넣어 다시 저장하세요(resume_items 참고)")
        return
    base = f"/education/{item_id}"
    values = {
        "school_name": fact.school_name,
        "education_level": fact.education_level,
        "graduation_status": fact.graduation_status,
    }
    writes = [said(f"{base}/{key}", value) for key, value in values.items() if value]
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
    plan.writes.extend(writes)


# 자격증 취득일 "2011년", "2011.05", "2011.05.20"
ACQUIRED = re.compile(r"(\d{4})(?:\s*[-./년]\s*(\d{1,2})(?:\s*[-./월]\s*(\d{1,2}))?)?")


def _acquired_value(m: re.Match[str]) -> str | None:
    """취득일 값. 말한(서류에 있는) 만큼만 씁니다: 연도, 연-월, 일까지 있으면 연-월-일.

    안 말한 "1일"을 지어 넣지 않습니다. 없는 달·날("2011.13", "2011.02.30")이나
    숫자가 더 붙으면("2011.05.201") None(다시 물음).
    """
    year, month, day = m[1], m[2], m[3]
    if m.string[m.end() :].lstrip()[:1].isdigit():
        return None
    if not month:
        return year
    try:
        value = date(int(year), int(month), int(day or 1))
    except ValueError:
        return None
    return value.isoformat() if day else value.isoformat()[:7]


def _certification(plan: FactPlan, picker: ItemPicker, fact: CertificationFact) -> None:
    values = (fact.certificate_name,)
    item_id, _ = _picked(plan, picker, "certifications", fact.item_id, values, "자격증")
    if item_id is None:
        return
    base = f"/certifications/{item_id}"
    plan.writes.append(said(f"{base}/certificate_name", fact.certificate_name))
    if fact.issuing_organization:
        plan.writes.append(said(f"{base}/issuing_organization", fact.issuing_organization))
    if fact.acquired and (m := ACQUIRED.search(fact.acquired)):
        if (value := _acquired_value(m)) is None:
            plan.asks.append(f"자격증 취득일 '{fact.acquired}'은(는) 없는 날짜라 다시 물어야 해요")
        else:
            plan.writes.append(said(f"{base}/acquired_date", value))


def _desired_occupation(plan: FactPlan, picker: ItemPicker, name: str) -> None:
    pick = picker.pick("desired_occupations", values=(name,), limit=MAX_PICKS)
    if pick.full:
        plan.rejected.append(f"희망 직종 '{name}': 고용24는 {MAX_PICKS}개까지라 넣지 않음")
    elif pick.is_new:  # 이미 적은 직종을 다시 말했으면 쓸 것이 없습니다.
        path = f"/job_preferences/desired_occupations/{pick.item_id}/occupation"
        plan.writes.append(said(path, occupation(name)))


def _picked(
    plan: FactPlan,
    picker: ItemPicker,
    section: str,
    item_id: str | None,
    values: tuple[Any, ...],
    label: str,
) -> tuple[str | None, bool]:
    """(쓸 item_id, 새 항목인지). 모델이 준 item_id가 없는 항목이면 asks에 남기고 None."""
    pick = picker.pick(section, item_id=item_id, values=values)
    if pick.item_id is None:
        plan.asks.append(f"{label} item_id '{item_id}'가 없어요. resume_items의 id를 쓰세요")
    return pick.item_id, pick.is_new


# ── 대기 칸의 답 → 칸 쓰기 ─────────────────────────────

DATE_SUFFIXES = ("/start_date", "/end_date")


def answer_writes(
    paths: tuple[str, ...], value: Any, today: date, separation_date: date
) -> FactPlan:
    """읽기 모델이 돌려준 대기 칸의 값을 칸 쓰기로 바꿉니다.

    - 경로가 하나면 값 그대로, 기간(시작·끝)이면 {"start", "end"}, 여러 칸이면 {칸 이름: 값}.
    - 날짜는 연·월로 바꾸고 못 바꾸면 asks에, 선택 칸의 선택지 밖 값은 rejected에 둡니다.
    """
    plan = FactPlan()
    # 섹션 경로(/careers 같은 반복 항목 묶음)와 *_status는 값 하나를 쓰는 칸이 아닙니다.
    # 그런 단계의 답은 facts(항목 단위)로 받으므로 여기서는 건너뜁니다.
    paths = tuple(p for p in paths if p.count("/") > 1 and not p.endswith("_status"))
    for path, item in _pair_values(paths, value):
        if item in (None, ""):
            continue
        if path.endswith(DATE_SUFFIXES) and isinstance(item, str):
            result = normalize_date(item, today, separation_date)
            if result.ask:
                plan.asks.append(f"'{item}'은(는) 연·월이 정해지지 않아 다시 물어야 해요")
            else:
                plan.writes.append(_dated(path, item, result, today))
        elif choices_of(path) and item not in choices_of(path):
            # 고를 값은 질문 카드 버튼에 있으므로 목록을 되풀이하지 않습니다.
            plan.rejected.append(f"{path}: 정해진 선택지 밖의 값이라 저장하지 않음")
        else:
            plan.writes.append(said(path, _shaped(path, item)))
    return plan


def _pair_values(paths: tuple[str, ...], value: Any) -> list[tuple[str, Any]]:
    if value in (None, "", [], {}):
        return []
    if len(paths) == 1:
        return [(paths[0], value)]
    if not isinstance(value, dict):
        return []
    period = all(p.endswith(DATE_SUFFIXES) for p in paths)
    return [
        (
            p,
            value.get(
                p.rsplit("/", 1)[-1].removesuffix("_date") if period else p.rsplit("/", 1)[-1]
            ),
        )
        for p in paths
    ]


def _shaped(path: str, item: Any) -> Any:
    """직종·희망 지역은 스키마 모양({name}·[{name}])으로 맞춥니다."""
    if path.endswith("/occupation") and isinstance(item, str):
        return occupation(item)
    if path.endswith("/desired_regions") and isinstance(item, list):
        return [{"code": None, "name": str(n)} for n in item][:MAX_PICKS]
    return item
