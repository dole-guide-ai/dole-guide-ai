from datetime import date

from app.schemas.procedure import ProcedureRead
from app.schemas.rounds import RoundSummary
from app.services.entry import branch_id, build_entry


def procedure(**overrides: object) -> ProcedureRead:
    base = {
        "stage": "job_registration",
        "recipient_group": "general",
        "age_at_separation": 58,
        "has_disability": False,
        "separation_date": date(2026, 9, 30),
        "education_done": False,
        "benefit_days": 270,
        "period_end_date": date(2027, 9, 30),
    }
    return ProcedureRead.model_validate({**base, **overrides})


def test_resume_branches() -> None:
    assert branch_id(procedure(), None, None, None) == "E7a"
    assert branch_id(procedure(), "outdated", None, None) == "E7b"
    assert branch_id(procedure(), "draft", None, None) == "E7c"
    assert branch_id(procedure(), "ready", None, None) == "E6"


def test_repeat_recipient_goes_to_center_guide() -> None:
    assert branch_id(procedure(recipient_group="repeat"), None, None, None) == "E1"


def test_recognition_without_current_round_is_end() -> None:
    assert branch_id(procedure(stage="recognition"), "ready", None, None) == "END"


def test_recognition_without_round_does_not_say_ended() -> None:
    """종료 처리 전(실업인정 단계)에는 끝났다고 확정하지 않고 예정일과 확인 안내만 줍니다."""
    waiting = procedure(stage="recognition", expected_end_date=date(2027, 6, 26))
    entry = build_entry(waiting, "ready", None, None)
    assert entry.branch_id == "END"
    assert entry.title != "실업급여 수급이 끝났어요"
    assert entry.next_step_text == "수급 종료 예정 : 06.26"
    assert [m.template_id for m in entry.messages] == ["T-NO-ROUND"]


def round_summary(no: int) -> RoundSummary:
    return RoundSummary.model_validate(
        {
            "round": no,
            "period_start": date(2026, 10, 1),
            "period_end": date(2026, 10, 28),
            "recognition_date": date(2026, 10, 28),
            "attendance_required": False,
            "status": "current",
            "application_status": "draft",
        }
    )


def test_last_round_gets_last_round_sentence() -> None:
    """마지막 회차면 첫 안내에 마지막 회차 문장을 붙입니다 (F-33)."""
    last = procedure(stage="recognition", last_round=9)
    entry = build_entry(last, "ready", round_summary(9), 7)
    assert [m.template_id for m in entry.messages] == ["T-LAST"]
    assert "마지막 회차" in entry.messages[0].text
    assert build_entry(last, "ready", round_summary(8), 7).messages == []


def test_ended_account_shows_end_screen() -> None:
    ended = procedure(stage="ended", end_reason="exhausted", expected_end_date=date(2027, 6, 26))
    entry = build_entry(ended, "ready", None, None)
    assert entry.branch_id == "END"
    assert entry.title == "실업급여 수급이 끝났어요"
    assert entry.next_step_text == "수급 종료 : 06.26"
    assert entry.messages[0].template_id == "T-END"
    assert "소정급여일수" in entry.messages[0].text


def test_big_text_is_default_from_65_at_separation() -> None:
    """이직 당시 만 65세 이상이면 글자 크게로 시작합니다 (1장 1.6 M4, F-06)."""
    assert build_entry(procedure(age_at_separation=64), "none", None, None).ui.big_text is False
    assert build_entry(procedure(age_at_separation=65), "none", None, None).ui.big_text is True
    assert build_entry(procedure(age_at_separation=67), "ready", None, None).ui.big_text is True
