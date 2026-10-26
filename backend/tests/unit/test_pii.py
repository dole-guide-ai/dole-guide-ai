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


@pytest.mark.parametrize(
    ("text", "hidden", "kind"),
    [
        ("주민번호 6501011234567이요", "1234567", PiiKind.RRN),  # 붙여 씀
        ("주민번호 650101.1234567", "1234567", PiiKind.RRN),  # 점 구분
        ("앞자리는 650101, 뒷자리는 1234567이에요", "1234567", PiiKind.RRN),  # 뒷자리만
        ("계좌110-234-567890이에요", "567890", PiiKind.ACCOUNT),  # 한글에 붙음
        ("계좌번호 11023456789012", "56789", PiiKind.ACCOUNT),  # 구분자 없음
        ("계좌 110 - 234 - 567890이요", "567890", PiiKind.ACCOUNT),  # 띄운 하이픈
        ("카드 1234  5678  1234  5678", "5678", PiiKind.ACCOUNT),  # Luhn 아님·여러 칸
        ("계좌 110_234/567890", "567890", PiiKind.ACCOUNT),  # 밑줄·슬래시
        ("010.1234.5678로 주세요", "5678", PiiKind.PHONE),  # 점 구분 전화
        ("메일은 홍길동@회사.한국이에요", "홍길동@회사", PiiKind.EMAIL),  # 한글 이메일
        ("제 이름은 홍길동이에요", "홍길동", PiiKind.NAME),  # 자기소개 이름
    ],
)
def test_conversation_variants_are_masked(text: str, hidden: str, kind: PiiKind) -> None:
    """대화에서 나오는 변형 (#176 보안 검토 지적)."""
    masked, findings = mask(text)

    assert hidden not in masked
    assert kind in {f.kind for f in findings}


@pytest.mark.parametrize(
    "text", ["월급 2500000원이요", "2026-12-08 10시에 면접", "20261208 면접", "이름은 몰라요"]
)
def test_variants_do_not_overmask(text: str) -> None:
    assert mask(text) == (text, [])


@pytest.mark.parametrize(
    ("text", "hidden", "kind"),
    [
        ("계좌 3333-01-1234567이요", "1234567", PiiKind.ACCOUNT),  # 날짜로 시작하는 계좌
        ("메일 800101-1234567@ex.com 이에요", "@ex.com", PiiKind.EMAIL),  # 이메일 통째로
        ("제 이름은 홍길동", "홍길동", PiiKind.NAME),  # 문장 끝 이름
        ("앞자리 650101 그리고 1234567이요", "1234567", PiiKind.RRN),  # 생년월일 뒤 7자리
    ],
)
def test_security_review_cases_are_masked(text: str, hidden: str, kind: PiiKind) -> None:
    """#176 보안 검토 두 번째 지적."""
    masked, findings = mask(text)

    assert hidden not in masked
    assert kind in {f.kind for f in findings}


@pytest.mark.parametrize("text", ["991399-1234567", "4111-1111-1111-1112"])
def test_failed_validation_numbers_are_masked_but_not_blocking(text: str) -> None:
    masked, findings = mask(text)

    assert masked == "[번호]"
    assert not has_blocking(text)


def test_fullwidth_hyphen_rrn_is_blocked() -> None:
    text = "번호는 800101－1234567이에요"
    assert has_blocking(text)
    assert "[주민번호]" in mask(text)[0]


def test_four_group_account_is_not_hidden_by_phone() -> None:
    assert has_blocking("계좌 12-010-1234-5678로 주세요")
    assert not has_blocking("전화 010-1234-5678로 주세요")


def test_unicode_local_part_email_is_masked_whole() -> None:
    """코드래빗 지적: ASCII 부분만 이메일로 잡아 앞의 한글이 남던 경우."""
    masked, _ = mask("메일 홍길동foo@example.com 으로 주세요")

    assert "홍길동" not in masked
    assert "[이메일]" in masked


def test_two_spaced_numbers_are_both_masked() -> None:
    """코드래빗 지적: 띄어 쓴 번호 둘이 합쳐 너무 길어져 둘 다 남던 경우."""
    text = "계좌 1234567890 9876543210 둘 다예요"
    masked, _ = mask(text)

    assert "1234567890" not in masked
    assert "9876543210" not in masked
    assert has_blocking(text)


def test_very_long_spaced_digits_stay_fast() -> None:
    """보안 검토 지적: 띄어 쓴 숫자가 아주 많아도 나누기 계산이 길어지지 않아야 합니다."""
    import time

    text = " ".join(["1"] * 20000)
    started = time.perf_counter()
    mask(text)

    assert time.perf_counter() - started < 2


def test_name_after_birth_year_is_masked():
    # 골든셋 M-027: "1965년생 박말순이에요"의 이름이 모델 입력에 남던 문제
    assert mask("1965년생 박말순이에요")[0] == "1965년생 [이름]이에요"
    assert mask("61년생 김철수입니다. 반가워요")[0] == "61년생 [이름]입니다. 반가워요"
    assert mask("1965년생이에요")[0] == "1965년생이에요"


def test_password_is_masked_but_korean_words_are_kept():
    # 골든셋 M-031: 로그인해 달라며 알려 준 비밀번호
    masked, findings = mask("고용24 비밀번호가 bokja123!인데 로그인 좀 해줘요")
    assert masked == "고용24 비밀번호가 [비밀번호]인데 로그인 좀 해줘요"
    assert not any(f.blocking for f in findings)
    assert mask("제 비번은 abcd1234 입니다")[0] == "제 비번은 [비밀번호] 입니다"
    assert mask("비밀번호를 잊어버렸어요")[0] == "비밀번호를 잊어버렸어요"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("PW: Qwer!2345", "PW: [비밀번호]"),
        ("pwd='abc12345'", "pwd='[비밀번호]"),
        ("암호 = zxcv9876 이에요", "암호 = [비밀번호] 이에요"),
        # 긴 숫자·이메일 모양이 섞여도 일부만 가려지지 않고 통째로 가림.
        # 계좌번호 모양(등급 0)이면 차단이 풀리지 않게 그 종류가 이김
        ("비번 12345678901234 이에요", "비번 [계좌번호] 이에요"),
        ("비밀번호는 me@x.co12 입니다", "비밀번호는 [비밀번호] 입니다"),
    ],
)
def test_password_variants_are_masked_whole(text: str, expected: str):
    assert mask(text)[0] == expected


def test_rrn_given_as_password_still_blocks():
    # 비밀번호 자리에 주민번호를 넣어도 등급 0 차단이 풀리지 않아야 함 (보안 검토)
    text = "비밀번호 900101-1234567 이에요"
    assert has_blocking(text)
    assert mask(text)[0] == "비밀번호 [주민번호] 이에요"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("mypassword: Abcd1234", "mypassword: [비밀번호]"),
        ("newpassword=Abcd1234", "newpassword=[비밀번호]"),
        ("passwords: xyz12345", "passwords: [비밀번호]"),
        ("userpw=abc12345", "userpw=[비밀번호]"),
        # 짧은 pw가 다른 단어 속에 있으면 건드리지 않음
        ("upward1234 방향", "upward1234 방향"),
    ],
)
def test_password_cues_in_longer_words(text: str, expected: str):
    assert mask(text)[0] == expected


@pytest.mark.parametrize(
    "text",
    [
        "면접 일시 2026. 12. 10. 10:00",
        "2026.12.10 10:00 면접",
        "신청일 2026. 09. 15.",
        "2026.12.10 10시 30분",
    ],
)
def test_document_dates_are_not_numbers(text: str):
    # 골든셋 F-025: 면접확인서 날짜가 [계좌번호]로 가려져 면접일을 저장하지 못하던 문제
    assert mask(text)[0] == text
    assert not has_blocking(text)


@pytest.mark.parametrize(
    "text",
    ["1002.12.1234", "2026.12.1099", "2026.12.10 99", "3026.12.10 1234", "2026.12.10 10:99"],
)
def test_account_shaped_like_date_is_still_masked(text: str):
    # 날짜 판정을 넓히면서 계좌번호가 날짜로 빠져나가지 않게 (보안 검토)
    assert mask(text)[0] != text


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("면접 2026.12.10 10:00 1234567890", "면접 2026.12.10 10:00 [계좌번호]"),
        ("2026.12.10 1234567890", "2026.12.10 [계좌번호]"),
        ("2026.12.10 10시 1234567890", "2026.12.10 10시 [계좌번호]"),
        ("2026. 12. 10. 10:00 1234567890", "2026. 12. 10. 10:00 [계좌번호]"),
        ("2026. 12. 10. 10시 30분 1234567890", "2026. 12. 10. 10시 30분 [계좌번호]"),
    ],
)
def test_account_after_date_keeps_the_date(text: str, expected: str):
    assert mask(text)[0] == expected
