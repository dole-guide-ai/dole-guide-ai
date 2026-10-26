"""활동 날짜 표현 → 날짜 (rules/days.py). 기준일 2026-12-16(수)."""

from datetime import date

import pytest

from app.rules.days import normalize_day

TODAY = date(2026, 12, 16)


@pytest.mark.parametrize(
    ("expr", "expected"),
    [
        ("방금", date(2026, 12, 16)),
        ("어제 지원했어요", date(2026, 12, 15)),
        ("그저께", date(2026, 12, 14)),
        ("지난주 금요일", date(2026, 12, 11)),
        ("이번 주 월요일", date(2026, 12, 14)),
        ("11월 20일", date(2026, 11, 20)),
        ("2026-12-01", date(2026, 12, 1)),
        ("3일 전", date(2026, 12, 13)),
    ],
)
def test_normalize_day(expr: str, expected: date) -> None:
    assert normalize_day(expr, TODAY) == expected


@pytest.mark.parametrize("expr", ["언젠가", "2월 30일", "얼마 전에"])
def test_unclear_day_is_none(expr: str) -> None:
    assert normalize_day(expr, TODAY) is None
