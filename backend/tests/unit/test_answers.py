"""신청서 본인 답변 규칙 (F-24·F-25, 설계 6.7·6.8)."""

from app.rules.answers import (
    answer_error,
    blocked_by_lock,
    conflict_paths,
    credit_applicable,
    department_only,
)
from app.rules.application import apply_credit_rule, checklist


def field(value, status="confirmed"):
    return {"value": value, "status": status, "source": "user_answer"}


def test_choices_follow_design_keys():
    assert answer_error("/work/has_work", "yes", {}, 58) is None
    assert answer_error("/work/has_work", "네", {}, 58) == "choice"
    assert answer_error("/privacy_consent", "agree_all", {}, 58) is None


def test_credit_details_only_when_wished():
    wished = {"credit": {"application": field("wish")}}
    assert answer_error("/credit/notice_method", "electronic", wished, 58) is None
    assert answer_error("/credit/notice_method", "electronic", {}, 58) == "required"


def test_age_60_or_more_has_no_credit():
    """F-24: 만 60세 이상은 실업크레딧 해당 없음. 다른 답은 받지 않습니다."""
    assert credit_applicable(59) and not credit_applicable(60)
    assert answer_error("/credit/application", "wish", {}, 67) == "choice"
    assert answer_error("/credit/application", "not_applicable", {}, 58) == "choice"
    data = apply_credit_rule({}, credit_applicable=False)
    assert data["credit"]["application"]["value"] == "not_applicable"


def test_started_on_only_when_employed():
    employed = {"employment": {"status": field("employed")}}
    assert answer_error("/employment/started_on", "2026-10-20", employed, 58) is None
    assert answer_error("/employment/started_on", "2026-10-20", {}, 58) == "required"
    assert answer_error("/employment/started_on", "10월 20일", employed, 58) == "date_format"


def test_locked_form_only_takes_employment_and_accident():
    assert blocked_by_lock("/credit/application", "employed")
    assert not blocked_by_lock("/employment/status", "employed")
    assert not blocked_by_lock("/credit/application", None)


def test_unsure_twice_blocks_submit():
    """'잘 모르겠어요'가 두 번이면 conflict로 남고 제출을 막습니다 (설계 6.8)."""
    data = {"work": {"has_work": field(None, "conflict")}}

    blocking, _ = checklist(data, [], remaining=0, remaining_job_search=0, evidence_missing=0)

    assert conflict_paths(data) == ["/work/has_work"]
    assert "unsure_answers" in [b["key"] for b in blocking]


def test_contact_keeps_department_only():
    """F-25: '김OO 과장님'이라고 해도 이름은 저장하지 않습니다."""
    assert department_only("김OO 과장님") is None
    assert department_only("이 대리") is None
    assert department_only("인사팀 김OO 과장님") == "인사팀"
    assert department_only("총무부") == "총무부"
