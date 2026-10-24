"""개인정보 탐지·가림 (N-02, AI 설계 5.5). 번호는 모두 합성 값입니다."""

import pytest

from app.agent.input.pii import PiiKind, detect, has_blocking, mask

# 생년월일이 유효한 합성 주민번호와 Luhn을 통과하는 합성 카드번호
RRN = "800101-1234567"
FOREIGN = "800101-5234567"
CARD = "4111-1111-1111-1111"


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        (f"제 주민번호는 {RRN}이에요", PiiKind.RRN),
        (f"외국인등록번호 {FOREIGN}", PiiKind.FOREIGNER_RRN),
        (f"카드 {CARD}로 냈어요", PiiKind.CARD),
        ("계좌는 123-456789-01-234입니다", PiiKind.ACCOUNT),
        ("연락처 010-1234-5678", PiiKind.PHONE),
        ("메일 test.user@example.com 으로", PiiKind.EMAIL),
    ],
)
def test_detects_each_kind(text: str, kind: PiiKind) -> None:
    assert [f.kind for f in detect(text)] == [kind]


def test_mask_replaces_with_tokens_and_keeps_rest() -> None:
    masked, findings = mask(f"주민번호 {RRN}, 전화 010-1234-5678")

    assert masked == "주민번호 [주민번호], 전화 [전화]"
    assert {f.kind for f in findings} == {PiiKind.RRN, PiiKind.PHONE}
    assert not has_blocking(masked)


def test_has_blocking_for_grade_zero() -> None:
    assert has_blocking(f"이거 {RRN} 맞아요?")
    assert not has_blocking("전화는 010-1234-5678이에요")


@pytest.mark.parametrize(
    "text",
    [
        "2026-10-21에 면접 봤어요",  # 날짜
        "월급은 2,500,000원이었어요",  # 금액
        "4차 실업인정일이 12월 22일이에요",  # 회차·날짜
        "991399-1234567",  # 생년월일이 없는 날짜라 주민번호 아님
        "4111-1111-1111-1112",  # Luhn 실패
        "2004.03 ~ 2026.09 근무",  # 경력 기간
    ],
)
def test_ordinary_sentences_are_not_flagged(text: str) -> None:
    assert [f.kind for f in detect(text) if f.blocking] == []


def test_fullwidth_hyphen_rrn_is_blocked() -> None:
    text = "번호는 800101－1234567이에요"
    assert has_blocking(text)
    assert "[주민번호]" in mask(text)[0]
