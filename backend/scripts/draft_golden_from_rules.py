"""팀 규칙표로 골든셋 '근거' 문항을 만들 때 쓰는 보조 도구입니다.

골든셋 500문항 확장(#230)에서 규칙표 카드 기반 문항을 만들 때 썼습니다. 두 가지를 합니다.

- `--draft`: 수치·마감·증빙이 있는 카드를 분류 비례로 뽑아 초안 CSV를 만듭니다.
  질문·꼭포함은 사람이 다듬습니다(자동 생성 문장을 그대로 쓰지 않습니다).
- `--check`: golden_set.csv에서 근거 칸이 규칙표 카드 ID인 행을 검사합니다.
  ① 꼭포함 문자열이 그 카드(수치·마감·증빙·내용)에 실제로 있는지
  ② 질문이 검색용 예상 질문(rule_questions.csv, 색인에 들어감)과 2-gram 자카드 0.5 이상으로
     겹치지 않는지 — 겹치면 검색 점수가 부풀어 평가가 무의미해집니다.

규칙표 CSV(data/rules/rule_table)는 아직 develop에 없습니다(#220).
`--rules-dir`로 경로를 주거나, #220 브랜치를 받은 뒤 실행하세요.

실행: uv run python -m scripts.draft_golden_from_rules --draft 초안.csv
      uv run python -m scripts.draft_golden_from_rules --check evals/golden/golden_set.csv
"""

import argparse
import csv
import re
import sys
from pathlib import Path

RULES_DIR = Path(__file__).resolve().parents[1] / "data" / "rules" / "rule_table"
QUESTIONS_FILE = RULES_DIR.parent / "rule_questions.csv"
RULE_FILES = ("proc", "elig", "act", "due", "sup")
# 분류별로 뽑을 카드 수 (수치·마감·증빙이 있는 카드 비율에 비례)
SAMPLE_PER_FILE = {"proc": 18, "elig": 32, "act": 26, "due": 20, "sup": 14}
# 예상 질문과 이 값 이상 겹치면 그 질문은 검색이 거저 맞히므로 다시 씁니다.
MAX_QUESTION_OVERLAP = 0.5
RULE_ID = re.compile(r"\b(?:PROC|ELIG|ACT|DUE|SUP)-\d+\b")


def load_cards(rules_dir: Path) -> dict[str, dict[str, str]]:
    if not rules_dir.is_dir():
        sys.exit(f"규칙표가 없습니다: {rules_dir} — #220 브랜치를 받거나 --rules-dir을 주세요.")
    cards = {}
    for name in RULE_FILES:
        with (rules_dir / f"{name}.csv").open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                cards[row["rule_id"]] = row
    return cards


def sample(cards: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    """분류마다 수치·마감·증빙이 있는 카드를 rule_id 순서에서 고르게 뽑습니다(결정적)."""
    picked = []
    for prefix, want in SAMPLE_PER_FILE.items():
        filled = [
            c for rid, c in sorted(cards.items())
            if rid.lower().startswith(prefix) and (c["number"] or c["deadline"] or c["evidence"])
        ]  # fmt: skip
        step = max(1, len(filled) // want)
        picked += filled[::step][:want]
    return picked


def draft(out: Path, rules_dir: Path) -> None:
    rows = sample(load_cards(rules_dir))
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["rule_id", "name", "body", "number", "deadline", "evidence", "caution"])
        for c in rows:
            writer.writerow([c["rule_id"], c["name"], c["body"], c["number"],
                             c["deadline"], c["evidence"], c["caution"]])  # fmt: skip
    print(f"초안 카드 {len(rows)}장 → {out}")


def _bigrams(text: str) -> set[str]:
    text = re.sub(r"\s+", "", text)
    return {text[i : i + 2] for i in range(len(text) - 1)}


def _jaccard(a: str, b: str) -> float:
    x, y = _bigrams(a), _bigrams(b)
    return len(x & y) / len(x | y) if x and y else 0.0


def check(golden: Path, rules_dir: Path) -> int:
    cards = load_cards(rules_dir)
    doc2query: dict[str, list[str]] = {}
    if QUESTIONS_FILE.exists():
        with QUESTIONS_FILE.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                doc2query.setdefault(row["rule_id"], []).append(row["question"])
    problems = []
    with golden.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            source = row.get("근거", "")
            # '대본 PROC-009'처럼 규칙표가 아닌 자료도 같은 접두사를 쓰므로, '규칙표'라고
            # 밝힌 행만 검사합니다.
            rule_ids = RULE_ID.findall(source) if "규칙표" in source else []
            if not rule_ids:
                continue
            texts = [cards[r] for r in rule_ids if r in cards]
            if missing := [r for r in rule_ids if r not in cards]:
                problems.append(f"{row['ID']}: 모르는 카드 {missing}")
                continue
            haystack = " ".join(
                " ".join((c["name"], c["body"], c["number"], c["deadline"], c["evidence"]))
                for c in texts
            )
            for need in filter(None, (s.strip() for s in row.get("꼭포함", "").split(";"))):
                if need not in haystack:
                    problems.append(f"{row['ID']}: 꼭포함 '{need}'이(가) 카드 {rule_ids}에 없음")
            for rid in rule_ids:
                for q in doc2query.get(rid, []):
                    overlap = _jaccard(row["입력"], q)
                    if overlap >= MAX_QUESTION_OVERLAP:
                        problems.append(
                            f"{row['ID']}: 질문이 예상 질문과 {overlap:.2f} 겹침 — '{q}'"
                        )
    for p in problems:
        print(p)
    print(f"검사한 파일: {golden} · 문제 {len(problems)}건")
    return 1 if problems else 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rules-dir", type=Path, default=RULES_DIR)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--draft", type=Path, help="초안 카드 CSV를 쓸 경로")
    group.add_argument("--check", type=Path, help="검사할 golden_set.csv 경로")
    args = parser.parse_args()
    if args.draft:
        draft(args.draft, args.rules_dir)
    else:
        sys.exit(check(args.check, args.rules_dir))


if __name__ == "__main__":
    main()
