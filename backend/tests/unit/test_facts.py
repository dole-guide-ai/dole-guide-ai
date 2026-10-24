from app.rules import situation
from app.rules.facts import CITE_EVIDENCE, build_facts, recorded_count_text

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
    "demo_time": "10:00",
}
SAME_DAY = [
    {"date": "2026-12-08", "kind": "job_search"},
    {"date": "2026-12-08", "kind": "job_search"},
]


def _facts(state: dict, activities: list) -> list[dict[str, str]]:
    derived = situation.derive(state)
    check = None
    if derived["current_round"]:
        check, _ = situation.check_round(state, derived, activities)
    return build_facts(state, derived, check)


def test_round_facts_state_numbers_dates_and_same_day_rule() -> None:
    texts = " ".join(f["text"] for f in _facts(LEE, SAME_DAY))

    assert "12월 22일(화)" in texts
    assert "2건(그중 구직활동 1건)" in texts
    assert "1건 더" in texts
    assert "다른 날" in texts
    assert "출석" in texts
    assert any(f["cite"] == CITE_EVIDENCE for f in _facts(LEE, SAME_DAY))


def test_submit_window_after_five_pm_on_recognition_day() -> None:
    state = {**LEE, "completed_rounds": 4, "demo_today": "2026-12-22", "demo_time": "17:30"}

    texts = " ".join(f["text"] for f in _facts(state, []))

    assert "17시가 지나" in texts


def test_repeat_recipient_fact_says_every_two_weeks() -> None:
    texts = " ".join(f["text"] for f in _facts({**LEE, "recipient_type": "repeat"}, []))

    assert "2주(14일)마다 구직활동을 1건씩" in texts
    assert "2건 더" in texts
    assert "채웠어요" not in texts


def test_presubmit_depends_on_age_at_separation() -> None:
    before = {**LEE, "stage": "eligibility_application", "next_recognition_date": None}

    assert "대상이 될 수" in _facts({**before, "age_at_separation": 64}, [])[0]["text"]
    assert "방문" in _facts({**before, "age_at_separation": 65}, [])[0]["text"]


def test_recorded_count_text_states_counts_after_recording() -> None:
    derived = situation.derive(LEE)
    one = [{"date": "2026-12-01", "kind": "job_application", "route": "work24"}]
    check, _ = situation.check_round(LEE, derived, one)

    text = recorded_count_text(check)

    assert text is not None
    assert "인정된 활동은 1건" in text
    assert "1건 더" in text
    assert recorded_count_text(None) is None
