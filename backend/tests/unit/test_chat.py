from app.agent.events import TurnEvent
from app.schemas.messages import (
    AskUserEvent,
    DoneEvent,
    ErrorEvent,
    MessageKind,
    MessageRole,
    TokenEvent,
    ToolCallEvent,
)
from app.services.chat import assistant_bubbles
from app.services.messages import TurnMessage


def test_tokens_join_into_one_answer_with_cite() -> None:
    bubbles = assistant_bubbles(
        [
            TurnEvent(ToolCallEvent(name="check_round", status="started")),
            TurnEvent(TokenEvent(text="1건 ")),
            TurnEvent(TokenEvent(text="남았어요. ")),
            TurnEvent(DoneEvent(cite="안내문")),
        ]
    )

    assert bubbles == [
        TurnMessage(
            MessageRole.ASSISTANT,
            MessageKind.TEXT,
            "1건 남았어요.",
            {"cite": "안내문", "rule_refs": []},
        )
    ]


def test_question_and_error_follow_the_answer() -> None:
    bubbles = assistant_bubbles(
        [
            TurnEvent(TokenEvent(text="여쭤볼게요.")),
            TurnEvent(AskUserEvent(question_id="q1", text="언제요?")),
            TurnEvent(ErrorEvent(code="TIMEOUT", message="멈췄어요")),
        ]
    )

    assert [(b.kind, b.text) for b in bubbles] == [
        (MessageKind.TEXT, "여쭤볼게요."),
        (MessageKind.ASK_USER, "언제요?"),
        (MessageKind.ERROR, "멈췄어요"),
    ]


def test_no_events_means_no_bubbles() -> None:
    assert assistant_bubbles([]) == []
