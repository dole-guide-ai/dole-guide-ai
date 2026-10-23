import json
from pathlib import Path

from app.agent import events
from app.agent.events import TurnEvent
from app.agent.responder import TurnInput, echo_responder
from app.schemas.messages import AskUserEvent, DoneEvent, TokenEvent

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


def test_echo_responder_ends_with_done_and_does_not_repeat_input() -> None:
    import uuid
    from datetime import date

    turn = TurnInput(uuid.uuid4(), "lee", "합성 입력 문장", "text", date(2026, 10, 21))

    out = list(echo_responder(turn))

    assert all(isinstance(e.data, TokenEvent) for e in out[:-1])
    assert isinstance(out[-1].data, DoneEvent)
    assert "합성 입력 문장" not in "".join(e.data.text for e in out[:-1])


def test_form_update_keeps_null_value_for_replace() -> None:
    import json

    from app.agent.events import TurnEvent
    from app.schemas.common import FormUpdate

    sse = TurnEvent(FormUpdate(form="resume", path="/hope_wage", op="replace")).to_sse()

    assert json.loads(sse["data"])["value"] is None
