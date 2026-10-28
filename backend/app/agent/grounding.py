"""답의 근거 검사(6단계). 답 문장의 숫자·날짜·시간·금액이 이번 턴의 근거에 있는지 봅니다.

근거 = 지금 상황(facts: 절차 단계·회차 숫자·붙인 규칙 카드·정책 조각) + 도구 결과 + 사용자 말.
모델이 앞 턴에 한 답은 근거로 치지 않습니다(틀린 답이 스스로를 근거로 삼지 않게).

- 숫자: 코드가 대조합니다. 빠르고 비용이 없고 결과가 늘 같습니다.
- 수급·인정 여부를 단정하는 문장("받을 수 있어요", "인정 안 돼요"): 숫자가 맞아도 근거를 넘어
  쓴 것일 수 있어 작은 모델에 근거와 함께 물어봅니다. 그런 문장에서만 부릅니다.
- 근거 줄: 붙인 카드 중 답에 숫자·증빙 이름·규칙 용어가 나온 카드만 남깁니다.
"""

import json
import logging
import re
from collections.abc import Iterable, Sequence
from typing import Any

from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage, ToolMessage
from pydantic import BaseModel

from app.agent import gateway
from app.agent.prompts import load_prompt
from app.rules.ranking import bigrams

logger = logging.getLogger(__name__)

SUPPORT_PROMPT = "verify/support"
# 문장 하나를 판정할 때 모델에 넘기는 근거 글자 수 상한(비용·지연)
EVIDENCE_MAX_CHARS = 6000
# 한 답에서 모델에 묻는 단정 문장 수 상한
MAX_MODEL_CHECKS = 2
# 근거 줄: 카드의 규칙명·증빙 이름 글자 묶음이 답에 이만큼 나오면 쓴 카드로 봅니다.
CARD_TERM_OVERLAP = 0.5
# 근거 줄: 카드 내용(body) 글자 묶음이 답에 이만큼 나오면 내용을 풀어 쓴 것으로 봅니다.
CARD_BODY_OVERLAP = 0.4

_UNIT_ALIASES = {"달": "개월", "퍼센트": "%", "시": "시"}
_MULTIPLIERS = {"십": 10, "백": 100, "천": 1000, "만": 10_000, "억": 100_000_000}
_AMOUNT = re.compile(r"(\d[\d,]*)\s*((?:[십백천]?만|억|천)?)\s*원")
# 날짜는 "12월 22일" 또는 연도가 붙은 "2026-12-22"·"2026.12.22"만 봅니다("3.8점"은 날짜가 아님).
_DATE = re.compile(
    r"(?:(\d{4})\s*년\s*)?(\d{1,2})\s*월\s*(\d{1,2})\s*일|(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})"
)
_YEAR_MONTH = re.compile(r"(\d{4})\s*(?:년\s*|[.\-])\s*(\d{1,2})\s*월?")
_CLOCK = re.compile(r"(\d{1,2}):(\d{2})")
_HOUR = re.compile(r"(?:(오전|오후)\s*)?(\d{1,2})\s*시(?!간)")
_COUNT = re.compile(r"(\d[\d,]*)\s*(시간|개월|달|주|일|회|건|분|세|%|퍼센트|차|년)")
# 수급·인정 여부를 단정하는 문장. 숫자가 없어도 근거를 넘어설 수 있어 모델에 묻습니다.
RISKY = re.compile(
    r"받을 수 (있|없)|받으실 수 (있|없)|못 받|수급(이|할 수|은) (가능|불가능|안 ?돼|돼)"
    r"|인정(이 )?(돼|되지 않|안 ?돼|받을 수|이 안)|불인정|부정수급(이에요|입니다|에 해당|이 돼)"
)


def _num(text: str) -> int:
    return int(text.replace(",", ""))


def _amount_value(digits: str, unit: str) -> int:
    value = _num(digits)
    for ch in unit:
        value *= _MULTIPLIERS[ch]
    return value


def claims(text: str) -> set[str]:
    """글 속 숫자 주장을 견줄 수 있는 모양으로 꺼냅니다.

    예: "68,100원" → "68100원", "12월 22일" → "12-22", "오후 6시" → "18시", "두 달"은 꺼내지 않음.
    """
    found: set[str] = set()
    rest = text
    for m in _AMOUNT.finditer(rest):
        found.add(f"{_amount_value(m.group(1), m.group(2))}원")
    rest = _AMOUNT.sub(" ", rest)
    for m in _CLOCK.finditer(rest):
        found.add(f"{int(m.group(1))}시")
    rest = _CLOCK.sub(" ", rest)
    for m in _DATE.finditer(rest):
        month, day = (m.group(2), m.group(3)) if m.group(2) else (m.group(5), m.group(6))
        if 1 <= int(month) <= 12 and 1 <= int(day) <= 31:
            found.add(f"{int(month)}-{int(day)}")
    rest = _DATE.sub(" ", rest)
    for m in _YEAR_MONTH.finditer(rest):
        found.add(f"{m.group(1)}-{int(m.group(2))}")
    rest = _YEAR_MONTH.sub(" ", rest)
    for m in _HOUR.finditer(rest):
        hour = int(m.group(2)) + (12 if m.group(1) == "오후" and int(m.group(2)) < 12 else 0)
        found.add(f"{hour}시")
    rest = _HOUR.sub(" ", rest)
    for m in _COUNT.finditer(rest):
        found.add(f"{_num(m.group(1))}{_UNIT_ALIASES.get(m.group(2), m.group(2))}")
    return found


def _bare_numbers(text: str) -> set[str]:
    """단위 없이 적힌 숫자(facts의 "remaining": 1 같은 값). 코드가 계산한 값은 단위가 없습니다."""
    return {str(_num(n)) for n in re.findall(r"\d[\d,]*", text)}


def _value_of(claim: str) -> str:
    return re.sub(r"[^\d]", "", claim.split("-")[-1]) if "-" in claim else re.sub(r"\D", "", claim)


_SINO = {"일": 1, "이": 2, "삼": 3, "사": 4, "오": 5, "육": 6, "칠": 7, "팔": 8, "구": 9}
_NATIVE = {
    "한": 1, "두": 2, "세": 3, "네": 4, "다섯": 5,
    "여섯": 6, "일곱": 7, "여덟": 8, "아홉": 9, "열": 10,
}  # fmt: skip
_KOREAN_COUNT = re.compile(
    r"(?<![가-힣])((?:[일이삼사오육칠팔구]?십)?[일이삼사오육칠팔구]?|"
    + "|".join(sorted(_NATIVE, key=len, reverse=True))
    # "십일월"처럼 뒤에 "월"이 오면 날짜라 일수로 바꾸지 않습니다.
    + r")\s*(년|개월|달|주|일|시간|번|건|회)(?!월)"
)


def _sino_value(word: str) -> int | None:
    if not word:
        return None
    if "십" not in word:
        return _SINO.get(word)
    tens, _, ones = word.partition("십")
    return (_SINO.get(tens, 1) if tens else 1) * 10 + (_SINO.get(ones, 0) if ones else 0)


def korean_counts(text: str) -> str:
    """한글로 쓴 수("칠 년", "두 달", "열 번")를 숫자로 바꾼 글. 사용자 말을 근거로 견줄 때."""

    def to_digits(m: re.Match[str]) -> str:
        value = _NATIVE.get(m.group(1)) or _sino_value(m.group(1))
        return f"{value}{m.group(2)}" if value else m.group(0)

    return _KOREAN_COUNT.sub(to_digits, text)


class Evidence:
    """이번 턴의 근거. 숫자 주장 집합과 모델 판정에 넘길 글을 함께 둡니다.

    사용자는 "보험 칠 년 부었는데"처럼 수를 한글로 말하기도 해서, 숫자로 바꾼 글도 근거로 봅니다
    ("7년이면 240일이에요"가 근거 없는 숫자로 빠지지 않게).
    """

    def __init__(self, texts: Iterable[str]) -> None:
        joined = "\n".join(t for t in texts if t)
        self.text = joined
        # 바꾼 글은 단위가 붙은 주장만 더합니다("칠 년"의 7을 단위 없이 넣으면 "7개월"도 통과).
        self.claims = claims(joined) | claims(korean_counts(joined))
        self.bare = _bare_numbers(joined)

    @classmethod
    def of_turn(cls, facts: dict[str, Any], messages: Sequence[AnyMessage]) -> Evidence:
        texts = [json.dumps(facts, ensure_ascii=False)]
        texts += [str(m.content) for m in messages if isinstance(m, HumanMessage | ToolMessage)]
        return cls(texts)

    def ungrounded(self, sentence: str) -> list[str]:
        """근거에 없는 숫자 주장. 단위까지 같으면 통과, 아니면 같은 숫자가 근거에 있어야 합니다."""
        return [
            c for c in claims(sentence) if c not in self.claims and _value_of(c) not in self.bare
        ]


class SupportVerdict(BaseModel):
    supported: bool


def supported_by_model(sentence: str, evidence: Evidence) -> bool:
    """단정 문장이 근거로 뒷받침되는지 작은 모델에 묻습니다.

    묻지 못하면 뒷받침되지 않은 것으로 봅니다(수급 여부를 근거 없이 단정하는 것이 더 위험해서).
    """
    model = gateway.get_chat_model("extract").with_structured_output(SupportVerdict)
    try:
        verdict = model.invoke(
            [
                SystemMessage(load_prompt(SUPPORT_PROMPT)),
                HumanMessage(
                    f"<evidence>\n{evidence.text[:EVIDENCE_MAX_CHARS]}\n</evidence>\n"
                    f"<sentence>\n{sentence}\n</sentence>"
                ),
            ]
        )
    except Exception as exc:  # noqa: BLE001 — 판정 실패는 그 문장만 빼고 대화는 이어 갑니다
        logger.warning("support_check_failed", extra={"code": gateway.to_app_error(exc).code})
        return False
    return verdict.supported


class SentenceChecker:
    """문장 관문(output.SentenceStream)에 끼우는 검사. 통과하지 못한 문장은 보내지 않습니다."""

    def __init__(self, evidence: Evidence) -> None:
        self.evidence = evidence
        self.model_checks = 0
        self.failed = 0

    def __call__(self, sentence: str) -> bool:
        if missing := self.evidence.ungrounded(sentence):
            logger.info("sentence_ungrounded_number", extra={"count": len(missing)})
            self.failed += 1
            return False
        if RISKY.search(sentence) and self.model_checks < MAX_MODEL_CHECKS:
            self.model_checks += 1
            if not supported_by_model(sentence, self.evidence):
                logger.info("sentence_unsupported_claim")
                self.failed += 1
                return False
        return True


# ── 근거 줄 ─────────────────────────────────────────────


def _term_overlap(terms: str, answer_grams: set[str]) -> float:
    grams = set(bigrams(terms))
    return len(grams & answer_grams) / len(grams) if grams else 0.0


def used_in_answer(item_text: str, key_terms: str, answer: str, body: str = "") -> bool:
    """붙인 근거를 답에 썼는지: 근거의 숫자가 답에 나왔거나, 규칙명·증빙 이름이 나왔거나,
    내용을 풀어 썼는지(내용 글자 묶음이 답에 많이 나옴)."""
    if claims(item_text) & claims(answer):
        return True
    answer_grams = set(bigrams(answer))
    if _term_overlap(key_terms, answer_grams) >= CARD_TERM_OVERLAP:
        return True
    return bool(body) and _term_overlap(body, answer_grams) >= CARD_BODY_OVERLAP
