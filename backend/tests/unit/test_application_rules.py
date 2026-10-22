from datetime import date

from app.rules.application import (
    ActivityInput,
    apply_method_from_route,
    build_form_activities,
    carry_previous_answers,
    locked_reason,
    required_activities,
)

START, END = date(2026, 11, 25), date(2026, 12, 22)


def activity(no: int, day: date, **kw: object) -> ActivityInput:
    base = {"category": "job_search", "kind": "job_application", "org_name": f"OO{no}"}
    return ActivityInput(activity_id=f"a{no}", activity_date=day, **{**base, **kw})


def test_apply_method_mapping() -> None:
    """2-2 경로 → 고용24 응모 방식. 홈페이지·취업 사이트는 기타 (2-3.4)."""
    assert apply_method_from_route("work24") == "고용24(워크넷)"
    assert apply_method_from_route("email") == "전자메일"
    assert apply_method_from_route("company_site") == "기타"
    assert apply_method_from_route(None) is None


def test_only_recorded_activities_in_period_go_into_form() -> None:
    """완료 기준: 기록한 활동만 신청서에 들어가고, 같은 날 2건째는 참고로 뺍니다."""
    result = build_form_activities(
        [
            activity(1, date(2026, 12, 8), route="work24"),
            activity(2, date(2026, 12, 8), route="company_site"),
            activity(3, date(2026, 12, 15), route="company_site", org_name="OO기획"),
            activity(4, date(2026, 12, 17), planned=True),
            activity(5, date(2026, 11, 20)),
            activity(6, date(2026, 12, 14), category="other", kind="lecture", org_name="특강"),
        ],
        START,
        END,
    )

    assert [r["company_name"] for r in result.job_search] == ["OO1", "OO기획"]
    assert result.job_search[0]["application_method"] == "고용24(워크넷)"
    assert result.job_search[0]["job_search_method"] == "고용24(워크넷)"
    assert result.job_search[1]["application_method"] == "기타"
    assert result.job_search[1]["job_search_method"] is None
    assert [(e["activity_id"], e["reason"]) for e in result.excluded] == [("a2", "same_day")]
    assert [o["kind"] for o in result.other] == ["lecture"]


def test_previous_answers_fill_only_empty_fields() -> None:
    answered = {"value": "sms", "status": "confirmed", "source": "user_answer", "answered_on": "x"}
    previous = {"notification_method": answered, "credit": {"application": {"value": "wish"}}}
    data = {"notification_method": {"value": None}, "credit": {"application": {"value": None}}}

    merged = carry_previous_answers(data, previous)

    assert merged["notification_method"] == answered
    assert merged["credit"]["application"]["value"] == "wish"
    mine = {"notification_method": {"value": "email"}, "credit": {}}
    assert carry_previous_answers(mine, previous)["notification_method"]["value"] == "email"
    assert carry_previous_answers(data, None) is data


def test_locked_reason() -> None:
    assert locked_reason({}) is None
    assert locked_reason({"employment": {"status": {"value": "employed"}}}) == "employed"
    assert (
        locked_reason({"industrial_accident": {"receiving": {"value": "yes"}}})
        == "industrial_accident"
    )


def test_required_activities_by_group_and_round() -> None:
    assert required_activities("general", 1) == (1, 0)
    assert required_activities("general", 4) == (2, 1)
    assert required_activities("age65_or_disabled", 4) == (1, 0)
