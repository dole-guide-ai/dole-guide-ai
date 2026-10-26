"""다음 할 일(rules/next_action.py)과 done 이벤트 조립(nodes/finish.py)."""

import pytest
from langchain_core.messages import AIMessage

from app.agent.nodes.finish import done_event
from app.agent.nodes.panel import _failure
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
