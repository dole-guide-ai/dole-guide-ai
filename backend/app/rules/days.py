"""활동 날짜 표현("어제", "지난주 금요일", "11월 20일")을 날짜로 바꿉니다.

모델은 사용자가 한 말 그대로의 표현만 넘기고, 날짜 계산은 이 함수가 합니다(ADR 0001: 날짜는 코드가).
뜻이 하나로 정해지지 않으면 None을 돌려주고, 대화에서 다시 묻습니다.

요일만("토요일에")·연도 없이("12월 28일")·일만("20일에") 말하면 이미 한 일인지(done)에 따라
가장 가까운 지난 날(오늘 포함) 또는 다가올 날(오늘 포함)로 정합니다. 시제는 문장 전체를 본
모델이 done으로 넘깁니다. 규칙은 위에서부터 한 번만 적용합니다(순서가 결과를 정함).
"""

import re
from datetime import date, timedelta

_WEEKDAYS = {"월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6}
_WEEK_OFFSETS = {"지난주": -1, "저번주": -1, "이번주": 0, "다음주": 1}
# 하루 단위 낱말. 긴 낱말부터 찾습니다("그끄저께"가 "그저께"보다, "엊그제"가 "그제"보다 먼저).
_DAY_OFFSETS = {
    "그끄저께": -3, "그그저께": -3, "그저께": -2, "그지께": -2, "엊그제": -2, "그제": -2,
    "어제": -1, "오늘": 0, "방금": 0, "아까": 0, "내일": 1, "모레": 2,
}  # fmt: skip
# "이틀 전"처럼 말로 한 날수. "일주일·한 주"는 7일, "두 주"는 14일입니다.
_SPOKEN_DAYS = {
    "하루": 1, "이틀": 2, "사흘": 3, "나흘": 4, "닷새": 5, "엿새": 6, "이레": 7,
    "일주일": 7, "열흘": 10, "보름": 15, "한주": 7, "두주": 14, "세주": 21,
}  # fmt: skip
DAYS_PER_WEEK = 7
# 연도·달을 말하지 않은 날짜를 고를 때 오늘에서 이만큼(반년)보다 먼 날은 고르지 않습니다.
MAX_GUESS_DAYS = 183

_FULL_DATE = re.compile(r"(\d{4})[-./년](\d{1,2})[-./월](\d{1,2})")
_MONTH_DAY = re.compile(r"(\d{1,2})월(\d{1,2})일")
_AGO = re.compile(r"(\d{1,3})(일|주)(?:일)?전")
_WEEK_DAY = re.compile(r"([월화수목금토일])요일")
_DAY_ONLY = re.compile(r"(?<![\d월])(\d{1,2})일(?!전)")


def normalize_day(expr: str, today: date, *, done: bool = True) -> date | None:
    """표현 → 날짜. done이 참이면 이미 한 일(지난 날 우선), 거짓이면 할 일(다가올 날 우선)."""
    text = re.sub(r"\s+", "", expr)
    if m := _FULL_DATE.search(text):
        return _safe(int(m[1]), int(m[2]), int(m[3]))
    if m := _MONTH_DAY.search(text):
        month, day = int(m[1]), int(m[2])
        years = (today.year, today.year - 1) if done else (today.year, today.year + 1)
        return _nearest([_safe(y, month, day) for y in years], today, done)
    if m := _AGO.search(text):
        unit = DAYS_PER_WEEK if m[2] == "주" else 1
        return today - timedelta(days=int(m[1]) * unit)
    for word, days in _SPOKEN_DAYS.items():
        if f"{word}전" in text:
            return today - timedelta(days=days)
    if m := _WEEK_DAY.search(text):
        weekday = _WEEKDAYS[m[1]]
        for word, offset in _WEEK_OFFSETS.items():
            if word in text:
                monday = today - timedelta(days=today.weekday()) + timedelta(weeks=offset)
                return monday + timedelta(days=weekday)
        if done:  # 가장 가까운 지난 그 요일(오늘 포함)
            return today - timedelta(days=(today.weekday() - weekday) % DAYS_PER_WEEK)
        return today + timedelta(days=(weekday - today.weekday()) % DAYS_PER_WEEK)
    for word, offset in _DAY_OFFSETS.items():
        if word in text:
            return today + timedelta(days=offset)
    if m := _DAY_ONLY.search(text):
        day = int(m[1])
        this_month = _safe(today.year, today.month, day)
        other = _shift_month(today, -1 if done else 1, day)
        return _nearest([this_month, other], today, done)
    return None


def _nearest(candidates: list[date | None], today: date, done: bool) -> date | None:
    """후보 중 오늘 기준 방향(done이면 오늘 이전, 아니면 오늘 이후)에서 가장 가까운 날.

    반년보다 멀면 말과 시제가 어긋난 것(오늘이 12월 16일인데 "12월 20일에 지원했어요")이라
    추측하지 않고 None으로 다시 묻게 합니다.
    """
    valid = [d for d in candidates if d is not None and ((d <= today) if done else (d >= today))]
    if not valid:
        return None
    nearest = min(valid, key=lambda d: abs((d - today).days))
    return nearest if abs((nearest - today).days) <= MAX_GUESS_DAYS else None


def _shift_month(today: date, months: int, day: int) -> date | None:
    month_index = today.year * 12 + today.month - 1 + months
    return _safe(month_index // 12, month_index % 12 + 1, day)


def _safe(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None
