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
        help="off: LLM 판정 없이 규칙 채점만(비교 실험용. 판정 포함 실행과 점수를 견주지 않음)",
    )
    group.addoption(
        "--golden-shard",
        default="1/1",
        help="i/n: 문항을 n조각으로 나눈 것 중 i번째만 실행. 여러 프로세스로 동시에 돌린 뒤 "
        "골든셋은 evals.golden.merge로, 인터뷰는 보고서 파일을 그대로 모아 봅니다",
    )


# 조각으로 나눠 동시에 돌릴 수 있는 평가
SHARDED_TESTS = frozenset({"test_golden", "test_interview"})


def _shard(config: pytest.Config) -> tuple[int, int]:
    index, total = (int(x) for x in config.getoption("--golden-shard").split("/"))
    if not 1 <= index <= total:
        raise pytest.UsageError("--golden-shard는 1/4처럼 1 이상 n 이하로 줍니다.")
    return index, total


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """골든셋·인터뷰 문항 중 이 조각에 해당하는 것만 남깁니다(문항 순서의 i번째마다)."""
    index, total = _shard(config)
    if total == 1:
        return
    golden = [item for item in items if item.originalname in SHARDED_TESTS]
    keep = {id(item) for n, item in enumerate(golden) if n % total == index - 1}
    deselected = [item for item in golden if id(item) not in keep]
    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = [item for item in items if id(item) not in {id(d) for d in deselected}]


def pytest_configure(config: pytest.Config) -> None:
    """LangSmith 실험은 실제 AI 실행만 남깁니다. selftest·broken은 올리지 않습니다."""
    if config.getoption("--golden-agent", default="real") != "real":
        os.environ["LANGSMITH_TEST_TRACKING"] = "false"


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
    get = request.config.getoption
    report = Report(
        mode=get("--golden-agent"), judge=get("--golden-judge"), shard=get("--golden-shard")
    )
    request.config.stash[GOLDEN_REPORT] = report
    return report


def pytest_terminal_summary(terminalreporter, config: pytest.Config) -> None:
    report = config.stash.get(GOLDEN_REPORT, None)
    if report and report.records:
        path = report.write()
        counts = ", ".join(f"{name} {n}" for name, n in report.counts().most_common())
        terminalreporter.write_line(f"골든셋: {counts}")
        terminalreporter.write_line(f"보고서: {path}")
