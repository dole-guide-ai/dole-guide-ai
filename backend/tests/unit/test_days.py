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
        # 띄어쓰기·사투리·말로 한 날수 (골든셋 F-082 "그지께")
        ("지난 주 금요일", date(2026, 12, 11)),
        ("그지께 OO마트에 넣었구먼", date(2026, 12, 14)),
        ("엊그제", date(2026, 12, 14)),
        ("그끄저께", date(2026, 12, 13)),
        ("이틀 전에", date(2026, 12, 14)),
        ("사흘 전", date(2026, 12, 13)),
        ("일주일 전", date(2026, 12, 9)),
        ("2주 전", date(2026, 12, 2)),
        # 요일만 말하면 이미 한 일은 가장 가까운 지난 그 요일, 오늘이면 오늘 (골든셋 F-029·F-033)
        ("월요일에 지원했어요", date(2026, 12, 14)),
        ("토요일에 채용박람회 다녀왔어요", date(2026, 12, 12)),
        ("수요일", date(2026, 12, 16)),
        # 일만 말하면 이번 달에서, 아직 안 온 날이면 지난달에서
        ("10일에", date(2026, 12, 10)),
        ("20일에", date(2026, 11, 20)),
    ],
)
def test_normalize_day(expr: str, expected: date) -> None:
    assert normalize_day(expr, TODAY) == expected


@pytest.mark.parametrize(
    ("expr", "expected"),
    [
        ("금요일에 면접 있어요", date(2026, 12, 18)),
        ("다음 주 월요일", date(2026, 12, 21)),
        ("내일", date(2026, 12, 17)),
        ("12월 20일", date(2026, 12, 20)),
        ("1월 5일", date(2027, 1, 5)),
        # 방향을 말한 표현은 일만 있는 표현("20일")보다 먼저 봅니다(CodeRabbit #280).
        ("3일 후", date(2026, 12, 19)),
        ("이틀 뒤", date(2026, 12, 18)),
        ("다음 달 20일", date(2027, 1, 20)),
    ],
)
def test_planned_activity_looks_forward(expr: str, expected: date) -> None:
    # 앞으로 할 활동(예정)은 다가올 날로 정합니다(대화에서도 예정 활동을 받음).
    assert normalize_day(expr, TODAY, done=False) == expected


def test_year_less_date_said_early_in_year_is_last_year() -> None:
    # 1월에 "12월 28일에 지원했어요"는 올해 12월(미래)이 아니라 작년 12월입니다.
    assert normalize_day("12월 28일", date(2027, 1, 5)) == date(2026, 12, 28)


@pytest.mark.parametrize("expr", ["언젠가", "2월 30일", "얼마 전에", "12월 20일"])
def test_unclear_day_is_none(expr: str) -> None:
    # "12월 20일"(이미 한 일)은 오늘(12월 16일) 뒤라 작년으로 보면 반년 넘게 떨어져 다시 묻습니다.
    assert normalize_day(expr, TODAY) is None
