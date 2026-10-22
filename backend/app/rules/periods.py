"""수급 기간과 회차를 계산하는 규칙 함수입니다.

이직 당시 나이로 수급자 유형을 정하고, 나이와 고용보험 가입기간으로 소정급여일수를 구합니다.
1차 인정일부터 28일 간격으로 회차를 만들고, 인정일이 휴일이면 다음 평일로 옮깁니다.
급여 소진 예정일과 수급기간 끝(이직 다음 날부터 12개월) 중 이른 날을 종료 예정일로 봅니다.
종료 예정일이 지나면 종료 사유를 정하고, 남은 회차 수를 셉니다. 회차 활동 점검은 이후에 더합니다.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from app.core.calendar import next_business_day

WAITING_DAYS = 7
ROUND_INTERVAL_DAYS = 28

# 가입기간 경계(년)와 소정급여일수 (설계 6.6)
_YEAR_BOUNDS = (1, 3, 5, 10)
_DAYS_UNDER_50 = (120, 150, 180, 210, 240)
_DAYS_50_OR_DISABLED = (120, 180, 210, 240, 270)


def recipient_group(age_at_separation: int, has_disability: bool, is_repeat: bool = False) -> str:
    """이직 당시 만 나이로 한 번 정합니다. 수급 중 나이가 바뀌어도 그대로입니다."""
    if is_repeat:
        return "repeat"
    if has_disability or age_at_separation >= 65:
        return "age65_or_disabled"
    if age_at_separation >= 60:
        return "age_60_64"
    return "general"


def benefit_days(age_at_separation: int, has_disability: bool, insured_years: float) -> int:
    table = _DAYS_50_OR_DISABLED if has_disability or age_at_separation >= 50 else _DAYS_UNDER_50
    index = sum(1 for bound in _YEAR_BOUNDS if insured_years >= bound)
    return table[index]


def benefit_end_date(eligibility_applied_on: date, days: int) -> date:
    """급여 소진 예정일: 첫 지급일 + 소정급여일수 - 1 (매 회차 인정 가정).

    대기기간은 신청일부터 7일간(고용보험법 제49조)이라 첫 지급일은 신청일 + 7일입니다.
    """
    first_paid_day = eligibility_applied_on + timedelta(days=WAITING_DAYS)
    return first_paid_day + timedelta(days=days - 1)


def period_end_date(separation_date: date) -> date:
    """수급기간 끝: 이직일 다음 날부터 12개월.

    시작일의 1년 뒤 같은 날 전날에 끝납니다.
    그날이 없으면(2월 29일) 그 달 말일에 끝납니다(민법 제160조).
    """
    start = separation_date + timedelta(days=1)
    try:
        anniversary = start.replace(year=start.year + 1)
    except ValueError:  # 2월 29일
        return start.replace(year=start.year + 1, day=28)
    return anniversary - timedelta(days=1)


def expected_end_date(benefit_end: date | None, period_end: date) -> date:
    return min(benefit_end, period_end) if benefit_end else period_end


def is_attendance_round(group: str, round_no: int) -> bool:
    """일반은 1·4·8차, 60세 이상·장애인은 1·4차 (반복수급자는 지원하지 않음)."""
    rounds = (1, 4, 8) if group == "general" else (1, 4)
    return round_no in rounds


@dataclass(frozen=True)
class PlannedRound:
    round_no: int
    period_start: date
    period_end: date
    recognition_date: date
    attendance_required: bool


def build_rounds(
    group: str,
    eligibility_applied_on: date,
    first_recognition_date: date,
    end_date: date,
) -> list[PlannedRound]:
    """1차 인정일부터 종료 예정일까지 회차를 만듭니다. 휴일이면 다음 평일로 옮깁니다.

    마지막 회차의 대상기간은 종료 예정일까지만입니다. 인정일은 그 뒤여도 그대로 둡니다.
    """
    rounds: list[PlannedRound] = []
    start = eligibility_applied_on + timedelta(days=WAITING_DAYS)
    recognition = next_business_day(first_recognition_date)
    round_no = 1
    while start <= end_date:
        rounds.append(
            PlannedRound(
                round_no=round_no,
                period_start=start,
                period_end=min(recognition, end_date),
                recognition_date=recognition,
                attendance_required=is_attendance_round(group, round_no),
            )
        )
        start = recognition + timedelta(days=1)
        recognition = next_business_day(recognition + timedelta(days=ROUND_INTERVAL_DAYS))
        round_no += 1
    return rounds


def first_recognition_in_range(applied_on: date, first: date, end_date: date) -> bool:
    """1차 인정일은 대기기간(신청일부터 7일) 뒤이고 종료 예정일 안이어야 합니다 (F-16).

    종료 예정일 뒤 날짜를 받으면 회차가 수급기간 밖에 만들어집니다. 회차는 휴일이면 다음 평일을
    인정일로 저장하므로(`build_rounds`), 옮긴 날짜도 종료 예정일 안인지 봅니다.
    """
    return (
        applied_on + timedelta(days=WAITING_DAYS) < first and next_business_day(first) <= end_date
    )


def end_reason_on(today: date, benefit_end: date | None, period_end: date) -> str | None:
    """종료 예정일이 지났으면 종료 사유, 아니면 None (설계 6.6, F-33).

    급여 소진일과 수급기간 끝 중 먼저 오는 쪽이 사유입니다. 같은 날이면 수급기간 만료로 봅니다.
    취업(employed)은 신고로 정해지므로 여기서 계산하지 않습니다.
    """
    end = expected_end_date(benefit_end, period_end)
    if today <= end:
        return None
    if benefit_end is not None and benefit_end < period_end:
        return "exhausted"
    return "period_expired"


def remaining_rounds(recognition_dates: list[date], today: date) -> int:
    """오늘이 속한 회차를 포함해 아직 인정일이 지나지 않은 회차 수 (F-33)."""
    return sum(1 for d in recognition_dates if d >= today)
