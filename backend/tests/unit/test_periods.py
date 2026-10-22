from datetime import date

from app.rules.periods import (
    benefit_days,
    benefit_end_date,
    build_rounds,
    end_reason_on,
    expected_end_date,
    is_attendance_round,
    period_end_date,
    recipient_group,
    remaining_rounds,
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
    assert benefit_end_date(applied, 120) == date(2026, 5, 11)
    assert period_end_date(date(2026, 1, 31)) == date(2027, 1, 31)
    assert expected_end_date(date(2026, 5, 11), date(2027, 1, 31)) == date(2026, 5, 11)


def test_period_end_on_leap_day() -> None:
    # 2028-02-29 시작 → 2029-02-29가 없으므로 2월 말일에 끝남
    assert period_end_date(date(2028, 2, 28)) == date(2029, 2, 28)


def test_attendance_rounds() -> None:
    assert [n for n in range(1, 10) if is_attendance_round("general", n)] == [1, 4, 8]
    # 60세 이상·장애인도 4·8차 출석 (상세기획 결정, 평가 시나리오 form-011)
    assert [n for n in range(1, 10) if is_attendance_round("age_60_64", n)] == [1, 4, 8]
    assert [n for n in range(1, 10) if is_attendance_round("age65_or_disabled", n)] == [1, 4, 8]


def test_build_rounds_every_28_days_and_skips_holidays() -> None:
    rounds = build_rounds("general", date(2026, 9, 1), date(2026, 9, 15), date(2026, 12, 31))

    assert rounds[0].period_start == date(2026, 9, 8)
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


def test_end_reason_is_whichever_end_comes_first() -> None:
    """종료 예정일이 지나야 종료이고, 먼저 오는 쪽이 사유입니다 (설계 6.6, F-33)."""
    period_end = date(2027, 9, 30)
    assert end_reason_on(date(2027, 3, 1), date(2027, 3, 1), period_end) is None
    assert end_reason_on(date(2027, 3, 2), date(2027, 3, 1), period_end) == "exhausted"
    assert end_reason_on(date(2027, 10, 1), date(2027, 12, 1), period_end) == "period_expired"
    assert end_reason_on(date(2027, 10, 1), None, period_end) == "period_expired"


def test_remaining_rounds_counts_today_and_later() -> None:
    dates = [date(2026, 10, 1), date(2026, 10, 21), date(2026, 11, 18)]
    assert remaining_rounds(dates, date(2026, 10, 21)) == 2
    assert remaining_rounds(dates, date(2026, 11, 19)) == 0
