"""모델에 보내기 전에 개인정보를 가립니다 (설계 초안 결정 ⑦).

모양이 정해진 값(주민등록번호·휴대폰·이메일·계좌 같은 긴 숫자)은 정규식으로 가리고,
이름은 "제 이름은 OOO" 같은 자기소개 말투일 때만 가립니다. 가린 원문은 어디에도 남기지 않습니다.
"""

import re

RRN = re.compile(r"\d{6}\s*-\s*[1-8]\d{6}")
# "뒷자리는 1234567"처럼 주민번호 뒷자리만 따로 말한 경우
RRN_BACK = re.compile(r"(?<!\d)[1-8]\d{6}(?!\d)")
PHONE = re.compile(r"01[016789][\s-]*\d{3,4}[\s-]*\d{4}")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# 계좌·카드처럼 하이픈으로 이어진 긴 숫자. 날짜(2026-12-08)는 건드리지 않습니다.
LONG_NUMBER = re.compile(r"\b\d{2,6}(?:-\d{2,6}){2,}\b(?<!\d{4}-\d{2}-\d{2})")
NAME = re.compile(r"(이름은|이름이)\s*[가-힣]{2,4}(?=\s*(?:이에요|예요|입니다|이고|이요|$))")

PATTERNS = (
    (RRN, "[주민번호]"),
    (PHONE, "[전화번호]"),
    (EMAIL, "[이메일]"),
    (LONG_NUMBER, "[번호]"),
    (RRN_BACK, "[주민번호]"),
)


def mask(text: str) -> tuple[str, list[str]]:
    """가린 글과 가린 종류 목록을 돌려줍니다."""
    found = []
    for pattern, label in PATTERNS:
        text, count = pattern.subn(label, text)
        if count:
            found.append(label)
    text, count = NAME.subn(lambda m: f"{m.group(1)} [이름]", text)
    if count:
        found.append("[이름]")
    return text, found
