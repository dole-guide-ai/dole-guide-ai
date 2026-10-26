"""개인정보 탐지·가림 (N-02, AI 설계 5.3·5.5). LLM을 쓰지 않는 순수 함수입니다.

preprocess(입력), gateway(외부 호출 직전), LangSmith 마스킹, 출력 검사가 모두 이 함수를 씁니다.

- 등급 0(금지): 주민등록번호·외국인등록번호(생년월일 유효성), 카드번호(Luhn), 계좌번호.
  보낼 글에 남아 있으면 외부로 보내지 않습니다(`has_blocking`, gateway fail-closed).
- 등급 1(직접 식별): 전화번호·이메일 → `[전화]`·`[이메일]` 토큰.
- 실명은 정규식으로 찾을 수 없어 입력 안내와 칸을 만들지 않는 것으로 막습니다(5.5). 다만
  "제 이름은 OOO이에요" 같은 자기소개 말투는 `[이름]`으로 가립니다(등급 1).
- 대화에서 자주 나오는 변형도 잡습니다(#176 보안 검토): 점으로 나눈 주민번호, "뒷자리는 …"처럼
  뒷자리만 말한 주민번호, 붙여 쓰거나 공백·밑줄·슬래시로 나눈 10자리 이상 계좌·카드 번호,
  한글이 섞인 이메일 주소.

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
    NAME = "name"  # 자기소개 말투의 이름만
    SECRET = "secret"  # 비밀번호(로그인을 대신 해 달라는 말 등)
    NUMBER = "number"  # 주민번호·카드 모양인데 검증에 떨어진 긴 숫자 (가리되 차단 등급은 아님)


BLOCKING = frozenset({PiiKind.RRN, PiiKind.FOREIGNER_RRN, PiiKind.CARD, PiiKind.ACCOUNT})
TOKENS = {
    PiiKind.RRN: "[주민번호]",
    PiiKind.FOREIGNER_RRN: "[외국인번호]",
    PiiKind.CARD: "[카드번호]",
    PiiKind.ACCOUNT: "[계좌번호]",
    PiiKind.PHONE: "[전화]",
    PiiKind.EMAIL: "[이메일]",
    PiiKind.NAME: "[이름]",
    PiiKind.SECRET: "[비밀번호]",
    PiiKind.NUMBER: "[번호]",
}

# 숫자 사이 구분자: 하이픈·공백 (유니코드 하이픈 U+2010, 마이너스 U+2212, 전각 하이픈 U+FF0D 포함)
_SEP = r"[-‐−－.\s]?"
_RRN = re.compile(rf"(?<!\d)(\d{{6}}){_SEP}([1-8])(\d{{6}})(?!\d)")
_CARD = re.compile(rf"(?<!\d)(?:\d{{4}}{_SEP}){{3}}\d{{4}}(?!\d)")
# 은행 계좌: 숫자 2~6 묶음이 하이픈으로 3~4개 이어지고 숫자 10~14자리 (전화·날짜와 구분)
_ACCOUNT = re.compile(r"(?<![\d-])\d{2,6}(?:-\d{2,6}){2,3}(?![\d-])")
_PHONE = re.compile(r"(?<!\d)(?:01[016789]|0[2-6]\d?)[-.\s]?\d{3,4}[-.\s]?\d{4}(?!\d)")
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# 한글이 섞인 이메일("홍길동@회사.한국"). 영문 패턴이 못 잡은 것만 봅니다.
_EMAIL_UNICODE = re.compile(r"[\w.%+-]+@[\w-]+(?:\.[\w-]+)+")
# 뒷자리만 따로 말한 주민번호. 아무 7자리 숫자(금액 등)를 가리지 않도록 앞에 단서가 있을 때만.
_RRN_BACK = re.compile(r"(?:뒷자리|뒷번호|뒤\s*7자리|주민(?:등록)?번호)\D{0,10}?([1-8]\d{6})(?!\d)")
# 붙여 쓰거나 공백·점·밑줄·슬래시로 나눈 긴 번호(계좌·카드). 시각의 ":"·"시"도 이어 봐야
# "2026.12.10 10:99"처럼 분이 틀린 숫자를 날짜로 빼지 않습니다. 숫자 사이 구분자는 3글자까지.
# 숫자 10~19자리만 보고, 통째로 날짜(+시각)인 것("2026-12-08 10")만 뺍니다(_is_date_time).
_LONG_NUMBER = re.compile(r"(?<![\d-])\d(?:[\s.\-–—_/:시]{0,3}\d){9,}(?!\d)")
_LONG_DIGITS = range(10, 20)
# 서류의 날짜는 "2026. 12. 10." "2026.12.10 10:00"처럼 점 뒤 띄어쓰기·끝 점·시각이 붙기도 합니다.
# 시각은 날짜 뒤에 띄어쓰기가 있어야 붙습니다("1002.12.1234" 같은 계좌를 날짜로 보지 않게).
_DATE_TIME = re.compile(
    r"(\d{4})\s*[-./]\s*(\d{1,2})\s*[-./]\s*(\d{1,2})\.?"
    r"(?:\s+(\d{1,2})(?:\s*[:시]\s*(\d{1,2})?)?)?"
)
# 날짜·시각이 띄어쓰기로 나뉘는 최대 조각 수: "2026." "12." "10." "10시" "30"
DATE_TIME_MAX_PIECES = 5
_DATE_YEARS = range(1900, 2100)
_HOURS = range(24)
_MINUTES = range(60)
# 같은 말 안에 유효한 생년월일 6자리가 먼저 나오면, 뒤에 따로 말한 7자리도 뒷자리로 봅니다.
_BIRTH6 = re.compile(r"(?<!\d)(\d{6})(?!\d)")
_BACK7 = re.compile(r"(?<!\d)([1-8])\d{6}(?!\d)")
# 자기소개 말투의 이름("제 이름은 홍길동이에요", "제 이름은 홍길동").
# "몰라요"처럼 요·다로 끝나는 말은 이름이 아니라서 뺍니다.
_NAME = re.compile(
    r"(?:이름은|이름이)\s*([가-힣]{2,4})(?<![요다죠까네])(?=\s*(?:이에요|예요|입니다|이고|이요|[.,!]|$))"
)
# 생년 바로 뒤에 말한 이름("1965년생 박말순이에요"). 단서가 분명한 '년생' 뒤만 봅니다.
_NAME_AFTER_BIRTH = re.compile(
    r"\d{2,4}\s*년생\s*([가-힣]{2,4})(?<![요다죠까네])(?=\s*(?:이에요|예요|입니다|이고|이요|[.,!]|$))"
)
# 비밀번호 단서 뒤의 영문·숫자·기호 덩어리("비밀번호가 bokja123!인데"). 한글 말은 건드리지 않습니다.
_SECRET = re.compile(
    # 긴 영어 단서(mypassword·passwords 등)는 앞뒤 글자와 상관없이, 짧은 pw는 단어 전체이거나
    # 바로 뒤에 :·=가 올 때만 봅니다("upward1234" 같은 말은 건드리지 않음).
    r"(?:비밀\s*번호|비번|암호|패스워드|(?:password|passwd|pwd)s?"
    r"|(?<![A-Za-z])pw(?![A-Za-z])|pw(?=\s*[:=：]))"
    r"\s*(?:은|는|가|이|[:=：])?\s*['\"]?"
    r"([!-~]{4,})",
    re.IGNORECASE,
)
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
    # 이메일을 먼저 찾아야 주소 안의 숫자만 가려지고 주소 일부가 남는 일이 없습니다.
    # 두 패턴이 겹치면 긴 쪽("홍길동foo@ex.com" 전체)을 골라 한글 부분이 남지 않게 합니다.
    emails = [m.span() for p in (_EMAIL, _EMAIL_UNICODE) for m in p.finditer(text)]
    for start, end in sorted(emails, key=lambda span: span[0] - span[1]):
        if not _overlaps(found, start, end):
            found.append(Finding(PiiKind.EMAIL, start, end))
    for m in _RRN.finditer(text):
        if _valid_birth(m[1], m[2]) and not _overlaps(found, m.start(), m.end()):
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
    _add_extra(text, found)
    _add_secrets(text, found)
    return sorted(found, key=lambda f: f.start)


def _add_secrets(text: str, found: list[Finding]) -> None:
    """비밀번호 자리를 가립니다. 다른 패턴이 그 안의 일부(숫자·이메일 모양)만 찾았으면 두 자리를
    합쳐 통째로 가리고, 겹친 것 중 등급 0(주민번호 등)이 있으면 그 종류를 남겨 차단이 풀리지 않게
    합니다."""
    for m in _SECRET.finditer(text):
        start, end = m.span(1)
        inside = [f for f in found if f.start < end and start < f.end]
        for f in inside:
            found.remove(f)
        blocking = next((f.kind for f in inside if f.blocking), None)
        start = min([start, *(f.start for f in inside)])
        end = max([end, *(f.end for f in inside)])
        found.append(Finding(blocking or PiiKind.SECRET, start, end))


def _is_date_time(text: str) -> bool:
    """통째로 날짜(+시각 숫자)인지. 앞부분만 날짜인 계좌("3333-01-1234567")는 날짜가 아닙니다."""
    m = _DATE_TIME.fullmatch(text.strip())
    if not m or int(m[1]) not in _DATE_YEARS:
        return False
    if m[4] is not None and int(m[4]) not in _HOURS:
        return False
    if m[5] is not None and int(m[5]) not in _MINUTES:
        return False
    try:
        date(int(m[1]), int(m[2]), int(m[3]))
    except ValueError:
        return False
    return True


def _is_birth(yymmdd: str) -> bool:
    return any(_valid_birth(yymmdd, gender) for gender in "13")


def _is_number(text: str) -> bool:
    digits = re.sub(r"\D", "", text)
    return len(digits) in _LONG_DIGITS and not _is_date_time(text)


def _date_time_pieces(text: str, pieces: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """띄어쓰기 조각 중 날짜(+시·분)를 이루는 조각 범위들 [시작, 끝)."""
    found, i = [], 0
    while i < len(pieces):
        size = next(
            (
                k
                for k in range(DATE_TIME_MAX_PIECES, 0, -1)
                if i + k <= len(pieces) and _is_date_time(text[pieces[i][0] : pieces[i + k - 1][1]])
            ),
            0,
        )
        if size:
            found.append((i, i + size))
        i += size or 1
    return found


def _number_groups(m: re.Match[str]) -> list[tuple[int, int]]:
    """긴 숫자 덩어리에서 가릴 번호 자리들.

    "1234567890 9876543210"처럼 띄어 쓴 번호 둘은 합치면 너무 길어 통째로는 번호가 아니므로,
    띄어쓰기로 나눈 조각을 이어 붙여 번호 길이가 되는 묶음을 가장 많이 덮도록 고릅니다.
    """
    pieces = [p.span() for p in re.finditer(r"\S+", m[0]) if re.search(r"\d", p[0])]
    counts = [sum(ch.isdigit() for ch in m[0][s:e]) for s, e in pieces]
    # 날짜(+시각) 조각의 숫자는 덮어도 점수에 넣지 않아, "2026.12.10 1234567890"에서 날짜까지
    # 계좌로 묶지 않습니다. 날짜 모양 계좌("2026.12.10 99")는 뒤 숫자 때문에 그대로 묶입니다.
    weights = list(counts)
    for start, end in _date_time_pieces(m[0], pieces):
        weights[start:end] = [0] * (end - start)
    longest = max(_LONG_DIGITS)
    # covered[i]: 앞 조각 i개로 덮은 숫자 수, back[i]: 그때 마지막 묶음의 첫 조각(None이면 건너뜀)
    covered, back = [0], [None]
    for i in range(1, len(pieces) + 1):
        covered.append(covered[i - 1])
        back.append(None)
        digits = weight = 0
        # 묶음은 번호 길이(최대 19자리)를 넘을 수 없으니 그 안에서만 찾습니다(긴 입력에도 선형).
        for j in range(i - 1, -1, -1):
            digits += counts[j]
            weight += weights[j]
            if digits > longest:
                break
            span = m[0][pieces[j][0] : pieces[i - 1][1]]
            if _is_number(span) and covered[j] + weight > covered[i]:
                covered[i], back[i] = covered[j] + weight, j
    groups = []
    i = len(pieces)
    while i > 0:
        if (j := back[i]) is None:
            i -= 1
            continue
        groups.append((m.start() + pieces[j][0], m.start() + pieces[i - 1][1]))
        i = j
    return groups[::-1]


def _add_extra(text: str, found: list[Finding]) -> None:
    """위 기본 패턴이 놓치는 대화 속 변형. 이미 찾은 자리와 겹치면 넘깁니다."""
    for m in _RRN_BACK.finditer(text):
        if not _overlaps(found, m.start(1), m.end(1)):
            found.append(Finding(PiiKind.RRN, m.start(1), m.end(1)))
    if birth := next((b for b in _BIRTH6.finditer(text) if _is_birth(b[1])), None):
        for m in _BACK7.finditer(text, birth.end()):
            if not _overlaps(found, m.start(), m.end()):
                found.append(Finding(PiiKind.RRN, m.start(), m.end()))
    for m in _LONG_NUMBER.finditer(text):
        for start, end in _number_groups(m):
            if _overlaps(found, start, end):
                continue
            # 주민번호·카드 모양인데 검증(생년월일·Luhn)에서 떨어진 숫자도 가립니다
            # (차단 등급은 아님).
            shaped = _RRN.fullmatch(text[start:end]) or _CARD.fullmatch(text[start:end])
            kind = PiiKind.NUMBER if shaped else PiiKind.ACCOUNT
            found.append(Finding(kind, start, end))
    for pattern, kind in ((_NAME, PiiKind.NAME), (_NAME_AFTER_BIRTH, PiiKind.NAME)):
        for m in pattern.finditer(text):
            if not _overlaps(found, m.start(1), m.end(1)):
                found.append(Finding(kind, m.start(1), m.end(1)))


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
