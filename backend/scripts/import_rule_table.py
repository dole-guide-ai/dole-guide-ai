"""팀 규칙표(Google 시트)를 서비스 데이터 CSV로 가져옵니다.

원본은 Google 시트 「규칙표」입니다. 시트는 정리 작업 문서라 검수 상태·작업 메모가 섞여 있어서,
여기서 서비스에 필요한 칸만 남기고 값을 정리해 data/rules/rule_table/에 씁니다(2026-10-26 결정:
규칙은 모두 맞는 것으로 보고 검수 여부·메모는 데이터에 넣지 않음).

- 남기는 칸: 규칙 ID·분류·적용 대상·단계·규칙명·내용·수치·기준일·증빙·주의사항·출처 ID
- 빼는 것: 「확인 필요」 시트, 검수 상태·검수자·검수일·자료 확인일·시행일·근거 위치 칸,
  주의사항의 작업 메모 문장, "원문은 ~고 안내한다" 같은 전달자 말투, "미기재" 같은 공백 표시

시트를 고치면 엑셀(.xlsx)로 내려받아 다시 돌리고, 바뀐 CSV를 커밋합니다.
실행: backend/에서 `uv run python scripts/import_rule_table.py 내려받은파일.xlsx`
"""

import argparse
import csv
import re
from pathlib import Path

import openpyxl

OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "rules" / "rule_table"
RULE_SHEETS = {
    "신청·수급 절차": "proc.csv",
    "자격·급여 기준": "elig.csv",
    "회차·인정활동": "act.csv",
    "기한·신고·예외": "due.csv",
    "추가 지원": "sup.csv",
}
SOURCE_SHEET = "출처 목록"
RULE_FIELDS = [
    "rule_id", "category", "target", "stage", "name", "body",
    "number", "deadline", "evidence", "caution", "source_ids",
]  # fmt: skip
# 시트 열 위치(0부터). 시트마다 4번째 열 이름이 달라 위치로 읽습니다.
_RULE_COLUMNS = {
    "rule_id": 0, "category": 1, "target": 2, "stage": 3, "name": 4, "body": 5,
    "number": 6, "deadline": 7, "evidence": 8, "caution": 9, "source_ids": 10,
}  # fmt: skip
SOURCE_FIELDS = ["source_id", "name", "publisher", "url", "issued"]

# 작업 메모로 보는 문장: 다른 규칙·출처 ID 참조, 주소, 검수·보완·상충·자료 유무 표시,
# 출처의 판·쪽·변경 기록("2025년판 안내", "인쇄6~9쪽", "2026-10-21: …정정"), 출처끼리 비교한 메모.
# "개인별 지정일은 별도 확인"처럼 사용자에게 주는 안내는 남깁니다.
_NOTE = re.compile(
    r"(SRC|CHECK|ELIG|ACT|DUE|PROC|SUP)-\d|https?://|검수|로\s*(용어|근거)?\s*보완|보완했|상충|원문"
    r"|이 자료|이 페이지|자료에|자료상|수정 자료|자료 기준|미기재|미확인|추가 확인|확인 필요"
    r"|서비스 확정|적용\s?범위|\d+(~\d+)?쪽|\d{4}년판|\d{4}안내|\d{4}-\d{2}-\d{2}\s*:|추론|현행성"
    r"|최신 법령|안내는 없|자료 필요|페이지(의| 정보)|문구와|미표기|머리글|(최신|현재 사업) 기준"
)
_PLACEHOLDER = re.compile(r"미기재|자료에 없|해당 없음|자료 필요")
# 문장 끝 마침표·쌍반점에서 나눕니다. "1.5"처럼 숫자 사이 점은 나누지 않습니다.
_SENTENCE = re.compile(r"(?<=[.;])(?!\d)\s*|;\s*")
# 전달자 말투 → 규칙 문장. 앞의 것부터 바꿉니다(구체적인 꼴을 먼저).
_VOICE = [
    # "원문상 4년"의 상은 지우고 "원문 상·하한액"의 상은 남깁니다(조사 상 뒤에는 띄어쓰기).
    (r"원문(\s*Q&A)?(\s*안내\s*:|상(?=\s)|에서|에는|은|는|에)?\s*", ""),
    (r"(수첩|[^ ]+ 안내 페이지)(은|는|상|에서는?)\s+", ""),
    (r"\d{4}년판\s*:\s*", ""),
    (r"하다는 수첩 안내", ""),
    (r"된다고 안내하지 않음", "되지는 않음"),
    (r"하는 안내문이다", "한다"),
    (r"있음을 안내한다", "있다"),
    (r"도록 안내한다", "도록 한다"),
    (r"(다)고 안내(한다)?", r"\1"),
    (r"\s*(으로|로|[을를])\s*(안내|제시)(한다)?(?=[.;]|$)", ""),
]


def clean_text(text: str) -> str:
    """'수첩은 X로 안내한다' 같은 전달자 말투를 걷어 규칙 문장으로 바꿉니다."""
    for pattern, repl in _VOICE:
        text = re.sub(pattern, repl, text)
    return text.strip()


def clean_caution(text: str) -> str:
    """주의사항에서 작업 메모 문장만 빼고 사용자에게 필요한 문장은 남깁니다."""
    kept = [s.strip() for s in _SENTENCE.split(text) if s.strip() and not _NOTE.search(s)]
    return clean_text(" ".join(s if s.endswith(".") else s + "." for s in kept))


def clean_value(text: str) -> str:
    return "" if _PLACEHOLDER.search(text) else text


def rule_row(cells: list[str]) -> dict[str, str]:
    row = {field: cells[i] for field, i in _RULE_COLUMNS.items()}
    for field in ("name", "body", "number"):
        row[field] = clean_text(row[field])
    row["caution"] = clean_caution(row["caution"])
    for field in ("number", "deadline", "evidence"):
        row[field] = clean_value(row[field])
    row["source_ids"] = " ".join(re.findall(r"SRC-\d+", row["source_ids"]))
    return row


def source_row(cells: list[str]) -> dict[str, str]:
    issued = re.search(r"\d{4}-\d{2}-\d{2}", cells[4])
    return {
        "source_id": cells[0],
        "name": cells[1],
        "publisher": cells[2],
        "url": cells[3],
        "issued": issued[0] if issued else "",
    }


def _rows(workbook: openpyxl.Workbook, sheet: str) -> list[list[str]]:
    rows = [
        ["" if cell is None else str(cell).strip() for cell in row]
        for row in workbook[sheet].iter_rows(values_only=True)
    ]
    return [row for row in rows[1:] if any(row)]


def _write(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def export(xlsx: Path) -> dict[str, int]:
    workbook = openpyxl.load_workbook(xlsx, data_only=True, read_only=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    counts = {}
    for sheet, filename in RULE_SHEETS.items():
        rows = [rule_row(cells) for cells in _rows(workbook, sheet)]
        _write(OUT_DIR / filename, RULE_FIELDS, rows)
        counts[filename] = len(rows)
    sources = [source_row(cells) for cells in _rows(workbook, SOURCE_SHEET)]
    _write(OUT_DIR / "sources.csv", SOURCE_FIELDS, sources)
    counts["sources.csv"] = len(sources)
    (OUT_DIR / "check.csv").unlink(missing_ok=True)  # 예전 가져오기가 만든 작업 메모 시트
    return counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("xlsx", type=Path)
    for name, count in export(parser.parse_args().xlsx).items():
        print(f"{name}: {count}행")


if __name__ == "__main__":
    main()
