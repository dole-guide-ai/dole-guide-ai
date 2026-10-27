"""대시보드 알림 판정 (rules/notices.py). 합성 값만 씁니다."""

from datetime import date, datetime, time

from app.core.clock import KST
from app.rules.notices import account_notices, missed_round, round_deadline
from app.schemas.accounts import RoundDeadline
from app.schemas.application import SubmitMode
from app.schemas.procedure import ProcedureRead, RecipientGroup, Stage
from app.schemas.rounds import ApplicationStatus, RoundStatus, RoundSummary

TODAY = date(2026, 10, 21)


def procedure(stage: Stage = Stage.RECOGNITION, age: int = 58) -> ProcedureRead:
    return ProcedureRead(
        stage=stage,
        recipient_group=RecipientGroup.GENERAL,
        age_at_separation=age,
        has_disability=False,
        separation_date=date(2026, 8, 31),
        education_done=True,
        benefit_days=150,
        period_end_date=date(2027, 8, 31),
    )


def round_(
    no: int,
    recognition: date,
    *,
    status: RoundStatus = RoundStatus.CURRENT,
    attend: bool = False,
    submitted: bool = False,
) -> RoundSummary:
    return RoundSummary(
        round=no,
        period_start=date(2026, 10, 1),
        period_end=recognition,
        recognition_date=recognition,
        attendance_required=attend,
        status=status,
        application_status=ApplicationStatus.SUBMITTED if submitted else ApplicationStatus.DRAFT,
    )


def keys(notices) -> list[str]:
    return [n.key for n in notices]


def test_visit_notice_only_for_65_and_over_before_applying() -> None:
    visit = account_notices(procedure(Stage.EDUCATION, age=67), None, None, None)
    assert keys(visit) == ["visit"] and visit[0].rule_refs == ["PROC-048"]
    assert "67세" in visit[0].text
    assert account_notices(procedure(Stage.EDUCATION, age=61), None, None, None) == []
    assert account_notices(procedure(Stage.RECOGNITION, age=67), None, None, None) == []


def test_deadline_follows_the_18_oclock_rule_not_the_date_alone() -> None:
    current = round_(4, TODAY)
    morning = round_deadline(current, datetime.combine(TODAY, time(10), KST))
    evening = round_deadline(current, datetime.combine(TODAY, time(18, 30), KST))

    assert (morning.d_day, morning.submit_mode, morning.overdue) == (0, SubmitMode.SEND, False)
    assert (evening.d_day, evening.submit_mode, evening.overdue) == (0, SubmitMode.CHANGE, True)
    overdue = account_notices(procedure(), current, evening, None)
    assert keys(overdue) == ["overdue-2026-10-21"]
    assert overdue[0].rule_refs == ["DUE-089", "DUE-094"]
    assert "11월 4일" in overdue[0].text  # 인정일부터 14일


def test_missed_round_within_14_days_shows_change_request() -> None:
    closed = round_(3, date(2026, 10, 14), status=RoundStatus.CLOSED)
    sent = round_(3, date(2026, 10, 14), status=RoundStatus.CLOSED, submitted=True)
    old = round_(2, date(2026, 9, 30), status=RoundStatus.CLOSED)

    assert missed_round([old, closed], TODAY) == closed
    assert missed_round([sent], TODAY) is None
    assert missed_round([old], TODAY) is None  # 14일이 지남
    notices = account_notices(procedure(), None, None, closed)
    assert keys(notices) == ["overdue-2026-10-14"]


def test_attendance_notice_is_not_shown_with_overdue() -> None:
    current = round_(4, date(2026, 10, 27), attend=True)
    deadline = RoundDeadline(d_day=6, submit_mode=SubmitMode.ATTEND, overdue=False)

    attend = account_notices(procedure(), current, deadline, None)
    assert keys(attend) == ["attend-4"] and attend[0].title == "4차는 고용센터 출석 회차예요"
    missed = round_(3, date(2026, 10, 14), status=RoundStatus.CLOSED)
    assert keys(account_notices(procedure(), current, deadline, missed)) == ["overdue-2026-10-14"]
