from datetime import date

from app.schemas.procedure import ProcedureRead
from app.services.entry import branch_id


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
