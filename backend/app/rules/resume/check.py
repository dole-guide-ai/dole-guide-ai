"""이력서 값 정리·검사·완성도 (상세기획 2-1.4~2-1.6).

꼭 묻는 항목은 제목·학력·희망 조건·경력·자격면허 다섯 가지이고(REQUIRED_SECTIONS),
다섯 개가 다 차고 확인 필요가 없어야 저장할 수 있습니다.
"""

import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from app.rules.resume.dates import career_months, months, ym
from app.rules.resume.fields import (
    GPA_SCALE_SUFFIX,
    GPA_SUFFIX,
    REGIONS_PATH,
    as_list,
    confirmed,
    education_rank,
    form_fields,
    is_filled,
    no_check,
    occupation_name,
    suggested,
)
from app.rules.work24_codes import code_done, code_settled, said_name
from app.schemas.common import FieldSource, FieldStatus, FormField
from app.schemas.forms.resume import (
    Career,
    Certification,
    DesiredOccupation,
    Education,
    EducationLevel,
    EmploymentStatus,
    ExperienceType,
    GpaScale,
    JobPreferences,
    ResumeData,
    required_fields,
)
from app.schemas.resume import Completeness

MAX_PICKS = 3  # 희망 직종·지역은 고용24에서 3개까지
OVERLAP_MONTHS = 3
REQUIRED_SECTIONS = ("resume_title", "education", "job_preferences", "careers", "certifications")
# 꼭 묻는 항목의 화면 이름(패널 제목과 같음). 대화의 "지금 상황"에 남은 항목을 쓸 때 씁니다.
SECTION_LABELS = {
    "resume_title": "이력서 제목",
    "education": "학력사항",
    "job_preferences": "희망조건",
    "careers": "경력사항",
    "certifications": "보유 자격면허",
}


# ── 자동 값 ─────────────────────────────────────────────


def derive_resume_values(data: ResumeData, separation_date: date) -> ResumeData:
    """재직여부·최종학력·희망 직종 경력을 정합니다. 이미 찬 칸은 그대로 둡니다."""
    data = data.model_copy(deep=True)
    separation = (separation_date.year, separation_date.month)

    for c in data.careers:
        end = ym(c.end_date.value)
        if end and not is_filled(c.employment_status) and end <= separation:
            c.employment_status = confirmed(EmploymentStatus.LEFT.value)

    if not any(is_filled(e.is_highest_education) for e in data.education):
        levels = [e for e in data.education if is_filled(e.education_level)]
        if len(levels) == 1:
            levels[0].is_highest_education = confirmed(True)
        elif levels:
            top = max(levels, key=lambda e: education_rank(e.education_level.value))
            top.is_highest_education = suggested(True, "가장 높은 학력")

    for d in data.job_preferences.desired_occupations:
        name = occupation_name(d.occupation)
        if not name or is_filled(d.experience_type):
            continue
        # 고른 공식 이름이나 말한 이름(said)이 경력의 직종과 같으면 같은 직종입니다.
        names = {name, said_name(d.occupation.value)}
        same = [c for c in data.careers if occupation_name(c.occupation) in names]
        if same:
            years, rest = divmod(career_months(same), 12)
            note = f"같은 직종 경력 합계 {years}년 {rest}개월"
            d.experience_type = suggested(ExperienceType.EXPERIENCED.value, note)
            d.experience_years = suggested(years, note)
            d.experience_months = suggested(rest, note)
        elif data.careers_status.status == FieldStatus.NOT_APPLICABLE:
            d.experience_type = suggested(ExperienceType.NEW.value, "경력 없음")
    return data


# ── 검사 ────────────────────────────────────────────────


@dataclass(frozen=True)
class ResumeIssue:
    # period_order · future_date · separation_mismatch · career_overlap · too_many · conflict
    code: str
    path: str


def check_resume(data: ResumeData, separation_date: date, today: date) -> list[ResumeIssue]:
    """일관성 검사. 막지 않고 대화에서 다시 물을 칸을 알려 주는 데 씁니다."""
    issues: list[ResumeIssue] = []
    now = (today.year, today.month)
    for name, items in (("careers", data.careers), ("education", data.education)):
        for it in items:
            start, end = ym(it.start_date.value), ym(it.end_date.value)
            if start and end and start > end:
                issues.append(ResumeIssue("period_order", f"/{name}/{it.item_id}/start_date"))
            if end and end > now:
                issues.append(ResumeIssue("future_date", f"/{name}/{it.item_id}/end_date"))

    latest = latest_career(data.careers)
    if latest and ym(latest.end_date.value) != (separation_date.year, separation_date.month):
        issues.append(ResumeIssue("separation_mismatch", f"/careers/{latest.item_id}/end_date"))

    spans = [(c, ym(c.start_date.value), ym(c.end_date.value)) for c in data.careers]
    spans = [(c, s, e) for c, s, e in spans if s and e]
    for i, (_, a_start, a_end) in enumerate(spans):
        for b, b_start, b_end in spans[i + 1 :]:
            overlap = min(months(a_end), months(b_end)) - max(months(a_start), months(b_start)) + 1
            if overlap >= OVERLAP_MONTHS:
                issues.append(ResumeIssue("career_overlap", f"/careers/{b.item_id}"))

    prefs = data.job_preferences
    if len(prefs.desired_occupations) > MAX_PICKS:
        issues.append(ResumeIssue("too_many", "/job_preferences/desired_occupations"))
    if len(as_list(prefs.desired_regions)) > MAX_PICKS:
        issues.append(ResumeIssue("too_many", REGIONS_PATH))

    issues += [
        ResumeIssue("conflict", p) for p, f in form_fields(data) if f.status == FieldStatus.CONFLICT
    ]
    return issues


def latest_career(careers: list[Career]) -> Career | None:
    dated = [c for c in careers if ym(c.end_date.value)]
    return max(dated, key=lambda c: ym(c.end_date.value)) if dated else None


# ── 완성도 · 저장 ───────────────────────────────────────


# 대학 이상이면 고용24에서 전공·학점/총점을 받습니다. 전공은 꼭 채우고, 학점은 빈칸으로도
# 저장할 수 있지만 고용24 입력 때 필요합니다(2-1.8).
COLLEGE_FIELDS = ("major", "gpa_scale", "gpa")
COLLEGE_REQUIRED_FOR_SAVE = ("major",)


# 학점 만점(총점)은 고용24 드롭다운 값이라 목록 값으로 저장하고, 학점은 0 ~ 만점 범위로 봅니다.
GPA_SCALE_ERROR = "학점 만점은 " + "·".join(s.value for s in GpaScale) + "점 중 하나예요"
_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")  # 부호까지 읽어 "-1"을 1로 받지 않음


def gpa_scale_value(raw: Any) -> str | None:
    """말하거나 입력한 만점(4.5, "4.5점", "4.50", "100점 만점") → 고용24 총점 값. 없으면 None."""
    number = _number(raw)
    return next((s.value for s in GpaScale if float(s.value) == number), None)


def gpa_value(raw: Any, scale: Any) -> tuple[str | None, str | None]:
    """학점 → (저장할 값, 문제). 숫자이고 0 ~ 만점(만점을 알면) 사이여야 합니다."""
    number = _number(raw)
    if number is None:
        return None, "학점은 3.8처럼 숫자로 적어 주세요"
    top = gpa_scale_value(scale)
    if number < 0 or (top is not None and number > float(top)):
        return None, f"학점은 0~{top}점 사이로 적어 주세요" if top else "학점은 0점 이상이에요"
    return f"{number:g}", None


def current_scale(data: ResumeData, gpa_path: str, sent: Any = None) -> Any:
    """학점과 함께 보낸 만점, 없으면 이력서에 이미 적힌 만점(같은 학력 항목)."""
    if sent not in (None, ""):
        return sent
    scale_path = gpa_path.removesuffix(GPA_SUFFIX) + GPA_SCALE_SUFFIX
    return dict(form_fields(data)).get(scale_path, FormField()).value


def _number(raw: Any) -> float | None:
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int | float):
        return float(raw)
    match = _NUMBER.search(str(raw or ""))
    return float(match.group()) if match else None


def is_college(e: Education) -> bool:
    return education_rank(e.education_level.value) >= education_rank(EducationLevel.COLLEGE)


def education_done(e: Education) -> bool:
    """스키마의 꼭 채울 칸이 다 찼는지. 대학 이상이면 전공도(학점은 빈칸 저장 허용)."""
    names = [*required_fields(Education), *(COLLEGE_REQUIRED_FOR_SAVE if is_college(e) else ())]
    major_settled = not is_college(e) or code_settled("major", e.major_code.value)
    return all(is_filled(getattr(e, n)) for n in names) and major_settled


def required_paths(data: ResumeData) -> list[str]:
    """이 이력서에서 고용24에 꼭 넣어야 하는 칸 경로(★). 대학 이상 학력의 전공·학점처럼
    값에 따라 생기는 칸도 넣습니다. 화면은 이 목록으로 ★와 칸 표시를 정합니다."""
    paths = [f"/{n}" for n in required_fields(ResumeData)]
    groups = (
        ("/education", data.education, Education),
        ("/careers", data.careers, Career),
        ("/certifications", data.certifications, Certification),
    )
    for base, items, model in groups:
        for item in items:
            names = [*required_fields(model)]
            if model is Education and is_college(item):
                names += COLLEGE_FIELDS
            paths += [f"{base}/{item.item_id}/{n}" for n in names]
    paths += [f"/job_preferences/{n}" for n in required_fields(JobPreferences)]
    return paths


def saved_before_separation(saved_on: date | None, separation_date: date) -> bool:
    """이직일 전에 저장한 이력서인지 (1장 1.2 `outdated`)."""
    return saved_on is not None and saved_on <= separation_date


def old_careers_pending(data: ResumeData) -> bool:
    """예전 이력서의 경력만 있고 그 뒤 경력을 아직 묻지 않았는지 (1장 1.9 ④, 질문 4).

    새로 더한 경력은 시작일부터 새로 받으므로 시작일 출처로 봅니다. 예전 경력의 회사명만
    고쳐서는 확인이 끝나지 않습니다.
    """
    return (
        data.careers_status.status == FieldStatus.MISSING
        and bool(data.careers)
        and all(c.start_date.source == FieldSource.SEED for c in data.careers)
    )


def occupation_done(d: DesiredOccupation) -> bool:
    """희망 직종 하나가 끝났는지: 고용24 공통코드를 골랐거나 이름만 적기로 했고, 경력여부가 있음."""
    return (
        is_filled(d.occupation) and code_done(d.occupation.value) and is_filled(d.experience_type)
    )


def unpicked_regions(prefs: JobPreferences) -> list[dict[str, Any]]:
    """아직 공통코드 후보를 고르지 않은 희망 지역."""
    return [r for r in as_list(prefs.desired_regions) if not code_done(r)]


def section_done(data: ResumeData, *, outdated: bool = False) -> dict[str, bool]:
    """꼭 묻는 다섯 항목(REQUIRED_SECTIONS)이 끝났는지. 확인 필요가 남으면 끝나지 않은 것.

    대화의 질문 목록(rules/resume/steps)도 같은 함수(occupation_done·unpicked_regions)로 남은
    칸을 찾아 묻습니다. 여기 조건을 더하면 그 칸을 묻는 질문도 같이 있어야 합니다
    (tests/unit/test_resume_steps.py의 판정·질문 일치 테스트가 확인).
    """
    prefs = data.job_preferences
    occupations_done = bool(prefs.desired_occupations) and all(
        occupation_done(d) for d in prefs.desired_occupations
    )
    na = FieldStatus.NOT_APPLICABLE
    return {
        "resume_title": is_filled(data.resume_title) and no_check(data.resume_title),
        "education": bool(data.education)
        and all(education_done(e) for e in data.education)
        and any(is_filled(e.is_highest_education) for e in data.education)
        and no_check(data.education),
        "job_preferences": occupations_done
        and all(
            is_filled(f)
            for f in (
                prefs.desired_regions,
                prefs.desired_salary,
                prefs.employment_contract_type,
                prefs.military_alternative,
            )
        )
        and not unpicked_regions(prefs)
        and no_check(prefs),
        "careers": (
            data.careers_status.status == na
            or (
                bool(data.careers)
                and all(
                    all(is_filled(getattr(c, n)) for n in required_fields(Career))
                    for c in data.careers
                )
            )
        )
        and no_check(data.careers)
        and not (outdated and old_careers_pending(data)),
        "certifications": (
            data.certifications_status.status == na
            or (
                bool(data.certifications)
                and all(
                    is_filled(c.certificate_name)
                    and code_settled("license", c.certificate_code.value)
                    for c in data.certifications
                )
            )
        )
        and no_check(data.certifications),
    }


def resume_completeness(data: ResumeData, *, outdated: bool = False) -> Completeness:
    """꼭 묻는 5개 중 끝난 항목 수 (2-1.2). 확인 필요가 남은 항목은 세지 않습니다.

    `outdated`(이직일 전에 저장한 예전 이력서)면 그 뒤 경력을 묻기 전까지 경력을 세지 않습니다.
    """
    sections = section_done(data, outdated=outdated)
    return Completeness(filled=sum(sections.values()), sections=sections)


def can_save_resume(data: ResumeData, *, outdated: bool = False) -> bool:
    """5/5이고 확인 필요가 하나도 없을 때만 저장할 수 있습니다 (2-1.6)."""
    filled = resume_completeness(data, outdated=outdated).filled
    return filled == len(REQUIRED_SECTIONS) and no_check(data)
