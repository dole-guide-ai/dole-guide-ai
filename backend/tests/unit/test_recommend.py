"""부족한 활동 추천 규칙 (F-19, 상세기획 2-2.8)."""

from datetime import date

from app.rules.recommend import (
    deadline_text,
    is_weekly_job_search,
    parse_recommendation_id,
    planned_date,
    recommend_activities,
    recommendation_id,
)
from app.schemas.rounds import LimitsUsed


def _keys(**kwargs) -> list[str]:
    base = {
        "shortfall": 1,
        "shortfall_job_search": 0,
        "group": "general",
        "round_no": 4,
        "limits_used": LimitsUsed(),
        "desired_occupation": "일반 사무",
    }
    return [r.candidate.key for r in recommend_activities(**{**base, **kwargs})]


def test_lee_example_order_is_easy_evidence_first() -> None:
    """이정호 예시: 부족 1건(구직활동 부족 0) → 고용24 입사지원, 온라인 특강, 면접."""
    picks = recommend_activities(
        shortfall=1,
        shortfall_job_search=0,
        group="general",
        round_no=4,
        limits_used=LimitsUsed(lecture=0),
        desired_occupation="일반 사무",
    )

    assert [p.candidate.key for p in picks] == ["work24_apply", "step_lecture", "interview"]
    assert picks[0].title == "입사지원 (고용24) — 희망 직종 ‘일반 사무’ 공고"
    assert picks[0].reason == "구직활동 · 증빙 불필요"
    assert picks[1].reason == "구직 외 활동 · 증빙 불필요 · 한도 2회 중 0회 사용"
    assert picks[2].reason == "구직활동 · 증빙 면접확인서 + 명함"


def test_no_shortfall_means_no_recommendation() -> None:
    assert _keys(shortfall=0, shortfall_job_search=0) == []


def test_job_search_shortfall_puts_job_search_first() -> None:
    """특강만 2건이라 구직활동이 모자라면(round-003) 구직활동 후보가 위로 갑니다."""
    assert _keys(shortfall=0, shortfall_job_search=1, limits_used=LimitsUsed(lecture=1)) == [
        "work24_apply",
        "interview",
        "company_site_apply",
    ]


def test_non_job_search_gets_note_when_job_search_is_short() -> None:
    picks = recommend_activities(
        shortfall=1,
        shortfall_job_search=1,
        group="age_60_64",
        round_no=4,
        limits_used=LimitsUsed(lecture=0),
        desired_occupation=None,
    )

    assert picks[0].title == "입사지원 (고용24)"
    assert all(p.candidate.category == "job_search" for p in picks)
    lecture = next(
        p
        for p in recommend_activities(
            shortfall=5,
            shortfall_job_search=1,
            group="age_60_64",
            round_no=4,
            limits_used=LimitsUsed(lecture=0),
            desired_occupation=None,
        )
        if p.candidate.key == "work24_apply"
    )
    assert "구직활동 1건은 따로" not in lecture.reason


def test_lecture_limit_and_round_8_rules() -> None:
    assert "step_lecture" not in _keys(limits_used=LimitsUsed(lecture=2))
    # general 8차부터는 구직활동만 인정 (ACT-030)
    assert _keys(round_no=8) == ["work24_apply", "interview", "company_site_apply"]
    assert "step_lecture" in _keys(round_no=8, group="age65_or_disabled")
    # 반복수급자는 지원하지 않아 추천하지 않습니다 (설계 6.1)
    assert _keys(round_no=8, group="repeat") == []


def test_recommendation_id_round_trip() -> None:
    value = recommendation_id(4, "step_lecture")

    assert value == "rec_4_step_lecture"
    parsed = parse_recommendation_id(value)
    assert parsed is not None
    round_no, candidate = parsed
    assert (round_no, candidate.kind, candidate.route) == (4, "lecture", "step_online")
    assert parse_recommendation_id("rec_x_step_lecture") is None
    assert parse_recommendation_id("rec_4_unknown") is None
    assert parse_recommendation_id("rec_²_work24_apply") is None
    assert parse_recommendation_id("rec_" + "9" * 5000 + "_work24_apply") is None


def test_deadline_is_day_before_recognition_and_avoids_busy_days() -> None:
    """인정일 당일도 인정되지만 권장 기한은 전날까지 (round-007)."""
    text = deadline_text(date(2026, 12, 22), [date(2026, 12, 8), date(2026, 12, 8)])

    assert text == (
        "12.21(월)까지 해 두세요. 이미 활동이 있는 날(12.8(화))은 하루 1건만 인정되니 피해 주세요."
    )
    assert deadline_text(date(2026, 12, 22), []) == "12.21(월)까지 해 두세요."


def test_weekly_rounds_always_recommend_job_search() -> None:
    """일반 8차부터는 7일마다 구직활동 1건 (설계 6.2)."""
    assert is_weekly_job_search("general", 8) is True
    assert is_weekly_job_search("repeat", 9) is False
    assert is_weekly_job_search("general", 7) is False
    assert is_weekly_job_search("age65_or_disabled", 8) is False
    assert deadline_text(date(2027, 6, 1), [], weekly=True).endswith(
        "8차부터는 대상기간 시작일부터 7일마다 구직활동 1건이 필요해요."
    )


def test_planned_date_is_day_before_recognition_or_today() -> None:
    assert planned_date(date(2026, 12, 22), date(2026, 12, 16)) == date(2026, 12, 21)
    # 인정일 당일에는 전날이 지났으므로 오늘
    assert planned_date(date(2026, 12, 22), date(2026, 12, 22)) == date(2026, 12, 22)


def test_already_planned_candidates_are_not_recommended_again() -> None:
    assert _keys(planned=frozenset({("job_application", "work24")})) == [
        "step_lecture",
        "interview",
        "company_site_apply",
    ]


def test_non_job_search_note_when_job_search_is_still_needed() -> None:
    """구직활동 후보를 다 넣었으면 남은 구직 외 후보에 '구직활동 1건은 따로' 안내를 붙입니다."""
    planned = frozenset(
        {
            ("job_application", "work24"),
            ("interview", "interview"),
            ("job_application", "company_site"),
        }
    )
    picks = recommend_activities(
        shortfall=1,
        shortfall_job_search=1,
        group="general",
        round_no=4,
        limits_used=LimitsUsed(lecture=0),
        desired_occupation=None,
        planned=planned,
    )

    assert [p.candidate.key for p in picks] == ["step_lecture", "training"]
    assert all("구직활동 1건은 따로 필요해요" in p.reason for p in picks)
