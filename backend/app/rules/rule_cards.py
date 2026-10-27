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
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
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


def search_card_ids(
    query: str, limit: int, profile: Profile | None = None, add_terms: bool = True
) -> list[str]:
    """질문과 겹치는 글자 묶음이 많은 카드 ID 순(BM25). 겹치는 게 없으면 빈 목록.

    profile을 주면 그 사용자에게 맞지 않는 카드(다른 수급자 유형·회차)는 빼고, 질문에
    "반복수급자 3차" 같은 말을 덧붙여 찾습니다(빼기만 하면 맞는 카드를 못 찾음).
    """
    cards = cards_by_id()
    if profile and add_terms and profile.terms:
        query = f"{query} {profile.terms}"
    found = _index().search(query, limit * PROFILE_OVERFETCH if profile else limit)
    ids = [i for i, _ in found if profile is None or applies_to(cards[i], profile)]
    return ids[:limit]


def search_cards(query: str, limit: int = 3, profile: Profile | None = None) -> list[RuleCard]:
    cards = cards_by_id()
    return [cards[i] for i in search_card_ids(query, limit, profile)]


# ── 사용자에게 맞는 카드 ─────────────────────────────────

# 규칙표의 수급자 유형(적용 대상 칸)과 절차 상태의 수급자 그룹(procedure.recipient_group)
GROUP_LABELS = {
    "general": "일반수급자",
    "age_60_64": "만 60~64세 수급자",
    "age65_or_disabled": "만 65세 이상·장애인 수급자",
    "repeat": "반복수급자",
}
# 맞지 않는 카드를 거른 뒤에도 limit만큼 남게 넉넉히 찾습니다.
PROFILE_OVERFETCH = 4
_ROUND_IN_QUERY = re.compile(r"(\d{1,2})\s*차")


@dataclass(frozen=True)
class Profile:
    """규칙 카드를 고를 때 쓰는 사용자 조건. 값이 없으면 그 조건으로 거르지 않습니다."""

    group: str | None = None
    round_no: int | None = None
    # 이직 당시 50세 이상이거나 장애인(소정급여일수 표가 둘로 나뉨)
    over_50: bool | None = None

    def for_query(self, query: str) -> Profile:
        """질문에 "4차"처럼 회차가 있으면 지금 회차 대신 그 회차로 고릅니다."""
        if m := _ROUND_IN_QUERY.search(query):
            return replace(self, round_no=int(m.group(1)))
        return self

    @property
    def terms(self) -> str:
        """검색 질문에 덧붙이는 말. 예: "반복수급자 3차"."""
        label = GROUP_LABELS.get(self.group or "", "")
        round_ = f"{self.round_no}차" if self.round_no else ""
        return " ".join(p for p in (label, round_) if p)


def _target_groups(target: str) -> set[str] | None:
    """카드 적용 대상 칸에 수급자 유형이 적혀 있으면 그 그룹들. 없으면 모두에게 적용(None)."""
    t = target.replace(" ", "")
    if "반복수급자" in t:
        return {"repeat"}
    if "일반수급자" in t:
        return {"general"}
    if "60~64세" in t:
        return {"age_60_64"}
    if "65세이상" in t:
        return {"age65_or_disabled"}
    if "60세이상" in t:
        return {"age_60_64", "age65_or_disabled"}
    return None


def _over_50(target: str) -> bool | None:
    """대상 칸이 "50세 미만"이면 False, "50세 이상 또는 장애인"이면 True, 구분이 없으면 None."""
    t = target.replace(" ", "")
    if "50세미만" in t:
        return False
    if "50세이상" in t:
        return True
    return None


def _rounds(stage: str) -> Callable[[int], bool] | None:
    """카드 단계 칸의 회차 범위("2~3차", "8차~만료", "1·4·8차", "3차 이후"). 회차가 아니면 None."""
    s = stage.replace(" ", "")
    if m := re.fullmatch(r"(\d+)~(\d+)차", s):
        low, high = int(m.group(1)), int(m.group(2))
        return lambda n: low <= n <= high
    if m := re.fullmatch(r"(\d+)차(?:~만료일?|이후)", s):
        low = int(m.group(1))
        return lambda n: n >= low
    if re.fullmatch(r"\d+(?:·\d+)*차", s):
        rounds = {int(x) for x in s[:-1].split("·")}
        return lambda n: n in rounds
    return None


# 회차 범위 대신 "모든 회차"로 적힌 단계 칸
_EVERY_ROUND = {"매회차", "전체", "전회차"}


def cards_for(profile: Profile) -> list[RuleCard]:
    """이 수급자 유형·회차에 정해진 카드(활동 횟수·출석·인정 범위). 검색하지 않고 바로 고릅니다.

    예: 반복수급자 3차 → ACT-102(매 회차 출석)·ACT-104(2주1회, 3차부터 구직활동만)·ACT-112.
    유형별 카드는 글이 짧아("2주1회;3차부터 구직활동만 인정") 질문으로 찾으면 일반 카드에 밀립니다.
    """
    if not profile.group or not profile.round_no:
        return []
    picked = []
    for card in load_cards():
        groups = _target_groups(card.target)
        if is_other_employment(card.target) or not groups or profile.group not in groups:
            continue
        rounds = _rounds(card.stage)
        if rounds is None and card.stage.replace(" ", "") not in _EVERY_ROUND:
            continue
        if rounds is None or rounds(profile.round_no):
            picked.append(card)
    return picked


def applies_to(card: RuleCard, profile: Profile) -> bool:
    """이 사용자에게 맞는 카드인지. 다른 유형·회차의 규칙을 알려 주면 틀린 안내가 됩니다."""
    groups = _target_groups(card.target)
    if groups and profile.group and profile.group not in groups:
        return False
    band = _over_50(card.target)
    if band is not None and profile.over_50 is not None and band != profile.over_50:
        return False
    rounds = _rounds(card.stage)
    return not (rounds and profile.round_no and not rounds(profile.round_no))


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
