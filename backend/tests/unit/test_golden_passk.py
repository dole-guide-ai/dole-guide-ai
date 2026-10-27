"""골든셋 pass^k 집계(evals/golden/passk): 실제로 돈 문항만 세고, 문항 오류는 점수에서 뺍니다."""

import json
from pathlib import Path

import pytest

from evals.golden import passk


def _report(tmp_path: Path, name: str, statuses: dict[str, str]) -> Path:
    """보고서(.md 표)와 기록(.json)을 만듭니다. statuses: 문항 ID → 상태."""
    lines = ["# 골든셋 결과", ""]
    for status in ("문항 오류", "실패"):
        ids = [i for i, s in statuses.items() if s == status]
        if ids:
            lines += [
                f"## {status} {len(ids)}개",
                "",
                "| ID | 설명 | 이유 |",
                "| --- | --- | --- |",
            ]
            lines += [f"| {i} | 설명 | 이유 |" for i in ids]
    path = tmp_path / f"{name}.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    records = [{"case": {"id": i, "area": "procedure"}, "status": s} for i, s in statuses.items()]
    path.with_suffix(".json").write_text(json.dumps({"records": records}), encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def all_cases(monkeypatch: pytest.MonkeyPatch) -> None:
    ids = ["P-001", "P-002", "P-003", "P-004"]
    monkeypatch.setattr(passk, "case_ids", lambda area: ids)


def test_only_cases_that_ran_count(tmp_path: Path) -> None:
    # 개발용 세트만 돌린 실행: P-003·P-004는 돌지 않았으니 통과로 치지 않음
    reports = [
        _report(tmp_path, f"r{n}", {"P-001": "통과", "P-002": "실패", "P-003": "건너뜀"})
        for n in range(2)
    ]

    result = passk.summarize("procedure", reports)

    assert result["cases"] == 2
    assert result["pass^k"] == 0.5
    assert result["always_failed"] == ["P-002"]


def test_setup_broken_is_left_out_of_scores(tmp_path: Path) -> None:
    reports = [
        _report(tmp_path, f"r{n}", {"P-001": "통과", "P-002": "문항 오류"}) for n in range(2)
    ]

    result = passk.summarize("procedure", reports)

    assert result["cases"] == 1 and result["pass^k"] == 1.0
    assert result["setup_broken"] == ["P-002"]
    assert result["always_failed"] == ["P-002"]
