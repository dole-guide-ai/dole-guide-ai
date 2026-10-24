import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.agent import gateway
from app.core.config import get_settings
from evals.golden.report import Report

SCENARIO_DIR = Path(__file__).parent / "scenarios"


def load_scenarios(area: str) -> list[dict[str, Any]]:
    """scenarios/<area>/*.json을 읽어 pytest parametrize에 넘길 목록을 만듭니다."""
    return [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted((SCENARIO_DIR / area).glob("*.json"))
    ]


@pytest.fixture
def requires_llm() -> None:
    """실제 LLM을 호출하는 평가에서 사용합니다. API 키가 없으면 건너뜁니다."""
    if not get_settings().has_llm_key():
        pytest.skip("모델 공급자 키가 없어 실제 모델 평가를 건너뜁니다.")


@pytest.fixture(scope="session", autouse=True)
def eval_tracing() -> None:
    """실제 모델 평가는 서버와 같은 .env 설정으로 LangSmith에 트레이스를 남깁니다.

    루트 conftest가 테스트용으로 끈 값을 지우고 설정을 다시 읽습니다.
    import 때가 아니라 evals 테스트가 실제로 돌 때만 하므로, tests/와 같이 실행해도
    tests/ 쪽에는 트레이스가 켜지지 않습니다.
    """
    os.environ.pop("LANGSMITH_TRACING", None)
    get_settings.cache_clear()
    gateway.configure_tracing()


# ── 골든셋 (evals/test_golden.py) ──
GOLDEN_REPORT = pytest.StashKey["Report"]()


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("golden", "골든셋")
    group.addoption(
        "--golden-agent",
        choices=["real", "selftest", "broken"],
        default="real",
        help="real: 실제 AI · selftest: 채점 코드 점검(모두 통과해야 정상) · broken: 일부러 틀리기",
    )
    group.addoption(
        "--golden-area",
        choices=["all", "procedure", "form_fill", "grounding", "masking"],
        default="all",
        help="이 영역만 실행",
    )
    group.addoption("--golden-threshold", type=float, default=0.7, help="LLM 판정 통과 점수(0~1)")
    group.addoption(
        "--golden-judge",
        choices=["on", "off"],
        default="on",
        help="off: LLM 판정을 건너뛰고 정답 비교만 (고치는 중 빠르고 싸게 확인할 때)",
    )


@pytest.fixture(scope="session")
def golden_options(request: pytest.FixtureRequest) -> SimpleNamespace:
    get = request.config.getoption
    return SimpleNamespace(
        agent=get("--golden-agent"),
        area=get("--golden-area"),
        threshold=get("--golden-threshold"),
        judge=get("--golden-judge") == "on",
    )


@pytest.fixture(scope="session")
def golden_report(request: pytest.FixtureRequest) -> Report:
    report = Report(mode=request.config.getoption("--golden-agent"))
    request.config.stash[GOLDEN_REPORT] = report
    return report


def pytest_terminal_summary(terminalreporter, config: pytest.Config) -> None:
    report = config.stash.get(GOLDEN_REPORT, None)
    if report and report.records:
        path = report.write()
        counts = ", ".join(f"{name} {n}" for name, n in report.counts().most_common())
        terminalreporter.write_line(f"골든셋: {counts}")
        terminalreporter.write_line(f"보고서: {path}")
