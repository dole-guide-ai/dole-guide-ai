"""활동 날짜 표현("어제", "지난주 금요일", "11월 20일")을 날짜로 바꿉니다.

모델은 사용자가 한 말 그대로의 표현만 넘기고, 날짜 계산은 이 함수가 합니다(ADR 0001: 날짜는 코드가).
뜻이 하나로 정해지지 않으면 None을 돌려주고, 대화에서 다시 묻습니다.
"""

import re
from datetime import date, timedelta

_DAY_OFFSETS = {"오늘": 0, "방금": 0, "아까": 0, "어제": -1, "그제": -2, "그저께": -2}
_WEEKDAYS = {"월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6}
_WEEK_OFFSETS = {"지난주": -1, "저번 주": -1, "저번주": -1, "이번 주": 0, "이번주": 0}


def normalize_day(expr: str, today: date) -> date | None:
    text = expr.strip()
    if m := re.search(r"(\d{4})\s*[-./년]\s*(\d{1,2})\s*[-./월]\s*(\d{1,2})", text):
        return _safe(int(m[1]), int(m[2]), int(m[3]))
    if m := re.search(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일", text):
        return _safe(today.year, int(m[1]), int(m[2]))
    if m := re.search(r"(\d{1,2})\s*일\s*전", text):
        return today - timedelta(days=int(m[1]))
    for word, offset in _WEEK_OFFSETS.items():
        if word in text and (m := re.search(r"([월화수목금토일])요일", text)):
            monday = today - timedelta(days=today.weekday()) + timedelta(weeks=offset)
            return monday + timedelta(days=_WEEKDAYS[m[1]])
    for word, offset in _DAY_OFFSETS.items():
        if word in text:
            return today + timedelta(days=offset)
    return None


def _safe(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None
