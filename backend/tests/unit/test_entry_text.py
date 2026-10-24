"""첫 안내 템플릿 (상세기획 1장 1.7·1.9·1.11 예시). 같은 상태면 늘 같은 문구입니다."""

from dataclasses import replace
from datetime import date

from app.rules.entry_text import EntryFacts, RoundFacts, compose, next_step_text

LEE = EntryFacts(
    name="이정호",
    stage="recognition",
    rule_group="general",
    age_at_separation=58,
    round_no=4,
    recognition_date=date(2026, 12, 22),
    d_day=6,
    attendance=True,
    round_facts=RoundFacts(
        required=2, required_job_search=1, recorded=2, counted=1, counted_job_search=1, same_day=1
    ),
)


def test_lee_e4b_matches_design_example() -> None:
    """1.11 진입 결과 예시: T-E4b + T-S + M3, 근거 줄은 마지막 말풍선에."""
    c = compose("E4b", LEE)

    assert [m[0] for m in c.messages] == ["T-E4b", "T-S+M3"]
    assert c.messages[0][1] == (
        "이정호님, 3차 실업인정까지 받으셨네요. 이제 4차 실업인정 준비를 시작해 볼까요? "
        "12월 22일(화)까지 6일 남았어요."
    )
    assert "같은 날 활동이 있어 1건만 인정돼요" in c.messages[1][1]
    assert "다른 날 활동이 1건 더 필요해요" in c.messages[1][1]
    assert c.messages[1][1].endswith("4차는 고용센터에 직접 가는 출석 회차예요.")
    assert c.messages[0][2] is None and c.messages[1][2]
    assert c.choices == ["부족한 활동 추천해 주세요", "새 활동 기록할게요", "신청서 미리 볼래요"]
    assert next_step_text(LEE) == "다음 기한 : 4차 실업인정일 12.22(화) · 고용센터 출석"


def test_choi_e7b_gets_m1_for_65_or_more() -> None:
    choi = EntryFacts(
        name="최영수",
        stage="job_registration",
        rule_group="age65_or_disabled",
        age_at_separation=67,
        old_resume_year=2019,
    )

    c = compose("E7b", choi)

    assert [m[0] for m in c.messages] == ["T-E7b", "T-M1"]
    assert "2019년에 쓰신 이력서" in c.messages[0][1]
    assert "67세" in c.messages[1][1]
    assert next_step_text(choi).startswith("다음 할 일 : 이력서 최신화")


def test_e7a_asks_for_file_and_e4a_adds_group_sentence() -> None:
    park = EntryFacts(
        name="박진수", stage="job_registration", rule_group="age_60_64", age_at_separation=61
    )
    first = EntryFacts(
        name="박진수",
        stage="recognition",
        rule_group="age_60_64",
        age_at_separation=61,
        round_no=1,
        recognition_date=date(2026, 11, 2),
        d_day=5,
    )

    assert compose("E7a", park).accepts_file is True
    assert "온라인이나 고용센터" in compose("E4a", first).messages[0][1]


def test_recognition_day_without_attendance_opens_online_text() -> None:
    today = EntryFacts(
        name="이정호", stage="recognition", rule_group="general", age_at_separation=58, round_no=5
    )

    assert "17시까지" in compose("E3", today).messages[0][1]


def test_summary_reason_and_job_search_shortfall() -> None:
    """같은 날이 아닌 사유로 빠졌으면 같은 날이라 말하지 않고, 구직활동 부족분도 같이 말합니다."""
    rf = RoundFacts(required=2, required_job_search=1, recorded=2, counted=1, counted_job_search=0)
    text = compose("E4b", replace(LEE, round_facts=rf)).messages[1][1]

    assert "같은 날" not in text and "그중 1건만 인정돼요" in text
    assert "1건 더 필요하고, 그중 구직활동이 1건 있어야 해요" in text


def test_e7b_without_saved_year() -> None:
    choi = EntryFacts(
        name="최영수",
        stage="job_registration",
        rule_group="age65_or_disabled",
        age_at_separation=67,
    )

    assert "예전에 쓰신 이력서" in compose("E7b", choi).messages[0][1]
