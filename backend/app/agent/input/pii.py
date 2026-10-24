"""개인정보 탐지·가림 (N-02, AI 설계 5.3·5.5). LLM을 쓰지 않는 순수 함수입니다.

preprocess(입력), gateway(외부 호출 직전), LangSmith 마스킹, 출력 검사가 모두 이 함수를 씁니다.

- 등급 0(금지): 주민등록번호·외국인등록번호(생년월일 유효성), 카드번호(Luhn), 계좌번호.
  보낼 글에 남아 있으면 외부로 보내지 않습니다(`has_blocking`, gateway fail-closed).
- 등급 1(직접 식별): 전화번호·이메일 → `[전화]`·`[이메일]` 토큰.
- 실명은 정규식으로 찾을 수 없어 입력 안내와 칸을 만들지 않는 것으로 막습니다(5.5).

찾은 값 자체는 결과에 담지 않고 종류·위치만 돌려줍니다(로그·트레이스에 원문이 남지 않게).
"""

import re
from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class PiiKind(StrEnum):
    RRN = "rrn"  # 주민등록번호
    FOREIGNER_RRN = "foreigner_rrn"  # 외국인등록번호
    CARD = "card"
    ACCOUNT = "account"
    PHONE = "phone"
    EMAIL = "email"


BLOCKING = frozenset({PiiKind.RRN, PiiKind.FOREIGNER_RRN, PiiKind.CARD, PiiKind.ACCOUNT})
TOKENS = {
    PiiKind.RRN: "[주민번호]",
    PiiKind.FOREIGNER_RRN: "[외국인번호]",
    PiiKind.CARD: "[카드번호]",
    PiiKind.ACCOUNT: "[계좌번호]",
    PiiKind.PHONE: "[전화]",
    PiiKind.EMAIL: "[이메일]",
}

# 숫자 사이 구분자: 하이픈·공백 (유니코드 하이픈 U+2010, 마이너스 U+2212, 전각 하이픈 U+FF0D 포함)
_SEP = r"[-‐−－\s]?"
_RRN = re.compile(rf"(?<!\d)(\d{{6}}){_SEP}([1-8])(\d{{6}})(?!\d)")
_CARD = re.compile(rf"(?<!\d)(?:\d{{4}}{_SEP}){{3}}\d{{4}}(?!\d)")
# 은행 계좌: 숫자 2~6 묶음이 하이픈으로 3~4개 이어지고 숫자 10~14자리 (전화·날짜와 구분)
_ACCOUNT = re.compile(r"(?<![\d-])\d{2,6}(?:-\d{2,6}){2,3}(?![\d-])")
_PHONE = re.compile(r"(?<!\d)(?:01[016789]|0[2-6]\d?)[-.\s]?\d{3,4}[-.\s]?\d{4}(?!\d)")
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_ACCOUNT_DIGITS = range(10, 15)


@dataclass(frozen=True)
class Finding:
    kind: PiiKind
    start: int
    end: int

    @property
    def blocking(self) -> bool:
        return self.kind in BLOCKING


def _valid_birth(yymmdd: str, gender: str) -> bool:
    """뒷자리 첫 숫자로 세기를 정해 실제 있는 날짜인지 봅니다.

    1·2·5·6이면 1900년대, 3·4·7·8이면 2000년대입니다.
    """
    century = 1900 if gender in "1256" else 2000
    try:
        date(century + int(yymmdd[:2]), int(yymmdd[2:4]), int(yymmdd[4:6]))
    except ValueError:
        return False
    return True


def _luhn(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2:
            n = n * 2 - 9 if n * 2 > 9 else n * 2
        total += n
    return total % 10 == 0


def _overlaps(found: list[Finding], start: int, end: int) -> bool:
    return any(f.start < end and start < f.end for f in found)


_FOUR_GROUPS = 4


def _add_accounts(text: str, found: list[Finding], groups: int | None = None) -> None:
    for m in _ACCOUNT.finditer(text):
        if groups is not None and m[0].count("-") + 1 != groups:
            continue
        digits = re.sub(r"\D", "", m[0])
        if len(digits) in _ACCOUNT_DIGITS and not _overlaps(found, m.start(), m.end()):
            found.append(Finding(PiiKind.ACCOUNT, m.start(), m.end()))


def detect(text: str) -> list[Finding]:
    """찾은 개인정보의 종류·위치. 먼저 찾은 등급 0이 이기고, 같은 자리는 한 번만 셉니다."""
    found: list[Finding] = []
    for m in _RRN.finditer(text):
        if _valid_birth(m[1], m[2]):
            kind = PiiKind.RRN if m[2] in "1234" else PiiKind.FOREIGNER_RRN
            found.append(Finding(kind, m.start(), m.end()))
    for m in _CARD.finditer(text):
        digits = re.sub(r"\D", "", m[0])
        if _luhn(digits) and not _overlaps(found, m.start(), m.end()):
            found.append(Finding(PiiKind.CARD, m.start(), m.end()))
    # 네 묶음 계좌(12-010-1234-5678)는 전화번호보다 먼저 봅니다. 전화번호는 세 묶음까지라
    # 먼저 찾으면 계좌 안의 010-1234-5678만 전화로 가려지고 계좌(등급 0)를 놓칩니다.
    _add_accounts(text, found, groups=_FOUR_GROUPS)
    for m in _PHONE.finditer(text):
        if not _overlaps(found, m.start(), m.end()):
            found.append(Finding(PiiKind.PHONE, m.start(), m.end()))
    _add_accounts(text, found)
    for m in _EMAIL.finditer(text):
        found.append(Finding(PiiKind.EMAIL, m.start(), m.end()))
    return sorted(found, key=lambda f: f.start)


def mask(text: str) -> tuple[str, list[Finding]]:
    """찾은 자리를 토큰으로 바꾼 글과 찾은 목록."""
    findings = detect(text)
    out, last = [], 0
    for f in findings:
        out.append(text[last : f.start])
        out.append(TOKENS[f.kind])
        last = f.end
    out.append(text[last:])
    return "".join(out), findings


def has_blocking(text: str) -> bool:
    """보내려는 글에 등급 0이 있는지 (gateway fail-closed, AI 설계 5.5).

    gateway는 가린(`mask`) 글을 다시 이 함수로 검사하고, 그래도 남으면 호출하지 않습니다.
    """
    return any(f.blocking for f in detect(text))
