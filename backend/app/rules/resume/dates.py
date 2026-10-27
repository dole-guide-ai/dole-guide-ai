"""사용자의 날짜 표현을 고용24 칸 형식(YYYY-MM)으로 바꿉니다 (상세기획 2-1.4 날짜 표현)."""

import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from app.schemas.common import EvidenceKind, FieldEvidence, FieldSource, FieldStatus, FormField
from app.schemas.forms.resume import Career


def ym(value: Any) -> tuple[int, int] | None:
    m = re.fullmatch(r"(\d{4})-(\d{2})", str(value or ""))
    return (int(m[1]), int(m[2])) if m and _is_month(int(m[2])) else None


def _is_month(month: int) -> bool:
    return 1 <= month <= 12


def months(value: tuple[int, int]) -> int:
    return value[0] * 12 + value[1]


def fmt(year: int, month: int) -> str:
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
# 말로 한 월("삼월", "시월")을 숫자로. 긴 이름부터 바꿔야 "십이월"이 "십"+"이월"로 깨지지 않습니다.
_KOREAN_MONTHS = {
    "십이월": 12, "십일월": 11, "시월": 10, "구월": 9, "팔월": 8, "칠월": 7,
    "유월": 6, "오월": 5, "사월": 4, "삼월": 3, "이월": 2, "일월": 1,
}  # fmt: skip


def _spoken_months(text: str) -> str:
    """말로 한 월을 숫자로, 월 앞의 "올"("올 구월")을 "올해"로 바꿉니다("올렸어요"는 그대로)."""
    for word, month in _KOREAN_MONTHS.items():
        text = text.replace(word, f"{month}월")
    return re.sub(r"올(?!해)\s*(?=\d{1,2}\s*월)", "올해 ", text)


def normalize_date(
    expr: str, today: date, separation_date: date, age_at_separation: int | None = None
) -> DateResult:
    """사용자의 날짜 표현을 YYYY-MM으로 바꿉니다."""
    text = _spoken_months(expr.strip())
    if m := re.search(r"(\d{4})\s*(?:년|[-./])\s*(\d{1,2})", text):
        if not _is_month(int(m[2])):
            return DateResult(None, ask=True)
        return DateResult(fmt(int(m[1]), int(m[2])))
    if re.search(r"지금까지|그만둘\s*때까지|퇴사할\s*때까지|그만둔\s*날까지", text):
        return DateResult(fmt(separation_date.year, separation_date.month))
    for word, delta in _RELATIVE_YEARS.items():
        if word in text:
            year = today.year + delta
            month = re.search(r"(\d{1,2})\s*월", text)
            if month and not _is_month(int(month[1])):
                return DateResult(None, ask=True, year_range=(year, year))
            if month and not _VAGUE.search(text.replace(month[0], "")):
                note = f"'{word} {month[1]}월' → {fmt(year, int(month[1]))} (기준일 {today})"
                return DateResult(fmt(year, int(month[1])), transformed=True, note=note)
            return DateResult(None, ask=True, year_range=(year, year))
    if (m := re.search(r"(\d{2})\s*(?:살|세)", text)) and age_at_separation is not None:
        # 만 나이·세는 나이가 섞여 쓰이므로 2년 넓게 잡고 연·월을 다시 묻습니다.
        latest = separation_date.year - (age_at_separation - int(m[1]))
        return DateResult(None, ask=True, year_range=(latest - 2, latest))
    return DateResult(None, ask=True)


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
        start, end = ym(c.start_date.value), ym(c.end_date.value)
        if start and end and start <= end:
            total += months(end) - months(start) + 1
    return total
