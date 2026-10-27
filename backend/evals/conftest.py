import json
import os
from collections.abc import Iterator
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


# 루트 conftest가 테스트에서만 끄는 설정(트레이스·재정렬). 평가에서는 .env·기본값을 씁니다.
TEST_ONLY_ENV = ("LANGSMITH_TRACING", "RETRIEVAL_RERANK")


@pytest.fixture(scope="package", autouse=True)
def eval_tracing() -> Iterator[None]:
    """실제 모델 평가는 서버와 같은 .env 설정으로 LangSmith에 트레이스를 남깁니다.

    루트 conftest가 테스트용으로 끈 값(트레이스·재정렬)을 지우고 설정을 다시 읽습니다.
    import 때가 아니라 evals 테스트가 실제로 돌 때만 하므로, tests/와 같이 실행해도
    tests/ 쪽에는 트레이스가 켜지지 않습니다. 평가가 끝나면 원래 값으로 되돌립니다(같은 실행에서
    뒤에 도는 tests/가 실제 모델을 부르지 않게).
    """
    saved = {name: os.environ.get(name) for name in TEST_ONLY_ENV}
    for name in TEST_ONLY_ENV:
        os.environ.pop(name, None)
    get_settings.cache_clear()
    gateway.configure_tracing()
    yield
    for name, value in saved.items():
        if value is not None:
            os.environ[name] = value
    get_settings.cache_clear()
    gateway.configure_tracing()


# ── 골든셋 (evals/test_golden.py) ──
GOLDEN_REPORT = pytest.StashKey["Report"]()


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("golden", "골든셋")
    group.addoption(
        "--golden-agent",
        choices=["real", "selftest", "broken", "setup"],
        default="real",
        help="real: 실제 AI · selftest: 채점 코드 점검(확정 문항은 모두 통과해야 정상) · "
        "broken: 일부러 틀리기 · setup: 모델 없이 문항 시작 상태만 점검(DB 필요)",
    )
    group.addoption(
        "--golden-set",
        choices=["dev", "test", "all"],
        default="dev",
        help="dev: 개발용(고칠 때 보는 문항) · test: 검증용(최종 확인 때만) · all: 전체",
    )
    group.addoption(
        "--golden-area",
        choices=["all", "procedure", "form_fill", "grounding", "masking"],
        default="all",
        help="이 영역만 실행",
    )
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
        "evals.golden.merge로 합칩니다",
    )


def _shard(config: pytest.Config) -> tuple[int, int]:
    index, total = (int(x) for x in config.getoption("--golden-shard").split("/"))
    if not 1 <= index <= total:
        raise pytest.UsageError("--golden-shard는 1/4처럼 1 이상 n 이하로 줍니다.")
    return index, total


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """고른 세트의 골든셋 문항 중 이 조각에 해당하는 것만 남깁니다(문항 순서의 i번째마다)."""
    chosen = config.getoption("--golden-set", default="all")
    if chosen != "all":
        other = [
            item
            for item in items
            if item.originalname == "test_golden" and item.callspec.params["case"]["set"] != chosen
        ]
        if other:
            config.hook.pytest_deselected(items=other)
            items[:] = [item for item in items if id(item) not in {id(o) for o in other}]
    index, total = _shard(config)
    if total == 1:
        return
    golden = [item for item in items if item.originalname == "test_golden"]
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
        judge=get("--golden-judge") == "on",
    )


@pytest.fixture(scope="session")
def golden_report(request: pytest.FixtureRequest) -> Report:
    get = request.config.getoption
    report = Report(
        mode=get("--golden-agent"),
        judge=get("--golden-judge"),
        shard=get("--golden-shard"),
        case_set=get("--golden-set"),
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
