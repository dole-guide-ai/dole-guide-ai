"""이력서 칸을 정리하고 검사하고, 다음에 물을 질문을 고르는 규칙 함수입니다 (상세기획 2-1.3~2-1.6).

AI는 말에서 값을 뽑고 문장만 만들고, 날짜 변환·완성도·다음 질문·저장 가능 여부는 여기서 정합니다.
"확인 필요"는 AI·코드가 바꾼 값(extracted + transformed)이나 서로 다른 값(conflict)입니다.
날짜는 칸에 YYYY-MM 문자열로 둡니다.
"""

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.schemas.common import (
    EvidenceKind,
    FieldEvidence,
    FieldSource,
    FieldStatus,
    FormField,
)
from app.schemas.forms.resume import Career, Education, OccupationStatus, ResumeData
from app.schemas.resume import Completeness

MAX_PICKS = 3  # 희망 직종·지역은 고용24에서 3개까지
OVERLAP_MONTHS = 3
RECENT_CAREERS = 3  # 경력이 많으면 최근 3건만 주요 직무를 묻습니다 (2-1.8)

_EDUCATION_RANK = [
    "무학",
    "초등학교",
    "중학교",
    "고등학교",
    "대학교(2/3년제)",
    "대학교(4년제)",
    "대학원(석사)",
    "대학원(박사)",
]


# ── 칸 상태 ──────────────────────────────────────────────


def is_filled(f: FormField) -> bool:
    return f.status not in (FieldStatus.MISSING, FieldStatus.REJECTED) and f.value not in (
        None,
        "",
        [],
    )


def needs_check(f: FormField) -> bool:
    """확인 필요 칩 (2-0.6): 바꾼 값이거나 서로 다른 값."""
    return f.status == FieldStatus.CONFLICT or (f.status == FieldStatus.EXTRACTED and f.transformed)


def form_fields(node: Any, path: str = "") -> list[tuple[str, FormField]]:
    """모든 칸을 `/careers/c1/company_name` 경로와 함께 펼칩니다."""
    if isinstance(node, FormField):
        return [(path, node)]
    if isinstance(node, list):
        return [p for item in node for p in form_fields(item, f"{path}/{item.item_id}")]
    out: list[tuple[str, FormField]] = []
    for name in type(node).model_fields:
        if name != "item_id":
            out += form_fields(getattr(node, name), f"{path}/{name}")
    return out


def occupation_value(f: FormField) -> dict[str, Any]:
    return f.value if isinstance(f.value, dict) else {}


def occupation_name(f: FormField) -> str | None:
    """직종 칸 값 {code, name, status}에서 이름. 모양이 다르면 None."""
    return occupation_value(f).get("name")


def _as_list(f: FormField) -> list[Any]:
    return f.value if isinstance(f.value, list) else []


def _confirmed(value: Any) -> FormField:
    return FormField(value=value, status=FieldStatus.CONFIRMED, source=FieldSource.AUTO)


def _suggested(value: Any, note: str) -> FormField:
    return FormField(
        value=value,
        status=FieldStatus.EXTRACTED,
        source=FieldSource.AUTO,
        transformed=True,
        evidence=FieldEvidence(kind=EvidenceKind.COMPUTED, note=note),
    )


# ── 날짜 ────────────────────────────────────────────────


def _ym(value: Any) -> tuple[int, int] | None:
    m = re.fullmatch(r"(\d{4})-(\d{2})", str(value or ""))
    return (int(m[1]), int(m[2])) if m and _is_month(int(m[2])) else None


def _is_month(month: int) -> bool:
    return 1 <= month <= 12


def _months(ym: tuple[int, int]) -> int:
    return ym[0] * 12 + ym[1]


def _fmt(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


@dataclass(frozen=True)
class DateResult:
    """날짜 표현을 정리한 결과. ask면 값을 확정하지 말고 다시 물어야 합니다."""

    value: str | None
    transformed: bool = False
    note: str | None = None
    ask: bool = False
    year_range: tuple[int, int] | None = None


_RELATIVE_YEARS = {"재작년": -2, "작년": -1, "지난해": -1, "올해": 0, "금년": 0}
_VAGUE = re.compile(r"봄|여름|가을|겨울|초|중순|말|쯤|무렵")


def normalize_date(
    expr: str, today: date, separation_date: date, age_at_separation: int | None = None
) -> DateResult:
    """사용자의 날짜 표현을 YYYY-MM으로 바꿉니다 (2-1.4 날짜 표현)."""
    text = expr.strip()
    if m := re.search(r"(\d{4})\s*(?:년|[-./])\s*(\d{1,2})", text):
        if not _is_month(int(m[2])):
            return DateResult(None, ask=True)
        return DateResult(_fmt(int(m[1]), int(m[2])))
    if re.search(r"지금까지|그만둘\s*때까지|퇴사할\s*때까지|그만둔\s*날까지", text):
        return DateResult(_fmt(separation_date.year, separation_date.month))
    for word, delta in _RELATIVE_YEARS.items():
        if word in text:
            year = today.year + delta
            month = re.search(r"(\d{1,2})\s*월", text)
            if month and not _is_month(int(month[1])):
                return DateResult(None, ask=True, year_range=(year, year))
            if month and not _VAGUE.search(text.replace(month[0], "")):
                note = f"'{word} {month[1]}월' → {_fmt(year, int(month[1]))} (기준일 {today})"
                return DateResult(_fmt(year, int(month[1])), transformed=True, note=note)
            return DateResult(None, ask=True, year_range=(year, year))
    if (m := re.search(r"(\d{2})\s*(?:살|세)", text)) and age_at_separation is not None:
        # 만 나이·세는 나이가 섞여 쓰이므로 2년 넓게 잡고 연·월을 다시 묻습니다.
        latest = separation_date.year - (age_at_separation - int(m[1]))
        return DateResult(None, ask=True, year_range=(latest - 2, latest))
    return DateResult(None, ask=True)


# ── 자동 값 ─────────────────────────────────────────────


def date_field(expr: str, result: DateResult, today: date) -> FormField:
    """대화에서 받은 날짜 표현을 칸으로. 바꾼 값이면 확인 필요(extracted + transformed)이고,
    근거 보기에 원래 문장과 기준일이 남습니다 (F-11 완료 기준: '작년 3월' → 2025-03).
    """
    return FormField(
        value=result.value,
        status=FieldStatus.EXTRACTED if result.value else FieldStatus.MISSING,
        source=FieldSource.USER_ANSWER,
        transformed=result.transformed,
        evidence=FieldEvidence(
            kind=EvidenceKind.UTTERANCE, date=today, quote=expr.strip(), note=result.note
        ),
    )


def career_months(careers: list[Career]) -> int:
    """경력 기간 합계(개월). 시작·끝 월을 모두 넣어 셉니다 (2004-03~2026-09 = 271개월)."""
    total = 0
    for c in careers:
        start, end = _ym(c.start_date.value), _ym(c.end_date.value)
        if start and end and start <= end:
            total += _months(end) - _months(start) + 1
    return total


def derive_resume_values(data: ResumeData, separation_date: date) -> ResumeData:
    """재직여부·최종학력·희망 직종 경력을 정합니다 (2-1.4). 이미 찬 칸은 그대로 둡니다."""
    data = data.model_copy(deep=True)
    separation = (separation_date.year, separation_date.month)

    for c in data.careers:
        end = _ym(c.end_date.value)
        if end and not is_filled(c.employment_status) and end <= separation:
            c.employment_status = _confirmed("퇴직")

    if not any(is_filled(e.is_highest_education) for e in data.education):
        levels = [e for e in data.education if is_filled(e.education_level)]
        if len(levels) == 1:
            levels[0].is_highest_education = _confirmed(True)
        elif levels:
            top = max(levels, key=lambda e: _rank(e.education_level.value))
            top.is_highest_education = _suggested(True, "가장 높은 학력")

    for d in data.job_preferences.desired_occupations:
        name = occupation_name(d.occupation)
        if not name or is_filled(d.experience_type):
            continue
        same = [c for c in data.careers if occupation_name(c.occupation) == name]
        if same:
            years, months = divmod(career_months(same), 12)
            note = f"같은 직종 경력 합계 {years}년 {months}개월"
            d.experience_type = _suggested("경력", note)
            d.experience_years = _suggested(years, note)
            d.experience_months = _suggested(months, note)
        elif data.careers_status.status == FieldStatus.NOT_APPLICABLE:
            d.experience_type = _suggested("신입", "경력 없음")
    return data


def _rank(level: Any) -> int:
    return _EDUCATION_RANK.index(level) if level in _EDUCATION_RANK else -1


# ── 검사 ────────────────────────────────────────────────


@dataclass(frozen=True)
class ResumeIssue:
    # period_order · future_date · separation_mismatch · career_overlap · too_many · conflict
    code: str
    path: str


def check_resume(data: ResumeData, separation_date: date, today: date) -> list[ResumeIssue]:
    """일관성 검사 (2-1.4). 막지 않고 확인 질문을 고르는 데 씁니다."""
    issues: list[ResumeIssue] = []
    now = (today.year, today.month)
    for name, items in (("careers", data.careers), ("education", data.education)):
        for it in items:
            start, end = _ym(it.start_date.value), _ym(it.end_date.value)
            if start and end and start > end:
                issues.append(ResumeIssue("period_order", f"/{name}/{it.item_id}/start_date"))
            if end and end > now:
                issues.append(ResumeIssue("future_date", f"/{name}/{it.item_id}/end_date"))

    latest = _latest_career(data.careers)
    if latest and _ym(latest.end_date.value) != (separation_date.year, separation_date.month):
        issues.append(ResumeIssue("separation_mismatch", f"/careers/{latest.item_id}/end_date"))

    spans = [(c, _ym(c.start_date.value), _ym(c.end_date.value)) for c in data.careers]
    spans = [(c, s, e) for c, s, e in spans if s and e]
    for i, (_, a_start, a_end) in enumerate(spans):
        for b, b_start, b_end in spans[i + 1 :]:
            overlap = (
                min(_months(a_end), _months(b_end)) - max(_months(a_start), _months(b_start)) + 1
            )
            if overlap >= OVERLAP_MONTHS:
                issues.append(ResumeIssue("career_overlap", f"/careers/{b.item_id}"))

    prefs = data.job_preferences
    if len(prefs.desired_occupations) > MAX_PICKS:
        issues.append(ResumeIssue("too_many", "/job_preferences/desired_occupations"))
    if len(_as_list(prefs.desired_regions)) > MAX_PICKS:
        issues.append(ResumeIssue("too_many", "/job_preferences/desired_regions"))

    issues += [
        ResumeIssue("conflict", p) for p, f in form_fields(data) if f.status == FieldStatus.CONFLICT
    ]
    return issues


def _latest_career(careers: list[Career]) -> Career | None:
    dated = [c for c in careers if _ym(c.end_date.value)]
    return max(dated, key=lambda c: _ym(c.end_date.value)) if dated else None


# ── 완성도 · 저장 ───────────────────────────────────────


def _no_check(node: Any) -> bool:
    return not any(needs_check(f) for _, f in form_fields(node))


def _education_done(e: Education) -> bool:
    required = [e.education_level, e.graduation_status, e.school_name, e.start_date, e.end_date]
    if _rank(e.education_level.value) >= _rank("대학교(2/3년제)"):
        required.append(e.major)  # 학점은 몰라도 빈칸 저장 허용 (2-1.8)
    return all(is_filled(f) for f in required)


def _section_done(data: ResumeData) -> dict[str, bool]:
    prefs = data.job_preferences
    occupations_done = bool(prefs.desired_occupations) and all(
        is_filled(d.occupation)
        and occupation_value(d.occupation).get("status") != OccupationStatus.NEEDS_CONFIRMATION
        and is_filled(d.experience_type)
        for d in prefs.desired_occupations
    )
    na = FieldStatus.NOT_APPLICABLE
    return {
        "resume_title": is_filled(data.resume_title) and _no_check(data.resume_title),
        "education": bool(data.education)
        and all(_education_done(e) for e in data.education)
        and any(is_filled(e.is_highest_education) for e in data.education)
        and _no_check(data.education),
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
        and _no_check(prefs),
        "careers": (
            data.careers_status.status == na
            or (
                bool(data.careers)
                and all(
                    all(
                        is_filled(f) for f in (c.company_name, c.start_date, c.end_date, c.position)
                    )
                    for c in data.careers
                )
            )
        )
        and _no_check(data.careers),
        "certifications": (
            data.certifications_status.status == na
            or (
                bool(data.certifications)
                and all(is_filled(c.certificate_name) for c in data.certifications)
            )
        )
        and _no_check(data.certifications),
    }


def resume_completeness(data: ResumeData) -> Completeness:
    """꼭 묻는 5개 중 끝난 항목 수 (2-1.2). 확인 필요가 남은 항목은 세지 않습니다."""
    return Completeness(filled=sum(_section_done(data).values()))


def can_save_resume(data: ResumeData) -> bool:
    """5/5이고 확인 필요가 하나도 없을 때만 저장할 수 있습니다 (2-1.6)."""
    return resume_completeness(data).filled == 5 and _no_check(data)


# ── 다음 질문 ───────────────────────────────────────────


@dataclass(frozen=True)
class ResumeQuestion:
    """다음 질문 ID(프론트 QUESTION_LABEL과 같음), 문구 변수, 선택지."""

    id: str
    vars: dict[str, Any] = field(default_factory=dict)
    choices: tuple[str, ...] = ()


def next_resume_question(
    data: ResumeData,
    *,
    entry_branch: str,
    separation_date: date,
    doc_failed: bool = False,
) -> ResumeQuestion:
    """2-1.3 표를 위에서부터 검사해 처음 맞는 질문 하나를 고릅니다."""
    q = ResumeQuestion
    if doc_failed:
        return q("resume.doc_retry", choices=("다시 찍을게요", "말로 할게요"))
    for path, f in form_fields(data):
        if needs_check(f):
            return q(
                "resume.value_confirm", {"path": path}, ("네, 맞아요", "아니요, 다시 말할게요")
            )

    careers = sorted(data.careers, key=lambda c: str(c.start_date.value or ""), reverse=True)
    careers_open = data.careers_status.status == FieldStatus.MISSING
    if not careers and careers_open:
        return q(
            "resume.career_new", choices=("사진 올릴게요", "고용24에서 불러올게요", "말로 할게요")
        )
    if (
        entry_branch == "E7b"
        and careers_open
        and all(c.company_name.source == FieldSource.SEED for c in careers)
    ):
        end = _ym(careers[0].end_date.value) if careers else None
        return q(
            "resume.career_since_old", {"year": end[0] if end else None}, ("네, 있어요", "없어요")
        )
    for c in careers[:RECENT_CAREERS]:
        if not is_filled(c.main_duties):
            return q("resume.career_duties", {"company": c.company_name.value})
    for c in careers:
        if not is_filled(c.position):
            return q(
                "resume.career_position",
                {"company": c.company_name.value},
                ("말로 할게요", "없었어요"),
            )
    latest = _latest_career(careers)
    if (
        latest
        and _ym(latest.end_date.value) != (separation_date.year, separation_date.month)
        and latest.end_date.status != FieldStatus.CONFIRMED
    ):
        return q(
            "resume.career_end_check",
            {
                "company": latest.company_name.value,
                "year": separation_date.year,
                "month": separation_date.month,
            },
            ("네, 맞아요", "아니요"),
        )

    if not data.certifications and data.certifications_status.status == FieldStatus.MISSING:
        return q("resume.license", choices=("있어요", "없어요", "사진 올릴게요"))
    if not any(is_filled(e.education_level) for e in data.education):
        return q("resume.education_level", choices=("고등학교 졸업", "대학교 졸업", "말로 할게요"))
    for e in data.education:
        if not _education_done(e):
            return q("resume.education_detail", {"level": e.education_level.value})

    prefs = data.job_preferences
    if not prefs.desired_occupations:
        return q("resume.wish_job")
    for d in prefs.desired_occupations:
        if not is_filled(d.experience_type):
            return q(
                "resume.wish_experience",
                {"occupation": occupation_name(d.occupation)},
                ("네, 맞아요", "아니요"),
            )
    if not is_filled(prefs.desired_regions):
        return q("resume.wish_region")
    if not is_filled(prefs.desired_salary):
        return q("resume.wish_wage", choices=("면접 후 결정할게요", "금액 말할게요"))
    if not is_filled(prefs.employment_contract_type):
        return q("resume.wish_employment", choices=("정해지지 않은 일", "정해진 일", "상관없어요"))
    if not is_filled(prefs.military_alternative):
        return q("resume.wish_military", choices=("네, 맞아요", "아니요"))
    if not is_filled(data.resume_title):
        return q("resume.resume_title", choices=("네, 좋아요", "다르게 할게요"))
    if data.competencies_status.status == FieldStatus.MISSING:
        return q("resume.optional_sections", choices=("없어요", "있어요"))
    return q("resume.save_ready", choices=("확인하고 저장할게요", "고칠 게 있어요"))
