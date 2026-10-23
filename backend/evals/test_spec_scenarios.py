"""상세기획 평가 시나리오 자동 검증 (N-12).

`scenarios/spec/<영역>/<ID>.json` 하나가 상세기획 표의 시나리오 하나입니다
(이력서 2-1.9, 회차 2-2.12, 신청서 2-3.10). 규칙으로 정답이 정해지는 시나리오는
규칙 함수로 바로 채점하고(LLM 호출 없음), 아직 돌릴 수 없는 시나리오는 `pending`에
이유(필요한 기능)를 적어 두고 건너뜁니다.
"""

import json
from typing import Any

import pytest

from evals.conftest import SCENARIO_DIR
from evals.spec_rules import RuleNotReadyError, run_rule

pytestmark = pytest.mark.eval

SPEC_DIR = SCENARIO_DIR / "spec"


def _load() -> list[dict[str, Any]]:
    return [
        json.loads(path.read_text(encoding="utf-8")) for path in sorted(SPEC_DIR.rglob("*.json"))
    ]


SCENARIOS = _load()


def test_ids_are_unique_and_match_files() -> None:
    ids = [scenario["id"] for scenario in SCENARIOS]
    assert len(ids) == len(set(ids))
    for path in SPEC_DIR.rglob("*.json"):
        scenario = json.loads(path.read_text(encoding="utf-8"))
        assert f"{path.parent.name}/{path.stem}" == scenario["id"], path


def test_spec_scenarios_cover_plan_tables() -> None:
    """상세기획 표의 시나리오 ID가 빠짐없이 있는지 봅니다 (이력서 10 · 회차 9 · 신청서 11)."""
    ids = {scenario["id"].split("/")[1] for scenario in SCENARIOS}
    expected = (
        {f"resume-{n:03d}" for n in range(1, 11)}
        | {f"round-{n:03d}" for n in range(1, 10)}
        | {f"form-{n:03d}" for n in range(1, 12)}
    )
    assert expected <= ids, sorted(expected - ids)


def _matches(actual: Any, expected: Any) -> bool:
    """expected에 적은 키만 비교합니다. 튜플은 JSON 목록과 같게 봅니다."""
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and _matches(actual[key], value) for key, value in expected.items()
        )
    if isinstance(actual, tuple | list) and isinstance(expected, list):
        return len(actual) == len(expected) and all(
            _matches(a, e) for a, e in zip(actual, expected, strict=True)
        )
    return actual == expected


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s["id"])
def test_spec_scenario(scenario: dict[str, Any]) -> None:
    if "pending" in scenario:
        pytest.skip(f"준비 전: {scenario['pending']}")
    try:
        actual = run_rule(scenario["rule"], scenario["args"])
    except RuleNotReadyError as error:
        pytest.skip(f"규칙 함수 준비 전: {error}")

    assert _matches(actual, scenario["expected"]), (
        f"{scenario['id']} ({scenario['description']})\n"
        f"기대: {scenario['expected']}\n실제: {actual}"
    )
