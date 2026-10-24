import json
from pathlib import Path

from app.agent import events
from app.agent.events import TurnEvent
from app.schemas.messages import AskUserEvent

SHARED = Path(__file__).resolve().parents[3] / "shared" / "sse-events.json"


def test_event_names_match_shared_file() -> None:
    shared = json.loads(SHARED.read_text(encoding="utf-8"))

    assert {key: getattr(events, key) for key in shared} == shared


def test_turn_event_to_sse_drops_empty_fields() -> None:
    sse = TurnEvent(AskUserEvent(question_id="q1", text="언제 퇴사하셨어요?")).to_sse()

    assert sse["event"] == "ask_user"
    assert json.loads(sse["data"]) == {
        "question_id": "q1",
        "text": "언제 퇴사하셨어요?",
        "choices": [],
        "accepts_file": False,
    }


def test_form_update_keeps_null_value_for_replace() -> None:
    import json

    from app.agent.events import TurnEvent
    from app.schemas.common import FormUpdate

    sse = TurnEvent(FormUpdate(form="resume", path="/hope_wage", op="replace")).to_sse()

    assert json.loads(sse["data"])["value"] is None
