"""팀 규칙표(data/rules/rule_table/*.csv)를 규칙 카드로 읽고 찾습니다. LLM·DB 없음.

규칙 카드 = 사람이 정리한 규칙 한 줄(내용·수치·마감·증빙·예외) + 출처.
모델은 카드를 기억 대신 읽고 쉬운 말로 전하기만 합니다.
원본은 Google 시트 「규칙표」이고 scripts/import_rule_table.py가 검수 상태·작업 메모를 걷어 낸
서비스 데이터만 CSV로 씁니다. 여기서는 모든 카드를 맞는 규칙으로 보고 씁니다.

예상 질문(data/rules/rule_questions.csv): 카드마다 사용자가 할 법한 질문을 미리 만들어 둔 것으로
검색에만 씁니다(scripts/generate_rule_questions.py). 모델이 읽는 카드 내용(for_model)에는 넣지
않습니다.
"""

import csv
import hashlib
import re
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path

from app.rules.ranking import Bm25Index

RULE_TABLE_DIR = Path(__file__).resolve().parents[2] / "data" / "rules" / "rule_table"
RULE_FILES = ("proc.csv", "elig.csv", "act.csv", "due.csv", "sup.csv")
SOURCES_FILE = "sources.csv"
QUESTIONS_FILE = RULE_TABLE_DIR.parent / "rule_questions.csv"

# 우리 사용자는 상용직(근로자)입니다. 다른 고용 형태 전용 규칙은 찾지 않습니다.
_OTHER_EMPLOYMENT = re.compile(
    r"^(자영업|일용|건설|예술인|노무제공|실업급여\((일용직|예술인|노무))"
)
# 검색 가중치: 규칙명·분류가 질문 주제와 가장 가깝습니다.
_FIELD_WEIGHTS = {
    "name": 3, "category": 2, "body": 1, "evidence": 1, "number": 1, "deadline": 1,
    "questions": 1,
}  # fmt: skip


@dataclass(frozen=True)
class RuleCard:
    rule_id: str
    category: str
    target: str
    stage: str
    name: str
    body: str
    number: str
    deadline: str
    evidence: str
    caution: str
    source_ids: tuple[str, ...]

    def for_model(self) -> dict[str, str]:
        """모델에 넘기는 모양. 빈 칸은 뺍니다."""
        fields = {
            "id": self.rule_id,
            "규칙": self.name,
            "내용": self.body,
            "수치": self.number,
            "기준일·마감": self.deadline,
            "증빙·경로": self.evidence,
            "예외·주의": self.caution,
        }
        return {k: v for k, v in fields.items() if v}


@dataclass(frozen=True)
class Source:
    source_id: str
    name: str
    issued: str
    url: str


def _read(filename: str) -> list[dict[str, str]]:
    with (RULE_TABLE_DIR / filename).open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _card(row: dict[str, str]) -> RuleCard:
    # 출처가 여럿이면 "SRC-008 SRC-017"처럼 띄어 씁니다.
    return RuleCard(**{**row, "source_ids": tuple(row["source_ids"].split())})


@lru_cache(maxsize=1)
def load_cards() -> tuple[RuleCard, ...]:
    return tuple(_card(row) for filename in RULE_FILES for row in _read(filename))


@lru_cache(maxsize=1)
def load_sources() -> dict[str, Source]:
    rows = _read(SOURCES_FILE)
    return {
        r["source_id"]: Source(
            source_id=r["source_id"], name=r["name"], issued=r["issued"], url=r["url"]
        )
        for r in rows
    }


def cards_by_id() -> dict[str, RuleCard]:
    return {c.rule_id: c for c in load_cards()}


# ── 찾기 ─────────────────────────────────────────────────


def is_other_employment(target: str) -> bool:
    return bool(_OTHER_EMPLOYMENT.match(target))


def card_text_hash(card: RuleCard) -> str:
    """예상 질문을 만든 카드 글의 해시. 카드가 바뀌면 달라져 예전 질문을 쓰지 않습니다."""
    text = "\n".join(f"{k}: {v}" for k, v in card.for_model().items())
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


@lru_cache(maxsize=1)
def load_card_questions() -> dict[str, tuple[str, tuple[str, ...]]]:
    """rule_id → (만들 때 카드 해시, 질문들). 파일이 없으면 빈 사전."""
    if not QUESTIONS_FILE.exists():
        return {}
    grouped: dict[str, tuple[str, list[str]]] = {}
    with QUESTIONS_FILE.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            grouped.setdefault(row["rule_id"], (row["card_hash"], []))[1].append(row["question"])
    return {rule_id: (h, tuple(qs)) for rule_id, (h, qs) in grouped.items()}


def card_questions(card: RuleCard) -> tuple[str, ...]:
    """지금 카드 글로 만든 예상 질문만 돌려줍니다(규칙표가 바뀐 뒤 다시 만들기 전이면 빈 값)."""
    card_hash, questions = load_card_questions().get(card.rule_id, ("", ()))
    return questions if card_hash == card_text_hash(card) else ()


@lru_cache(maxsize=1)
def _index() -> Bm25Index:
    cards = (c for c in load_cards() if not is_other_employment(c.target))
    return Bm25Index(
        ((c.rule_id, {**asdict(c), "questions": " ".join(card_questions(c))}) for c in cards),
        _FIELD_WEIGHTS,
    )


def search_card_ids(query: str, limit: int) -> list[str]:
    """질문과 겹치는 글자 묶음이 많은 카드 ID 순(BM25). 겹치는 게 없으면 빈 목록."""
    return [rule_id for rule_id, _ in _index().search(query, limit)]


def search_cards(query: str, limit: int = 3) -> list[RuleCard]:
    cards = cards_by_id()
    return [cards[i] for i in search_card_ids(query, limit)]


# ── 근거 줄 ─────────────────────────────────────────────


def cite_line(rule_ids: list[str], extra_sources: list[str] | None = None) -> str | None:
    """쓴 규칙들의 출처로 근거 줄을 만듭니다. 출처는 중복 없이 씁니다.

    extra_sources는 규칙 카드 밖의 근거(정책·FAQ 조각)로 이미 만든 표시이고 뒤에 붙입니다.
    예: "실업급여(상용직) · 2026-08-25 / 고용24 「조기재취업수당」 · 2025-07-10"
    """
    cards = cards_by_id()
    sources = load_sources()
    used = [cards[i] for i in rule_ids if i in cards]
    parts: list[str] = []
    for source_id in dict.fromkeys(s for c in used for s in c.source_ids):
        source = sources.get(source_id)
        if source is None:
            continue
        # 기준일은 날짜가 적힌 출처에만 붙습니다.
        parts.append(f"{source.name} · {source.issued}" if source.issued else source.name)
    parts += [label for label in dict.fromkeys(extra_sources or []) if label not in parts]
    return " / ".join(parts) or None
