from datetime import date

from app.rules.periods import (
    benefit_days,
    benefit_end_date,
    build_rounds,
    expected_end_date,
    is_attendance_round,
    period_end_date,
    recipient_group,
)


def test_recipient_group_uses_age_at_separation() -> None:
    assert recipient_group(58, False) == "general"
    assert recipient_group(61, False) == "age_60_64"
    assert recipient_group(67, False) == "age65_or_disabled"
    assert recipient_group(45, True) == "age65_or_disabled"
    assert recipient_group(58, False, is_repeat=True) == "repeat"


def test_benefit_days_table() -> None:
    assert benefit_days(58, False, 25.4) == 270
    assert benefit_days(67, False, 4.2) == 210
    assert benefit_days(45, False, 0.5) == 120
    assert benefit_days(45, False, 12) == 240


def test_end_dates() -> None:
    applied = date(2026, 1, 5)
    assert benefit_end_date(applied, 120) == date(2026, 5, 12)
    assert period_end_date(date(2026, 1, 31)) == date(2027, 1, 31)
    assert expected_end_date(date(2026, 5, 12), date(2027, 1, 31)) == date(2026, 5, 12)


def test_attendance_rounds() -> None:
    assert [n for n in range(1, 10) if is_attendance_round("general", n)] == [1, 4, 8]
    assert [n for n in range(1, 10) if is_attendance_round("age_60_64", n)] == [1, 4]


def test_build_rounds_every_28_days_and_skips_holidays() -> None:
    rounds = build_rounds("general", date(2026, 9, 1), date(2026, 9, 15), date(2026, 12, 31))

    assert rounds[0].period_start == date(2026, 9, 9)
    assert rounds[0].recognition_date == date(2026, 9, 15)
    # 9.15 + 28 = 10.13(화)
    assert rounds[1].period_start == date(2026, 9, 16)
    assert rounds[1].recognition_date == date(2026, 10, 13)
    assert all(r.period_start <= r.period_end for r in rounds)
    assert rounds[3].attendance_required


def test_build_rounds_moves_weekend_to_monday() -> None:
    # 1차 인정일이 토요일이면 월요일로
    rounds = build_rounds("general", date(2026, 10, 1), date(2026, 10, 17), date(2026, 11, 1))

    assert rounds[0].recognition_date == date(2026, 10, 19)
