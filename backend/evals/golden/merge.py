"""조각(--golden-shard)으로 나눠 돌린 골든셋 기록(.json)을 보고서 하나로 합칩니다.

실행: backend/에서 `uv run python -m evals.golden.merge 조각1.json 조각2.json ...`
"""

import argparse
import json
import uuid
from datetime import datetime
from pathlib import Path

from evals.golden.report import Record, Report


def merge(paths: list[Path]) -> Path:
    parts = [json.loads(p.read_text(encoding="utf-8")) for p in paths]
    first = parts[0]
    report = Report(mode=first["mode"], judge=first["judge"], shard=f"{len(parts)}조각 합침")
    for part in parts:
        report.records += [Record(r["case"], r["status"], r["reasons"]) for r in part["records"]]
    report.records.sort(key=lambda r: r.case["id"])
    # 여러 실험을 동시에 합치면 같은 초에 끝날 수 있어 고유값을 붙입니다(덮어쓰기 방지).
    return report.write(f"golden-{datetime.now():%Y%m%d-%H%M%S}-merged-{uuid.uuid4().hex[:6]}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("parts", nargs="+", type=Path)
    print(f"보고서: {merge(parser.parse_args().parts)}")


if __name__ == "__main__":
    main()
