"""규칙표(data/rules/rule_table) 검증과 규칙 카드 찾기·근거 줄 (rules/rule_cards.py).

시트를 고쳐 다시 가져왔을 때 빈 칸·중복 ID·없는 출처가 서비스로 나가기 전에 여기서 걸립니다.
"""

import re

import pytest

from app.rules.rule_cards import (
    Profile,
    applies_to,
    cards_by_id,
    cards_for,
    cite_line,
    load_cards,
    load_sources,
    search_cards,
)

# 서비스 데이터에 남으면 안 되는 작업 흔적: 검수 표시, 규칙·출처 ID, 주소, 전달자 말투, 공백 표시
WORK_NOTE = re.compile(
    r"검수|확인 필요|미확인|미기재|(SRC|CHECK|ELIG|ACT|DUE|PROC|SUP)-\d|https?://|원문"
    r"|안내(한다|문이다)|수첩[은상]|\d+쪽|\d{4}년판|\d{4}-\d{2}-\d{2}:|자료 필요|미표기"
)


def test_rule_ids_are_unique_and_required_fields_filled() -> None:
    cards = load_cards()
    ids = [c.rule_id for c in cards]

    assert len(ids) == len(set(ids))
    assert all(c.rule_id and c.name and c.body for c in cards)


def test_every_card_has_known_source() -> None:
    sources = load_sources()

    assert all(c.source_ids and set(c.source_ids) <= sources.keys() for c in load_cards())


def test_cards_carry_no_work_notes() -> None:
    dirty = [
        (c.rule_id, key)
        for c in load_cards()
        for key, value in c.for_model().items()
        if key != "id" and WORK_NOTE.search(value)
    ]

    assert dirty == []


def test_source_dates_are_iso_or_empty() -> None:
    assert all(re.fullmatch(r"(\d{4}-\d{2}-\d{2})?", s.issued) for s in load_sources().values())


@pytest.mark.parametrize(
    ("query", "rule_id"),
    [
        ("이메일로 이력서 보냈는데 증빙은 뭐예요", "ACT-134"),
        ("취업포털로 지원했으면 뭘 내야 돼요", "ACT-133"),
        ("인정일 당일 몇 시까지 신청해야 해요", "DUE-093"),
        ("영어학원 다니는 것도 활동으로 돼요", "ACT-054"),
        ("봉사활동도 활동으로 쳐 줘요", "ACT-125"),
    ],
)
def test_search_finds_rule_for_explicit_question(query: str, rule_id: str) -> None:
    assert rule_id in [c.rule_id for c in search_cards(query)]


def test_search_skips_other_employment_types() -> None:
    targets = {c.target for c in search_cards("폐업 신고 기한", limit=10)}

    assert not any(t.startswith("자영업") for t in targets)


def test_search_without_words_returns_nothing() -> None:
    assert search_cards("?!") == []


def test_cite_line_dedupes_sources() -> None:
    cards = cards_by_id()
    same_source = [i for i, c in cards.items() if c.source_ids == ("SRC-001",)][:2]

    line = cite_line(same_source)

    assert line == "실업급여(상용직) · 2026-08-25"
    assert cite_line(["NO-SUCH-RULE"]) is None


def test_cite_line_appends_guide_sources_without_duplicates() -> None:
    guide = "고용24 「조기재취업수당」 · 2025-07-10"

    assert cite_line(["NO-SUCH-RULE"], [guide, guide]) == guide
    assert cite_line(["DUE-093"], [guide]) == f"취업드림수첩(2025년판 PDF) / {guide}"


@pytest.mark.parametrize(
    ("rule_id", "group", "round_no", "expected"),
    [
        ("ACT-104", "repeat", 3, True),  # 반복수급자 2~3차
        ("ACT-104", "general", 3, False),  # 다른 수급자 유형
        ("ACT-023", "general", 2, True),  # 일반수급자 2차
        ("ACT-023", "general", 5, False),  # 다른 회차
        ("ACT-100", "general", 9, True),  # 8차~만료
        ("ACT-101", "general", 4, True),  # 1·4·8차
        ("ACT-107", "age_60_64", 3, True),  # 만60세 이상·장애인
        ("ACT-110", "repeat", 3, True),  # 전체 유형
    ],
)
def test_card_applies_only_to_matching_group_and_round(
    rule_id: str, group: str, round_no: int, expected: bool
) -> None:
    assert applies_to(cards_by_id()[rule_id], Profile(group, round_no)) is expected


@pytest.mark.parametrize(
    ("rule_id", "over_50", "expected"),
    [
        ("ELIG-183", False, True),  # 근로자 / 50세 미만
        ("ELIG-183", True, False),
        ("ELIG-184", True, True),  # 근로자 / 50세 이상 또는 장애인
        ("ELIG-184", False, False),
        ("ELIG-184", None, True),  # 나이를 모르면 거르지 않음
        ("ACT-110", True, True),  # 나이 구분 없는 카드
    ],
)
def test_card_applies_only_to_matching_age_band(
    rule_id: str, over_50: bool | None, expected: bool
) -> None:
    assert applies_to(cards_by_id()[rule_id], Profile(over_50=over_50)) is expected


def test_round_in_question_keeps_age_band() -> None:
    assert Profile("general", 3, over_50=True).for_query("4차 때 뭐 해요?").over_50 is True


def test_round_in_question_overrides_current_round() -> None:
    assert Profile("general", 3).for_query("4차 때 고용센터 가면 뭘 가져가요?").round_no == 4
    assert Profile("general", 3).for_query("이번에 뭐 해요?").round_no == 3


def test_search_with_profile_returns_only_cards_for_that_user() -> None:
    query = "이번 회차에 몇 번 해야 돼요?"

    repeat = {c.rule_id for c in search_cards(query, 5, Profile("repeat", 3))}
    general = {c.rule_id for c in search_cards(query, 5, Profile("general", 2))}

    assert "ACT-104" in repeat and "ACT-023" not in repeat
    assert "ACT-104" not in general


@pytest.mark.parametrize(
    ("group", "round_no", "expected"),
    [
        ("repeat", 3, {"ACT-102", "ACT-104", "ACT-112"}),
        ("general", 4, {"ACT-025", "ACT-026", "ACT-099", "ACT-101"}),
        ("age65_or_disabled", 4, {"ACT-037", "ACT-107", "ACT-108"}),
    ],
)
def test_cards_for_picks_rules_fixed_by_group_and_round(
    group: str, round_no: int, expected: set[str]
) -> None:
    assert {c.rule_id for c in cards_for(Profile(group, round_no))} == expected
    assert cards_for(Profile(group, None)) == []
