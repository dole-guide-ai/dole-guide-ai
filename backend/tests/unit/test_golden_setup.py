"""골든셋 러너의 시작 상태 점검(evals/golden/runner.setup_problems).

문항 고장(seed가 안 들어감 등)을 AI 실패와 가릅니다.
"""

from copy import deepcopy

from evals.golden.presets import resolve_input
from evals.golden.runner import setup_problems


def _case(persona: str, state: dict) -> dict:
    return resolve_input(
        {"persona": persona, "state": state, "activities": None, "messages": ["x"], "files": []}
    )


def _initial(case_input: dict) -> dict:
    """문항 의도대로 들어간 계정의 대화 전 데이터."""
    return {
        "resume": deepcopy(case_input["data"]["resume"]),
        "activities": deepcopy(case_input["data"]["activities"]),
        "procedure": {"stage": case_input["state"]["stage"], "education_done": False},
    }


def test_matching_start_state_has_no_problem() -> None:
    case_input = _case("park", {"seed": "park_almost"})

    assert setup_problems(case_input, _initial(case_input)) == []


def test_dropped_seed_resume_is_reported() -> None:
    # 박진수 seed 문항 9개가 시작 이력서 없이 채점되던 문제(#257)를 잡는지
    case_input = _case("park", {"seed": "park_career"})
    initial = _initial(case_input)
    initial["resume"]["competencies"] = {"careers": [], "certifications": []}

    problems = setup_problems(case_input, initial)

    assert "시작 경력 1개를 넣었는데 계정에는 0개" in problems
    assert "시작 자격증 1개를 넣었는데 계정에는 0개" in problems


def test_missing_activities_and_wrong_stage_are_reported() -> None:
    case_input = _case("lee", {})
    initial = _initial(case_input)
    initial["activities"] = []
    initial["procedure"]["stage"] = "education"

    problems = setup_problems(case_input, initial)

    assert "시작 활동 2개를 넣었는데 계정에는 0개" in problems
    assert "단계가 recognition이어야 하는데 education" in problems
