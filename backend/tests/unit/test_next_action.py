"""다음 할 일(rules/next_action.py)과 done 이벤트 조립(nodes/finish.py)."""

from datetime import date, datetime, time

import pytest
from langchain_core.messages import AIMessage

from app.agent.nodes.finish import done_event
from app.agent.nodes.panel import _failure
from app.core.clock import KST
from app.core.errors import ConflictError
from app.rules.next_action import NextAction, next_action


@pytest.mark.parametrize(
    ("stage", "expected"),
    [
        ("job_registration", NextAction.WRITE_RESUME),
        ("education", NextAction.COMPLETE_EDUCATION),
        ("eligibility_application", NextAction.PREPARE_ELIGIBILITY),
        ("eligibility_applied", NextAction.ENTER_RECOGNITION_DATE),
    ],
)
def test_next_action_by_stage(stage: str, expected: NextAction) -> None:
    assert next_action(stage, None) == expected


def test_saved_resume_after_separation_points_to_education() -> None:
    # 골든셋 P-042: 이력서를 다 썼으면 이력서 쓰기가 아니라 교육 (화면 안내 E6과 같은 기준)
    assert next_action("job_registration", None, resume_ready=True) == (
        NextAction.COMPLETE_EDUCATION
    )
    # 이직 전에 저장한 예전 이력서(최영수)는 고쳐야 하므로 그대로 이력서 쓰기
    assert next_action("job_registration", None, resume_ready=False) == NextAction.WRITE_RESUME


def test_finished_education_points_to_eligibility() -> None:
    # 골든셋 P-044: 교육을 이수했으면 수급자격 신청 준비
    assert next_action("education", None, education_done=True) == NextAction.PREPARE_ELIGIBILITY
    assert next_action("education", None, education_done=False) == NextAction.COMPLETE_EDUCATION


@pytest.mark.parametrize(
    ("round_facts", "expected"),
    [
        ({"remaining": 1, "remaining_job_search": 0, "d_day": 6}, NextAction.ADD_ACTIVITY),
        (
            {"remaining": 1, "remaining_job_search": 1, "d_day": 6},
            NextAction.ADD_JOB_SEARCH_ACTIVITY,
        ),
        ({"remaining": 0, "remaining_job_search": 0, "d_day": 0}, NextAction.SUBMIT_BY_SELF),
        ({"remaining": 0, "remaining_job_search": 0, "d_day": 3}, NextAction.REVIEW_FORM),
    ],
)
def test_next_action_in_recognition(round_facts: dict, expected: NextAction) -> None:
    assert next_action("recognition", round_facts) == expected


RECOGNITION_DAY = date(2026, 10, 27)


def _on_recognition_day(**overrides: object) -> dict:
    return {
        "remaining": 0,
        "remaining_job_search": 0,
        "d_day": 0,
        "recognition_date": RECOGNITION_DAY.isoformat(),
        "attendance_required": False,
    } | overrides


@pytest.mark.parametrize(
    ("hour", "minute", "round_facts", "expected"),
    [
        # 골든셋 P-017·P-018: 인정일 당일 마감 전후로 할 일이 바뀝니다(17시 인터넷·18시 방문).
        (16, 50, _on_recognition_day(), NextAction.SUBMIT_BY_SELF),
        (17, 20, _on_recognition_day(), NextAction.VISIT_CENTER_TODAY),
        (18, 30, _on_recognition_day(), NextAction.CONTACT_CENTER),
        # 출석 회차는 시각과 관계없이 오늘 센터에 갑니다(18시 뒤는 마감 지남).
        (10, 0, _on_recognition_day(attendance_required=True), NextAction.ATTEND_CENTER),
        # 활동이 모자라도 인터넷 마감이 지났으면 오늘 센터 방문이 먼저입니다.
        (17, 20, _on_recognition_day(remaining=1), NextAction.VISIT_CENTER_TODAY),
        (10, 0, _on_recognition_day(remaining=1), NextAction.ADD_ACTIVITY),
    ],
)
def test_recognition_day_follows_the_clock(
    hour: int, minute: int, round_facts: dict, expected: NextAction
) -> None:
    now = datetime.combine(RECOGNITION_DAY, time(hour, minute), KST)

    assert next_action("recognition", round_facts, now=now) == expected


def test_uncountable_round_asks_for_activities_instead_of_crashing() -> None:
    # 필요 건수를 셀 수 없는 회차(반복수급자 등)는 remaining이 None입니다(nodes/context).
    facts = {"remaining": None, "remaining_job_search": None, "d_day": 5}

    assert next_action("recognition", facts) == NextAction.ADD_ACTIVITY


def test_done_event_has_cite_from_used_rules_and_next_action() -> None:
    state = {
        "messages": [AIMessage("합성 답")],
        "cited": ["DUE-093"],
        "facts": {"stage": "job_registration"},
    }

    done = done_event(state)

    assert done.cite == "취업드림수첩(2025년판 PDF)"
    assert done.rule_refs == ["DUE-093"]
    assert done.next_action == "write_resume"


def test_service_error_becomes_reason_for_model_not_crash() -> None:
    """지난 회차 활동처럼 서비스가 거절해도 턴을 끝내지 않고 사유를 모델에 돌려줍니다."""
    reason = _failure(ConflictError(message="지난 회차 활동은 넣거나 뺄 수 없어요."))

    assert reason == "도구를 쓰지 못했어요: 지난 회차 활동은 넣거나 뺄 수 없어요."
