"""모델이 뽑은 이력서 사실(ResumeFacts)을 칸 쓰기(FieldWrite)로 바꿉니다. LLM·DB 없음.

모델은 이력서 스키마에 맞춘 값을 넘깁니다. 선택 칸(학력·졸업 여부)은 스키마의 선택지 중 하나로,
기존 항목을 고치면 그 항목의 item_id로 넘깁니다(말을 알아듣는 일은 모델이 합니다).
여기서는 날짜 계산(오늘 기준 "작년 3월" → YYYY-MM), 새 항목 id 만들기, 맞지 않는 값 거절만 합니다.
다시 물을 것은 사용자에게 그대로 보여도 되는 문장(asks)으로, 코드 사정(없는 item_id 등)은
diagnostics로 따로 둡니다. diagnostics는 로그에만 남기고 모델·사용자에게 보내지 않습니다.
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
# 사용자에게 다시 물을 때 쓰는 문장(말하기 모델이 그대로 옮김)
ASK_DATE = "'{expr}'이(가) 몇 년 몇 월인지 알려 주세요."
ASK_WHICH_CAREER = "어느 회사에서 일한 내용인지 회사 이름을 알려 주세요."
ASK_WHICH_SCHOOL = "어느 학교 학력인지 학교 이름을 알려 주세요."
ASK_DUTIES = "{company}에서 하신 일을 다룬 물건·장비나 맡은 범위로 조금 더 알려 주세요."
ASK_BAD_DATE = "자격증 취득일 '{expr}'은(는) 없는 날짜예요. 다시 알려 주세요."


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
    # 사용자에게 다시 물을 문장(ASK_*). 말하기 모델이 그대로 옮깁니다.
    asks: list[str] = field(default_factory=list)
    # 코드 사정(모델이 준 item_id가 없음 등). 로그에만 남기고 모델·사용자에게 보내지 않습니다.
    diagnostics: list[str] = field(default_factory=list)
    # 스키마 선택지 밖이라 저장하지 않은 칸("경로: 고를 수 있는 값")
    rejected: list[str] = field(default_factory=list)


def plan_writes(
    data: ResumeData,
    facts: ResumeFacts,
    today: date,
    separation_date: date,
    *,
    asking: tuple[str, ...] = (),
) -> FactPlan:
    """같은 회사·학교·자격증·직종을 다시 말하면 그 항목을 고칩니다(rules/resume/items).

    `asking`은 지금 답을 기다리는 칸 경로입니다. 회사·학교 이름 없이 기간·하던 일만 말하면
    지금 묻는 항목의 답으로 보고 그 항목에 씁니다("언제부터 다니셨어요?" → "작년 3월부터요").
    """
    plan = FactPlan()
    picker = ItemPicker(data)
    targets = _asked_items(asking)
    for fact in facts.careers:
        _career(plan, picker, fact, today, separation_date, targets.get("careers"))
    for fact in facts.education:
        _education(plan, picker, fact, today, separation_date, targets.get("education"))
    for fact in facts.certifications:
        _certification(plan, picker, fact, today, separation_date)
    for name in facts.desired_occupations:
        _desired_occupation(plan, picker, name)
    if facts.no_certifications and not data.certifications:
        plan.writes.append(not_applicable(CERTIFICATIONS_STATUS))
    if facts.desired_regions:
        regions = [{"code": None, "name": n} for n in facts.desired_regions[:MAX_PICKS]]
        plan.writes.append(said("/job_preferences/desired_regions", regions))
    return plan


def _asked_items(paths: tuple[str, ...]) -> dict[str, str]:
    """지금 묻는 칸 경로(/careers/c1/end_date) → {섹션: item_id}."""
    found: dict[str, str] = {}
    for path in paths:
        parts = path.strip("/").split("/")
        if len(parts) >= 2 and parts[0] in ("careers", "education"):
            found.setdefault(parts[0], parts[1])
    return found


def _dated(path: str, expr: str, result: DateResult, today: date) -> FieldWrite:
    form_field = date_field(expr, result, today)
    return FieldWrite(path=path, **form_field.model_dump(mode="json", exclude={"answered_on"}))


def _career(
    plan: FactPlan,
    picker: ItemPicker,
    fact: CareerFact,
    today: date,
    separation_date: date,
    asked: str | None = None,
) -> None:
    if not fact.item_id and not fact.company_name:
        # 회사 이름 없이 기간·직급·하던 일만 오면 기존 경력에 덧붙이는 말입니다. 지금 묻는 경력이
        # 있으면 그 경력으로, 없으면 추측하지 않고 회사 이름을 다시 묻습니다.
        if asked is None:
            plan.diagnostics.append("career without company or item_id")
            plan.asks.append(ASK_WHICH_CAREER)
            return
        fact = fact.model_copy(update={"item_id": asked})
    item_id, is_new = _picked(plan, picker, "careers", fact.item_id, (fact.company_name,), "경력")
    if item_id is None:
        return
    if fact.main_duties and len(re.sub(r"\s", "", fact.main_duties)) < DUTY_MIN_CHARS:
        plan.asks.append(ASK_DUTIES.format(company=fact.company_name or "그 회사"))
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
            plan.asks.append(ASK_DATE.format(expr=expr))
            continue
        writes.append(_dated(f"{base}/{key}", expr, result, today))
    # 새 항목인데 확정한 값이 하나도 없으면 빈 경력을 만들지 않습니다("재작년 겨울부터").
    if is_new and not writes:
        return
    plan.writes.extend(writes)


def _education(
    plan: FactPlan,
    picker: ItemPicker,
    fact: EducationFact,
    today: date,
    separation_date: date,
    asked: str | None = None,
) -> None:
    if asked and not fact.item_id and not (fact.school_name or fact.education_level):
        fact = fact.model_copy(update={"item_id": asked})
    values = (fact.school_name, fact.education_level)
    item_id, is_new = _picked(plan, picker, "education", fact.item_id, values, "학력")
    if item_id is None:
        return
    if is_new and picker.data.education and fact.education_level is None:
        # 다른 학교 이름·연도만 오면 기존 학력에 덧붙이는 말인지 새 학력인지 알 수 없습니다.
        plan.diagnostics.append("education item ambiguous")
        plan.asks.append(ASK_WHICH_SCHOOL)
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
            plan.asks.append(ASK_DATE.format(expr=expr))
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


def _certification(
    plan: FactPlan,
    picker: ItemPicker,
    fact: CertificationFact,
    today: date,
    separation_date: date,
) -> None:
    values = (fact.certificate_name,)
    item_id, _ = _picked(plan, picker, "certifications", fact.item_id, values, "자격증")
    if item_id is None:
        return
    base = f"/certifications/{item_id}"
    plan.writes.append(said(f"{base}/certificate_name", fact.certificate_name))
    if fact.issuing_organization:
        plan.writes.append(said(f"{base}/issuing_organization", fact.issuing_organization))
    if fact.acquired:
        _acquired(plan, f"{base}/acquired_date", fact.acquired, today, separation_date)


def _acquired(plan: FactPlan, path: str, expr: str, today: date, separation_date: date) -> None:
    """취득일. 서류처럼 쓴 날짜("2011.05.20")는 그대로 쓰고, 말로 한 날짜("작년 12월")는
    경력·학력과 같은 계산(dates.normalize_date)으로 연-월을 정해 바꾼 표시·근거를 남깁니다."""
    if m := ACQUIRED.search(expr):
        if (value := _acquired_value(m)) is None:
            plan.asks.append(ASK_BAD_DATE.format(expr=expr))
        else:
            plan.writes.append(said(path, value))
        return
    result = normalize_date(expr, today, separation_date)
    if result.ask:
        plan.asks.append(ASK_DATE.format(expr=expr))
    else:
        plan.writes.append(_dated(path, expr, result, today))


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
        plan.diagnostics.append(f"unknown {section} item_id")
    return pick.item_id, pick.is_new


# ── 대기 칸의 답 → 칸 쓰기 ─────────────────────────────

DATE_SUFFIXES = ("/start_date", "/end_date")
ACQUIRED_SUFFIX = "/acquired_date"


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
        if path.endswith(ACQUIRED_SUFFIX) and isinstance(item, str):
            _acquired(plan, path, item, today, separation_date)
        elif path.endswith(DATE_SUFFIXES) and isinstance(item, str):
            result = normalize_date(item, today, separation_date)
            if result.ask:
                plan.asks.append(ASK_DATE.format(expr=item))
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
