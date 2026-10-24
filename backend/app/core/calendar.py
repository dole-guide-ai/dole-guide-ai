"""
영업일을 판단하는 로직.
실업인정일이 토요일·일요일·공휴일(대체공휴일 포함)이면 다음 평일로 옮길 때 사용.
"""

from datetime import date, timedelta
from functools import lru_cache

import holidays


@lru_cache(maxsize=16)
def _kr_holidays(year: int) -> holidays.HolidayBase:
    return holidays.country_holidays("KR", years=year)


def is_business_day(day: date) -> bool:
    return day.weekday() < 5 and day not in _kr_holidays(day.year)


def next_business_day(day: date) -> date:
    """`day`가 영업일이면 그대로, 아니면 다음 영업일."""
    while not is_business_day(day):
        day += timedelta(days=1)
    return day
