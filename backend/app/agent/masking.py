"""모델에 보내기 전에 개인정보를 가립니다 (설계 초안 결정 ⑦).

주민번호·카드·계좌·전화·이메일은 팀 공용 `app/agent/input/pii.py`(`pii.mask`)가 먼저 가립니다.
여기에는 pii.mask가 놓치는 경우만 보강합니다. 가린 원문은 어디에도 남기지 않습니다.

- 주민번호 뒷자리만 따로 말한 경우("뒷자리는 1234567"), 점으로 구분한 주민번호
- 구분자 없이 붙여 쓰거나 공백·밑줄·슬래시로 나눈 계좌·카드 번호(숫자 10자리 이상)
- "제 이름은 OOO" 같은 자기소개 말투의 이름
"""

import re

from app.agent.input.pii import TOKENS, PiiKind
from app.agent.input.pii import mask as pii_mask

RRN_TOKEN = TOKENS[PiiKind.RRN]
ACCOUNT_TOKEN = TOKENS[PiiKind.ACCOUNT]
NAME_TOKEN = "[이름]"

# 숫자 경계는 \b 대신 (?<!\d)·(?!\d)로 봅니다. 한글에 붙은 숫자("계좌110…")도 잡습니다.
RRN_DOT = re.compile(r"(?<!\d)\d{6}\s*\.\s*[1-8]\d{6}(?!\d)")
RRN_BACK = re.compile(r"(?<!\d)[1-8]\d{6}(?!\d)")
# 숫자 사이 구분자는 3글자까지 봅니다. 국내 계좌는 10~14자리라 10자리 미만은 날짜·금액 오탐을
# 막으려고 가리지 않습니다(2026-12-08은 8자리).
LONG_NUMBER = re.compile(r"(?<!\d)\d(?:[\s.\-–—_/]{0,3}\d){9,}(?!\d)")
NAME = re.compile(r"(이름은|이름이)\s*[가-힣]{2,4}(?=\s*(?:이에요|예요|입니다|이고|이요|$))")

EXTRA_PATTERNS = ((RRN_DOT, RRN_TOKEN), (LONG_NUMBER, ACCOUNT_TOKEN), (RRN_BACK, RRN_TOKEN))


def mask(text: str) -> tuple[str, list[str]]:
    """가린 글과 가린 종류(토큰) 목록을 돌려줍니다."""
    text, findings = pii_mask(text)
    found = [TOKENS[f.kind] for f in findings]
    for pattern, token in EXTRA_PATTERNS:
        text, count = pattern.subn(token, text)
        if count:
            found.append(token)
    text, count = NAME.subn(lambda m: f"{m.group(1)} {NAME_TOKEN}", text)
    if count:
        found.append(NAME_TOKEN)
    return text, found
