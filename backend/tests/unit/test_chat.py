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


def test_finish_rolls_back_when_saving_fails_so_the_turn_lock_is_released() -> None:
    """말풍선 저장이 실패해도 트랜잭션을 끝내야 계정 잠금이 풀립니다."""
    import uuid
    from datetime import date
    from unittest.mock import MagicMock

    import pytest

    from app.services import chat as chat_service
    from app.services.accounts import AccountContext

    db = MagicMock()
    db.commit.side_effect = RuntimeError("db down")
    account = AccountContext(uuid.uuid4(), "park", date(2026, 10, 1))
    turn = chat_service.Turn(db, account, MagicMock())

    with pytest.raises(RuntimeError):
        turn.finish()

    db.rollback.assert_called_once()
