from datetime import date, datetime

from app.core.clock import KST
from app.rules.application import (
    ActivityInput,
    apply_method_from_route,
    build_form_activities,
    can_submit,
    carry_previous_answers,
    checklist,
    locked_reason,
    needs_evidence,
    required_activities,
    submit_mode,
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
    assert required_activities("repeat", 4) == (2, 1)


def kst(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=KST)


def test_submit_mode_by_time() -> None:
    """버튼 상태 5종: 인정일 전·당일 17시 전·17~18시·그 뒤·출석 회차 (설계 3.6, F-26)."""
    day = date(2026, 12, 22)
    assert submit_mode(kst(date(2026, 12, 21), 10), day, False) == "preview"
    assert submit_mode(kst(day, 16, 59), day, False) == "send"
    # 완료 기준: 온라인 회차 당일 17:30이면 방문 안내
    assert submit_mode(kst(day, 17, 30), day, False) == "visit_today"
    assert submit_mode(kst(day, 18), day, False) == "change"
    assert submit_mode(kst(date(2026, 12, 23), 9), day, False) == "change"
    assert submit_mode(kst(date(2026, 12, 21), 10), day, True) == "attend"
    assert submit_mode(kst(day, 18, 30), day, True) == "change"


def _answered(value: str) -> dict:
    return {"value": value, "status": "confirmed", "source": "user_answer"}


FULL = {
    "work": {"has_work": _answered("no")},
    "employment": {"status": _answered("none")},
    "industrial_accident": {"receiving": _answered("no")},
    "credit": {"application": _answered("wish")},
    "notification_method": _answered("sms"),
    "next_plan": _answered("job_search"),
}
ROW = {
    "company_name": "OO물류",
    "recruitment_contact": "인사팀",
    "recruitment_occupation": "일반 사무",
    "job_search_method": "고용24(워크넷)",
    "application_method": "고용24(워크넷)",
    "activity_result": "서류전형 심사진행 중",
}


def test_shortfall_and_missing_evidence_are_warnings_only() -> None:
    """완료 기준: 활동 1건 부족·증빙 없음은 경고만 나오고 제출은 가능합니다."""
    blocking, warnings = checklist(FULL, [ROW], counted=1, required=2, evidence_missing=1)

    assert blocking == []
    assert [w["key"] for w in warnings] == ["requirement_met", "evidence_ok"]
    assert can_submit("send", blocking, None) is True
    assert can_submit("visit_today", blocking, None) is False
    assert can_submit("preview", blocking, None) is False


def test_missing_self_answers_and_fields_block_submit() -> None:
    data = {**FULL, "work": {"has_work": {"value": None}}, "notification_method": {}}
    blocking, warnings = checklist(
        data, [{**ROW, "recruitment_contact": None}], counted=2, required=2, evidence_missing=0
    )

    assert [b["key"] for b in blocking] == ["self_answers", "job_search_fields", "notification"]
    assert warnings == []
    assert can_submit("attend", blocking, None) is False
    assert can_submit("send", [], "employed") is False


def test_evidence_needed_except_work24() -> None:
    assert needs_evidence("work24") is False
    assert needs_evidence("company_site") is True


def test_same_day_representative_prefers_work24_job_search() -> None:
    """같은 날 2건이면 기록 순서와 상관없이 구직활동·고용24(증빙 불필요)를 대표로 인정합니다."""
    day = date(2026, 12, 8)
    result = build_form_activities(
        [
            activity(2, day, route="company_site", org_name="OO상사"),
            activity(1, day, route="work24", org_name="OO물류"),
        ],
        START,
        END,
    )

    assert [r["company_name"] for r in result.job_search] == ["OO물류"]
    assert [e["company_name"] for e in result.excluded] == ["OO상사"]
