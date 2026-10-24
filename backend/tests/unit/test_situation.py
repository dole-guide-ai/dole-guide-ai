from app.rules import situation
from app.schemas.rounds import ActivityStatus

LEE = {
    "age_at_separation": 58,
    "has_disability": False,
    "recipient_type": "general",
    "stage": "recognition",
    "eligibility_applied_date": "2026-09-15",
    "completed_rounds": 3,
    "last_recognition_date": "2026-11-24",
    "next_recognition_date": "2026-12-22",
    "demo_today": "2026-12-16",
}
# 시연 데이터의 옛 종류 이름(job_search)도 입사지원으로 읽습니다.
SAME_DAY = [
    {"date": "2026-12-08", "kind": "job_search", "route": "work24"},
    {"date": "2026-12-08", "kind": "job_search", "route": "company_site"},
]


def test_derive_fourth_round_needs_two_activities() -> None:
    derived = situation.derive(LEE)

    assert derived["current_round"] == 4
    assert (derived["required"], derived["required_job_search"]) == (2, 1)
    assert derived["period"] == {"start": "2026-11-25", "end": "2026-12-22"}
    assert derived["is_attendance_round"] is True
    assert derived["d_day"] == 6


def test_derive_before_recognition_has_no_round() -> None:
    derived = situation.derive({**LEE, "stage": "job_registration", "age_at_separation": 65})

    assert derived["current_round"] is None
    assert derived["can_presubmit_online"] is False
    assert derived["rule_group"] == "age65_or_disabled"


def test_same_day_activities_count_once() -> None:
    check, statuses = situation.check_round(LEE, situation.derive(LEE), SAME_DAY)

    assert (check["counted"], check["shortfall"]) == (1, 1)
    assert sorted(statuses) == [ActivityStatus.COUNTED, ActivityStatus.SAME_DAY]
    assert check["same_day_messages"]


def test_activity_outside_period_is_not_counted() -> None:
    late = situation.complete_activity(
        {"date": "2026-11-20", "kind": "job_application", "route": "company_site"}
    )
    check, statuses = situation.check_round(LEE, situation.derive(LEE), [*SAME_DAY, late])

    assert late["category"] == "입사지원"
    assert "채용공고" in late["evidence"]["required"]
    assert statuses[-1] == ActivityStatus.OUT_OF_PERIOD
    assert check["counted"] == 1


def test_unknown_group_has_no_shortfall() -> None:
    repeat = {**LEE, "recipient_type": "repeat"}

    check, _ = situation.check_round(repeat, situation.derive(repeat), SAME_DAY)

    assert check["required"] is None
    assert check["shortfall"] is None
