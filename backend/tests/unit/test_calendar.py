from datetime import date

from app.core.calendar import is_business_day, next_business_day


def test_weekday_is_business_day() -> None:
    assert is_business_day(date(2026, 10, 21))  # 수요일


def test_weekend_moves_to_monday() -> None:
    assert next_business_day(date(2026, 10, 24)) == date(2026, 10, 26)


def test_holiday_moves_to_next_weekday() -> None:
    # 2026-10-09 한글날(금) → 다음 영업일은 10-12(월)
    assert not is_business_day(date(2026, 10, 9))
    assert next_business_day(date(2026, 10, 9)) == date(2026, 10, 12)


def test_substitute_holiday_is_not_business_day() -> None:
    # 2026-03-01 삼일절이 일요일 → 03-02(월) 대체공휴일
    assert not is_business_day(date(2026, 3, 2))
    assert next_business_day(date(2026, 3, 1)) == date(2026, 3, 3)
