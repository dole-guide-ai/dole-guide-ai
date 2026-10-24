import pytest

from app.agent.masking import mask


@pytest.mark.parametrize(
    ("text", "hidden"),
    [
        ("제 주민번호 650101-1234567이에요", "1234567"),
        ("앞자리는 650101, 뒷자리는 1234567이에요", "1234567"),
        ("연락처는 010-0000-0000이에요", "010-0000-0000"),
        ("번호 010 0000 0000으로 연락 주세요", "010 0000 0000"),
        ("메일은 a.b@example.com이에요", "a.b@example.com"),
        ("제 이름은 홍길동이에요", "홍길동"),
    ],
)
def test_mask_hides_personal_values(text: str, hidden: str) -> None:
    masked, found = mask(text)

    assert hidden not in masked
    assert found


@pytest.mark.parametrize("text", ["2026-12-08에 고용24로 지원했어요", "2004년 3월부터 일했어요"])
def test_mask_keeps_dates(text: str) -> None:
    assert mask(text) == (text, [])
