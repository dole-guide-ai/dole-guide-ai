"""같은 골든셋을 여러 번 돌린 보고서를 합쳐 문항별 통과 횟수와 pass^k를 냅니다.

LLM은 같은 입력에도 결과가 달라서 한 번 통과로는 품질을 말할 수 없습니다. pass^k는 k번 모두
통과한 문항 비율이고(τ-bench), pass@k는 k번 중 한 번이라도 통과한 비율입니다.

실행: backend/에서 `uv run python -m evals.golden.passk --area form_fill 보고서1.md 보고서2.md ...`
"""

import argparse
import json
import re
from pathlib import Path

from evals.golden.schema import OUT_DIR

_ROW = re.compile(r"^\| ([A-Z]-\d{3}) \|")
SKIPPED = "건너뜀"


def report_ids(report: Path) -> tuple[set[str], set[str]]:
    """보고서 표에서 (채점 실패 문항, 문항 오류 문항). 건너뛴 이유 표는 보지 않습니다."""
    failed: set[str] = set()
    broken: set[str] = set()
    section: set[str] | None = None
    for line in report.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            section = broken if "문항 오류" in line else failed if "실패" in line else None
        elif section is not None and (m := _ROW.match(line)):
            section.add(m[1])
    return failed, broken


def ran_ids(report: Path, area: str) -> set[str] | None:
    """그 실행에서 실제로 돈 문항(건너뜀 제외). 고른 세트(--golden-set) 밖 문항은 들어가지 않습니다.

    보고서 옆 기록(.json)이 없으면 None(만든 시나리오 전체로 셈).
    """
    record_path = report.with_suffix(".json")
    if not record_path.is_file():
        return None
    records = json.loads(record_path.read_text(encoding="utf-8"))["records"]
    return {
        r["case"]["id"] for r in records if r["case"]["area"] == area and r["status"] != SKIPPED
    }


def case_ids(area: str) -> list[str]:
    cases = [json.loads(p.read_text(encoding="utf-8")) for p in OUT_DIR.glob(f"{area}/*.json")]
    return sorted(c["id"] for c in cases if c["review"] != "보류")


def summarize(area: str, reports: list[Path]) -> dict[str, object]:
    ran = [ran_ids(r, area) for r in reports]
    # 모든 실행에서 돈 문항만 셉니다. 한 번이라도 안 돈 문항을 통과로 치면 점수가 부풀기 때문입니다.
    population = set(case_ids(area))
    for ids in ran:
        if ids is not None:
            population &= ids
    results = [report_ids(r) for r in reports]
    # 문항 오류(시작 상태 어긋남)는 AI 점수가 아니라서 지표에서 빼고 따로 보여 줍니다.
    broken = sorted(population & set().union(*(b for _, b in results)))
    ids = sorted(population - set(broken))
    passes = {i: sum(i not in failed for failed, _ in results) for i in ids}
    k = len(reports)
    count = max(len(ids), 1)
    return {
        "k": k,
        "cases": len(ids),
        "pass^k": sum(n == k for n in passes.values()) / count,
        "pass@k": sum(n > 0 for n in passes.values()) / count,
        "mean": sum(passes.values()) / (count * k),
        "flaky": sorted(i for i, n in passes.items() if 0 < n < k),
        # k번 모두 실패: AI 실력보다 문항·채점이 고장 났을 때가 많아 먼저 문항을 확인합니다.
        "always_failed": sorted([*broken, *(i for i, n in passes.items() if n == 0)]),
        "setup_broken": broken,
        "per_case": passes,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--area", required=True)
    parser.add_argument("reports", nargs="+", type=Path)
    args = parser.parse_args()
    result = summarize(args.area, args.reports)
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
