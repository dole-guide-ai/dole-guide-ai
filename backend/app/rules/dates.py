"""대화 속 날짜 표현을 서류 칸 값으로 바꾸는 규칙 함수입니다 (실험: 날짜는 규칙 코드가 바꾸기).

AI는 사용자가 한 말 그대로("작년 3월", "지난주 금요일")만 옮기고, 오늘 날짜를 기준으로 한
계산은 여기서 합니다. 이력서 연·월은 팀 공용 `resume.normalize_date`를 그대로 씁니다.
바꿀 수 없으면 None을 돌려 칸을 비워 둡니다(지어내지 않음). DB·LLM을 모르는 순수 함수입니다.
"""

import re
from datetime import date, timedelta

from app.rules.resume import normalize_date

WEEKDAYS = "월화수목금토일"
RELATIVE_DAYS = {"오늘": 0, "방금": 0, "지금": 0, "아까": 0, "어제": -1, "그제": -2, "그저께": -2}
ISO_DAY = re.compile(r"(\d{4})\s*[-./년]\s*(\d{1,2})\s*[-./월]\s*(\d{1,2})")
MONTH_DAY = re.compile(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일")
WEEKDAY = re.compile(r"(지난주|저번 ?주|이번 ?주)?\s*([월화수목금토일])요일")
YEAR_ONLY = re.compile(r"(\d{4})\s*년")
# 연도를 말로 한 표현. "재작년"이 "작년"보다 먼저 맞아야 합니다.
YEAR_WORDS = {"재작년": -2, "작년": -1, "지난해": -1, "올해": 0, "금년": 0}
MONTH_IN_TEXT = re.compile(r"\d\s*월|\d{4}\s*[-./]\s*\d")
# 말로 한 달 이름("삼월", "구월")과 "올"(=올해). 긴 이름(십이·십일)부터 맞춥니다.
KOREAN_MONTHS = {"십이": 12, "십일": 11, "십": 10, "일": 1, "이": 2, "삼": 3, "사": 4, "오": 5,
                 "유": 6, "육": 6, "칠": 7, "팔": 8, "구": 9}  # fmt: skip
KOREAN_MONTH = re.compile(rf"({'|'.join(KOREAN_MONTHS)})월")
THIS_YEAR_SHORT = re.compile(r"올(?!해)\s*")


def _spoken_to_digits(text: str) -> str:
    """ "작년 삼월", "올 구월" → "작년 3월", "올해 9월"."""
    text = KOREAN_MONTH.sub(lambda m: f"{KOREAN_MONTHS[m[1]]}월", text)
    return THIS_YEAR_SHORT.sub("올해 ", text)


def _safe(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _spoken_year(text: str, today: date) -> int | None:
    """말에 들어 있는 연도("2025년", "작년", "올해"). 없으면 None."""
    if m := YEAR_ONLY.search(text):
        return int(m[1])
    for word, delta in YEAR_WORDS.items():
        if word in text:
            return today.year + delta
    return None


def normalize_day(expr: str | None, today: date) -> str | None:
    """활동 날짜 표현 → YYYY-MM-DD.

    "11월 20일"처럼 연도가 없으면 오늘을 넘지 않는 가장 가까운 해로 봅니다.
    """
    text = (expr or "").strip()
    if not text:
        return None
    if m := ISO_DAY.search(text):
        day = _safe(int(m[1]), int(m[2]), int(m[3]))
        return day.isoformat() if day else None
    for word, delta in RELATIVE_DAYS.items():
        if word in text:
            return (today + timedelta(days=delta)).isoformat()
    if m := MONTH_DAY.search(text):
        if (year := _spoken_year(text, today)) is not None:
            # "작년 3월 20일"처럼 연도를 말했으면 그 해로 정하고 지난해로 미루지 않습니다.
            day = _safe(year, int(m[1]), int(m[2]))
            return day.isoformat() if day else None
        day = _safe(today.year, int(m[1]), int(m[2]))
        if day and day > today:
            day = _safe(today.year - 1, int(m[1]), int(m[2]))
        return day.isoformat() if day else None
    if m := WEEKDAY.search(text):
        monday = today - timedelta(days=today.weekday())
        target = WEEKDAYS.index(m[2])
        if m[1] and m[1].replace(" ", "") in ("지난주", "저번주"):
            return (monday - timedelta(days=7) + timedelta(days=target)).isoformat()
        day = monday + timedelta(days=target)
        # "금요일에"처럼 주를 말하지 않았는데 아직 오지 않은 요일이면 지난주로 봅니다.
        if not m[1] and day > today:
            day -= timedelta(days=7)
        return day.isoformat()
    return None


def normalize_month(
    expr: str | None,
    today: date,
    separation_date: date,
    age_at_separation: int | None = None,
    *,
    allow_year_only: bool = False,
) -> str | None:
    """경력·학력·자격증 날짜 표현 → YYYY-MM (팀 규칙 resume.normalize_date).

    자격증 취득·졸업처럼 연도만 알아도 되는 칸은 allow_year_only로 "YYYY"를 받습니다.
    경력 시작·끝은 월까지 필요해서 연도만이면 None(다시 물음)입니다.
    """
    text = _spoken_to_digits((expr or "").strip())
    if not text:
        return None
    if re.fullmatch(r"\d{4}-\d{2}", text):
        return text if 1 <= int(text[5:]) <= 12 else None
    result = normalize_date(text, today, separation_date, age_at_separation)
    if result.value:
        return result.value
    # 월을 말했는데 읽지 못했으면("2026년 13월") 연도만 남기지 않고 다시 묻습니다.
    if MONTH_IN_TEXT.search(text):
        return None
    if allow_year_only and (m := YEAR_ONLY.search(text) or re.fullmatch(r"\d{4}", text)):
        return m[1] if m.re.groups else m[0]
    return None
