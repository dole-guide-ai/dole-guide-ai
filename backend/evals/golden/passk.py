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


def failed_ids(report: Path) -> set[str]:
    """보고서의 실패·참고 실패·문항 오류 표에 있는 문항(건너뛴 이유 표는 제외)."""
    ids: set[str] = set()
    in_failures = False
    for line in report.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            in_failures = "실패" in line or "문항 오류" in line
        elif in_failures and (m := _ROW.match(line)):
            ids.add(m[1])
    return ids


def case_ids(area: str) -> list[str]:
    cases = [json.loads(p.read_text(encoding="utf-8")) for p in OUT_DIR.glob(f"{area}/*.json")]
    # 첨부 파일 문항은 아직 실행하지 않습니다(adapter가 건너뜀).
    return sorted(c["id"] for c in cases if not c["input"]["files"] and c["review"] != "보류")


def summarize(area: str, reports: list[Path]) -> dict[str, object]:
    ids = case_ids(area)
    fails = [failed_ids(r) for r in reports]
    passes = {i: sum(i not in f for f in fails) for i in ids}
    k = len(reports)
    return {
        "k": k,
        "cases": len(ids),
        "pass^k": sum(n == k for n in passes.values()) / len(ids),
        "pass@k": sum(n > 0 for n in passes.values()) / len(ids),
        "mean": sum(passes.values()) / (len(ids) * k),
        "flaky": sorted(i for i, n in passes.items() if 0 < n < k),
        # k번 모두 실패: AI 실력보다 문항·채점이 고장 났을 때가 많아 먼저 문항을 확인합니다.
        "always_failed": sorted(i for i, n in passes.items() if n == 0),
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
