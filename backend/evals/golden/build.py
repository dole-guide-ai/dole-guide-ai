"""골든셋 CSV → 시나리오 JSON. 루트에서 `pnpm golden:build`(만들기) · `pnpm golden:check`(검사만).

CSV가 원본입니다. 만든 JSON(evals/scenarios/golden/)은 저장소에 올리지 않고
실행할 때마다 다시 만듭니다.
"""

import argparse
import csv
import io
import json
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from evals.golden.presets import resolve_input
from evals.golden.schema import (
    COLUMNS,
    CSV_PATH,
    FILES_DIR,
    OUT_DIR,
    GoldenError,
    row_to_case,
)


def read_rows(path: Path) -> list[tuple[int, dict[str, str]]]:
    """(실제 줄 번호, 행) 목록. 엑셀 CSV도 읽습니다: UTF-8(BOM 포함)을 먼저, 안 되면 CP949로."""
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp949")
        print("알림: CSV가 CP949로 저장돼 있어요. 엑셀에서 'CSV UTF-8'로 저장하면 더 안전해요.")
    reader = csv.DictReader(io.StringIO(text, newline=""))
    header = [name.strip() for name in reader.fieldnames or []]
    if missing := [name for name in COLUMNS if name not in header]:
        raise GoldenError(f"CSV 첫 줄에 없는 열: {', '.join(missing)}")
    reader.fieldnames = header
    # 빈 줄·셀 안 줄바꿈이 있어도 맞도록 순서 대신 reader.line_num(그 행이 끝나는 줄)을 씁니다.
    return [(reader.line_num, row) for row in reader]


def load_cases(path: Path = CSV_PATH) -> tuple[list[dict[str, Any]], list[str]]:
    cases, errors, seen = [], [], set()
    for line, row in read_rows(path):
        if not any((value or "").strip() for value in row.values()):
            continue
        label = f"{line}번째 줄 ({(row.get('ID') or '').strip() or 'ID 없음'})"
        try:
            case = row_to_case(row)
            case["input"] = resolve_input(case["input"])
        except (GoldenError, ValueError) as error:
            errors.append(f"{label}: {error}")
            continue
        if case["id"] in seen:
            errors.append(f"{label}: ID가 겹쳐요.")
        seen.add(case["id"])
        for name in case["input"]["files"]:
            if not (FILES_DIR / name).is_file():
                errors.append(f"{label}: 첨부 파일 '{name}'이 golden/files/에 없어요.")
        cases.append(case)
    return cases, errors


def write_cases(cases: list[dict[str, Any]]) -> None:
    shutil.rmtree(OUT_DIR, ignore_errors=True)
    for case in cases:
        target = OUT_DIR / case["area"] / f"{case['id']}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(case, ensure_ascii=False, indent=2) + "\n"
        target.write_text(text, encoding="utf-8", newline="\n")


def summary(cases: list[dict[str, Any]]) -> str:
    def line(title: str, counter: Counter[str]) -> str:
        return f"{title}: " + ", ".join(f"{key} {count}" for key, count in counter.most_common())

    return "\n".join(
        [
            f"문항 {len(cases)}개",
            line("영역", Counter(case["area"] for case in cases)),
            line("방법", Counter(case["method"] for case in cases)),
            line("검수", Counter(case["review"] for case in cases)),
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="골든셋 CSV를 검사하고 시나리오 JSON을 만듭니다.")
    parser.add_argument("--check", action="store_true", help="검사만 하고 파일은 만들지 않음")
    args = parser.parse_args()
    try:
        cases, errors = load_cases()
    except GoldenError as error:
        print(f"오류: {error}")
        return 1
    if errors:
        print(f"고칠 곳 {len(errors)}개:")
        print("\n".join(f"- {message}" for message in errors))
        return 1
    if not args.check:
        write_cases(cases)
        print(f"만든 위치: {OUT_DIR}")
    print(summary(cases))
    return 0


if __name__ == "__main__":
    sys.exit(main())
