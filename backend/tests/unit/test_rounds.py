"""회차 점검 `check_round` — 상세기획 2-2.12 평가 시나리오 round-001~009와 이정호 계산 예."""

from datetime import date

from app.rules.application import ActivityInput
from app.rules.rounds import check_round
from app.schemas.rounds import ActivityStatus, CheckStatus, WarningId

# 이정호 4차 (상세기획 2-2.6): 대상기간 2026-11-25 ~ 2026-12-22, 기준일 2026-12-16
START, END, TODAY = date(2026, 11, 25), date(2026, 12, 22), date(2026, 12, 16)


def act(
    activity_id: str,
    day: date,
    kind: str = "job_application",
    route: str | None = "work24",
    org: str | None = "OO물류",
    **extra,
) -> ActivityInput:
    category = "job_search" if kind in ("job_application", "interview") else "non_job_search"
    return ActivityInput(
        activity_id=activity_id,
        activity_date=day,
        category=category,
        kind=kind,
        route=route,
        org_name=org,
        **extra,
    )


def check(activities, *, round_no=4, group="general", history=(), standard=True, today=TODAY):
    return check_round(
        round_no=round_no,
        group=group,
        period_start=START,
        period_end=END,
        standard_period=standard,
        activities=list(activities),
        history=list(history),
        today=today,
    )


def statuses(result) -> dict[str, ActivityStatus]:
    return {a.activity_id: a.status for a in result.activities}


def warning_ids(result) -> list[WarningId]:
    return [w.id for w in result.warnings]


def test_lee_before_recording_counts_one_and_needs_one_more():
    """round-001: 같은 날 구직 2건 → 대표 OO물류(고용24, 증빙 불필요), OO상사는 같은 날."""
    result = check(
        [
            act("a1", date(2026, 12, 8)),
            act("a2", date(2026, 12, 8), route="company_site", org="OO상사"),
        ]
    )

    assert statuses(result) == {"a1": ActivityStatus.COUNTED, "a2": ActivityStatus.SAME_DAY}
    assert (result.required, result.required_job_search) == (2, 1)
    assert (result.counted, result.counted_job_search) == (1, 1)
    assert result.check_status == CheckStatus.SHORT
    assert result.remaining == 1
    assert WarningId.SAME_DAY in warning_ids(result)


def test_same_day_prefers_activity_with_evidence_over_record_order():
    """대표 순서: 구직활동 > 구직 외 > 증빙 갖춤 > 먼저 기록 (2-2.6 5단계)."""
    result = check(
        [
            act("a1", date(2026, 12, 8), route="company_site", org="OO상사"),
            act("a2", date(2026, 12, 8), route="email", org="OO유통", file_ids=("f1",)),
        ]
    )

    assert statuses(result) == {"a1": ActivityStatus.SAME_DAY, "a2": ActivityStatus.COUNTED}


def test_activity_before_period_is_out_of_period():
    """round-002: 대상기간 전날 활동 → out_of_period, W2."""
    result = check([act("a1", date(2026, 11, 24))])

    assert statuses(result)["a1"] == ActivityStatus.OUT_OF_PERIOD
    assert result.counted == 0
    assert WarningId.OUT_OF_PERIOD in warning_ids(result)


def test_two_lectures_fill_total_but_not_job_search():
    """round-003: 4차 일반, 특강 2건(다른 날) → 건수 충족·구직 미충족, W6."""
    result = check(
        [
            act("l1", date(2026, 12, 1), kind="lecture", route="step_online", org=None),
            act("l2", date(2026, 12, 2), kind="lecture", route="step_online", org=None),
        ]
    )

    assert (result.counted, result.counted_job_search) == (2, 0)
    assert result.check_status == CheckStatus.SHORT
    assert result.remaining_job_search == 1
    assert WarningId.NO_JOB_SEARCH in warning_ids(result)


def test_third_lecture_over_whole_benefit_period_is_limit_over():
    """round-004: 특강 누적 3번째 → limit_over, W4."""
    history = [
        act("h1", date(2026, 10, 1), kind="lecture", route="step_online", org=None),
        act("h2", date(2026, 10, 20), kind="lecture", route="step_online", org=None),
    ]
    result = check(
        [act("l3", date(2026, 12, 1), kind="lecture", route="step_online", org=None)],
        history=history,
    )

    assert statuses(result)["l3"] == ActivityStatus.LIMIT_OVER
    assert WarningId.LIMIT_OVER in warning_ids(result)
    assert result.limits_used.lecture == 2


def test_general_round_8_counts_job_search_every_7_days():
    """round-005: 일반 8차부터는 대상기간 시작일부터 7일씩 나눠 주마다 구직활동 1건 (설계 6.2)."""
    result = check(
        [act("a1", date(2026, 11, 26)), act("a2", date(2026, 12, 3), org="OO유통")],
        round_no=8,
    )

    assert len(result.weeks) == 4
    assert [w.job_search for w in result.weeks] == [1, 1, 0, 0]
    assert (result.required_job_search, result.counted_job_search) == (4, 2)
    assert result.check_status == CheckStatus.SHORT


def test_general_round_8_rejects_non_job_search():
    result = check(
        [act("l1", date(2026, 12, 1), kind="lecture", route="step_online", org=None)],
        round_no=8,
    )

    assert statuses(result)["l1"] == ActivityStatus.NOT_ALLOWED


def test_lee_after_recording_is_satisfied():
    """round-006: 이정호 seed + 12.16 고용24 지원 → 충족, 인정 2 (구직 2)."""
    result = check(
        [
            act("a1", date(2026, 12, 8)),
            act("a2", date(2026, 12, 8), route="company_site", org="OO상사"),
            act("a3", date(2026, 12, 16), org="OO물산"),
        ]
    )

    assert (result.counted, result.counted_job_search) == (2, 2)
    assert result.check_status == CheckStatus.SATISFIED


def test_activity_on_recognition_day_is_counted():
    """round-007: 인정일(12.22) 당일 활동도 기간 안 (CHECK-011)."""
    result = check([act("a1", END)], today=END)

    assert statuses(result)["a1"] == ActivityStatus.COUNTED


def test_training_hours_are_summed_across_courses():
    """round-008: 직업훈련 두 과정 10시간 + 8시간 = 18시간 → 구직활동 1회로 환산."""
    result = check(
        [
            act("t1", date(2026, 12, 1), kind="training", route="training", org="A", hours=10),
            act("t2", date(2026, 12, 2), kind="training", route="training", org="B", hours=8),
        ]
    )

    assert (result.counted, result.counted_job_search) == (1, 1)
    assert statuses(result) == {"t1": ActivityStatus.COUNTED, "t2": ActivityStatus.COUNTED}


def test_training_over_30_hours_fills_the_round():
    result = check(
        [act("t1", date(2026, 12, 1), kind="training", route="training", org="A", hours=30)]
    )

    assert result.check_status == CheckStatus.SATISFIED


def test_unknown_course_is_needs_check_and_not_counted():
    """round-009: 규칙표에 기준이 없는 과정 → needs_check, 인정 건수 제외."""
    result = check([act("x1", date(2026, 12, 1), kind="job_request_upgrade", route=None, org=None)])

    assert statuses(result)["x1"] == ActivityStatus.NEEDS_CHECK
    assert result.counted == 0


def test_changed_recognition_date_needs_check():
    """대상기간이 28일이 아니면(인정일 변경) 필요 건수를 확인 필요로 둡니다 (DUE-091)."""
    result = check([act("a1", date(2026, 12, 8))], standard=False)

    assert result.check_status == CheckStatus.NEEDS_CHECK


def test_future_activity_is_planned():
    result = check([act("a1", date(2026, 12, 20))])

    assert statuses(result)["a1"] == ActivityStatus.PLANNED
    assert result.counted == 0


def test_missing_evidence_warns_w5():
    result = check([act("a1", date(2026, 12, 8), route="company_site", org="OO상사")])

    w5 = next(w for w in result.warnings if w.id == WarningId.NO_EVIDENCE)
    assert w5.activity_ids == ["a1"]
    assert "채용공고" in w5.message


def test_same_company_twice_warns_w3():
    result = check(
        [act("a1", date(2026, 12, 1), org="OO상사"), act("a2", date(2026, 12, 9), org="OO 상사")]
    )

    assert WarningId.SAME_COMPANY in warning_ids(result)


def test_age_60_64_needs_one_activity_from_round_4():
    result = check(
        [act("l1", date(2026, 12, 1), kind="lecture", route="step_online", org=None)],
        group="age_60_64",
    )

    assert (result.required, result.required_job_search) == (1, 0)
    assert result.check_status == CheckStatus.SATISFIED


def test_volunteer_is_not_allowed_for_general():
    result = check([act("v1", date(2026, 12, 1), kind="volunteer", route=None, org=None)])

    assert statuses(result)["v1"] == ActivityStatus.NOT_ALLOWED


def test_repeat_recipient_needs_one_activity_every_two_weeks():
    """반복수급자는 2주에 1회 (1350 의무 횟수 2026-10-15 답변, 팀 결정 2026-10-24).

    대상기간 11.25~12.22(28일)를 14일씩 나눈 두 조각에 각각 1건이 있어야 합니다.
    """
    first_half = check([act("a1", date(2026, 12, 1))], group="repeat")
    both_halves = check(
        [act("a1", date(2026, 12, 1)), act("a2", date(2026, 12, 15))], group="repeat"
    )

    assert (first_half.required, first_half.counted) == (2, 1)
    assert first_half.check_status == CheckStatus.SHORT
    assert (both_halves.required, both_halves.counted) == (2, 2)
    assert both_halves.check_status == CheckStatus.SATISFIED


def test_repeat_recipient_counts_job_search_only_from_round_3():
    lecture = act("a1", date(2026, 12, 1), kind="lecture", route="step_online")

    round_2 = check([lecture], round_no=2, group="repeat")
    round_3 = check([lecture], round_no=3, group="repeat")

    assert round_2.activities[0].status == ActivityStatus.COUNTED
    assert round_3.activities[0].status == ActivityStatus.NOT_ALLOWED


def test_repeat_recipient_round_3_counts_job_search_slices():
    """코드래빗 지적: 구직활동만 인정되는 회차에 구직활동 건수가 0으로 나오던 문제."""
    result = check(
        [act("a1", date(2026, 12, 1)), act("a2", date(2026, 12, 15))], round_no=3, group="repeat"
    )

    assert (result.required_job_search, result.counted_job_search) == (2, 2)
    assert result.check_status == CheckStatus.SATISFIED


def test_repeat_recipient_counts_accepted_training_in_its_slice():
    """코드래빗 지적: 인정된 직업훈련이 14일 조각 계산에서 빠지던 문제."""
    result = check(
        [
            act("a1", date(2026, 12, 1)),
            act("t1", date(2026, 12, 15), kind="training", route="training", org="A", hours=20),
        ],
        round_no=2,
        group="repeat",
    )

    assert (result.required, result.counted) == (2, 2)
