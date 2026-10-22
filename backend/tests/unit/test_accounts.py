from datetime import date

from app.rules.periods import build_rounds
from app.services.accounts import _prev_answers


def test_prev_answers_use_last_submitted_round_date() -> None:
    planned = build_rounds("general", date(2026, 6, 1), date(2026, 6, 15), date(2026, 12, 31))

    data = _prev_answers({"notification_method": "sms"}, planned, submitted_through=3)

    assert data.model_dump(mode="json")["notification_method"]["answered_on"] == str(
        planned[2].recognition_date
    )
