from datetime import date

import pytest

from app.rules.dates import normalize_day, normalize_month

TODAY = date(2026, 12, 16)  # 수요일
SEPARATION = date(2026, 9, 30)


@pytest.mark.parametrize(
    ("expr", "expected"),
    [
        ("방금", "2026-12-16"),
        ("지금", "2026-12-16"),
        ("어제", "2026-12-15"),
        ("어제 지원했어요", "2026-12-15"),
        ("그저께", "2026-12-14"),
        ("이번 주 월요일", "2026-12-14"),
        ("2026-12-01", "2026-12-01"),
        ("3일 전", "2026-12-13"),
        ("언젠가", None),
        ("얼마 전에", None),
        ("지난주 금요일", "2026-12-11"),
        ("금요일", "2026-12-11"),  # 아직 오지 않은 요일이면 지난주
        ("월요일", "2026-12-14"),
        ("11월 20일", "2026-11-20"),
        ("12월 20일", "2025-12-20"),  # 오늘을 넘으면 작년
        ("2026.12.08", "2026-12-08"),
        ("다음 주쯤", None),
        ("2월 30일", None),
        ("작년 3월 20일", "2025-03-20"),  # 말한 연도를 따름
        ("올해 12월 20일", "2026-12-20"),
        ("2025년 11월 20일", "2025-11-20"),
    ],
)
def test_normalize_day(expr: str, expected: str | None) -> None:
    assert normalize_day(expr, TODAY) == expected


@pytest.mark.parametrize(
    ("expr", "year_only", "expected"),
    [
        ("작년 3월", False, "2025-03"),
        ("작년 삼월", False, "2025-03"),
        ("올 구월", False, "2026-09"),
        ("2004년 3월", False, "2004-03"),
        ("2025-03", False, "2025-03"),
        ("재작년 겨울", False, None),  # 애매하면 다시 물음
        ("2011년", False, None),  # 경력은 월까지 필요
        ("2011년에", True, "2011"),  # 자격증 취득·졸업은 연도만도 받음
        ("1990", True, "1990"),
        ("2026-13", False, None),  # 없는 달
        ("2026년 13월", True, None),  # 월을 말했으면 연도만 남기지 않음
    ],
)
def test_normalize_month(expr: str, year_only: bool, expected: str | None) -> None:
    got = normalize_month(expr, TODAY, SEPARATION, 61, allow_year_only=year_only)

    assert got == expected
