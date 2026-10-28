"""구어 표현 → 행정 용어 사전(data/rules/synonyms.csv)으로 검색 질문을 넓힙니다.

사용자는 "날일 하다 관뒀는데"처럼 말하고 규칙표는 "일용직", "이직"으로 적혀 있어 단어 검색이
못 찾습니다. 사전에 있는 말이 질문에 있으면 행정 용어를 질문 뒤에 덧붙입니다. 띄어쓰기는 무시하고
비교합니다("나가 달라" = "나가달라").
"""

import csv
import re
from functools import lru_cache
from pathlib import Path

SYNONYMS_FILE = Path(__file__).resolve().parents[2] / "data" / "rules" / "synonyms.csv"


@lru_cache(maxsize=1)
def load_synonyms() -> tuple[tuple[str, str], ...]:
    with SYNONYMS_FILE.open(encoding="utf-8") as f:
        return tuple((row["term"], row["expansion"]) for row in csv.DictReader(f))


def expand_query(query: str) -> str:
    compact = re.sub(r"\s+", "", query)
    added = [expansion for term, expansion in load_synonyms() if term in compact]
    return " ".join([query, *dict.fromkeys(added)])
