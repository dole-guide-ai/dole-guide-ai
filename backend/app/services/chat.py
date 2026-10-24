"""대화 턴 서비스입니다 (F-07·F-08·N-06·N-07의 백엔드 부분).

메시지 하나를 보내면 턴 하나가 시작됩니다.
1. `start_turn`: 스트림을 열기 전에 막을 것을 모두 확인합니다. 같은 계정의 턴이 이미 돌고 있으면
   409 TURN_IN_PROGRESS, 같은 Idempotency-Key가 다시 오면 409. 통과하면 사용자 말풍선을 남깁니다.
2. `Turn.events()`: 응답기(agent/responder.py)의 이벤트를 그대로 흘려보내며 AI 말풍선을 모읍니다.
   - 응답기 예외는 `error` 이벤트로 바꿉니다. 이미 반영된 패널 값은 건드리지 않습니다.
   - 턴이 TURN_TIMEOUT_SECONDS를 넘으면 `error{TIMEOUT}`을 보내고 끝냅니다.
   - 연결이 끊겨 호출자가 제너레이터를 닫으면 응답기도 멈춥니다.
   - 어떻게 끝나든 말풍선을 저장하고 commit합니다. commit과 함께 턴 잠금이 풀립니다.

계정 잠금은 요청 세션의 트랜잭션이 턴 내내 쥐고 있습니다(노션 「API · ERD 설계」 3.11).
"""

import logging
import time
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import date
from http import HTTPStatus
from typing import Any

from sqlalchemy.orm import Session

from app.agent import gateway, responder
from app.agent.events import ASK_USER, DONE, ERROR, TOKEN, TurnEvent
from app.core.config import get_settings
from app.core.errors import DEFAULT_MESSAGES, ConflictError
from app.repositories import idempotency as idempotency_repo
from app.repositories import messages as repo
from app.schemas.common import ErrorCode
from app.schemas.messages import (
    ErrorEvent,
    MessageCreate,
    MessageKind,
    MessageRole,
)
from app.services import messages as message_service
from app.services.accounts import AccountContext
from app.services.idempotency import request_hash
from app.services.messages import TurnMessage

logger = logging.getLogger(__name__)


def assistant_bubbles(events: Iterable[TurnEvent]) -> list[TurnMessage]:
    """턴에서 나간 이벤트를 화면용 AI 말풍선으로 바꿉니다(순수 함수).

    글자(token)는 이어 붙여 말풍선 하나로, 근거(done)는 그 말풍선에 싣고, 질문(ask_user)과
    오류(error)는 각각 말풍선 하나로 남깁니다. 저장 순서도 화면에 보인 순서와 같습니다.
    """
    texts: list[str] = []
    done: dict[str, Any] | None = None
    tail: list[TurnMessage] = []
    for event in events:
        payload = event.data.model_dump(mode="json", exclude_none=True)
        if event.name == TOKEN:
            texts.append(payload["text"])
        elif event.name == DONE:
            done = payload
        elif event.name == ASK_USER:
            tail.append(_assistant(MessageKind.ASK_USER, payload["text"], payload))
        elif event.name == ERROR:
            tail.append(_assistant(MessageKind.ERROR, payload["message"], payload))
    text = "".join(texts).strip() or None
    answer = [_assistant(MessageKind.TEXT, text, done)] if text or done else []
    return answer + tail


def _assistant(kind: MessageKind, text: str | None, payload: dict[str, Any] | None) -> TurnMessage:
    return TurnMessage(MessageRole.ASSISTANT, kind, text, payload)


def _error_event(code: ErrorCode, message: str | None = None) -> TurnEvent:
    return TurnEvent(ErrorEvent(code=code, message=message or DEFAULT_MESSAGES[code]))


@dataclass
class Turn:
    db: Session
    account: AccountContext
    turn_input: responder.TurnInput
    _sent: list[TurnEvent] = field(default_factory=list)
    _finished: bool = False

    def events(self) -> Iterator[TurnEvent]:
        started = time.monotonic()
        timeout = get_settings().turn_timeout_seconds
        source = responder.get_responder()(self.turn_input)
        try:
            for event in self._guarded(source):
                # 보내기 전에 시간을 봅니다. 늦게 나온 done이 TIMEOUT보다 먼저 가지 않게.
                if event.name != ERROR and time.monotonic() - started > timeout:
                    event = _error_event(ErrorCode.TIMEOUT)
                self._sent.append(event)
                yield event
                if event.name == ERROR:
                    return
        finally:
            # 끝까지 갔든, 실패했든, 연결이 끊겨 닫혔든 응답기를 멈추고 말풍선을 남깁니다.
            source.close()
            self.finish()

    def finish(self) -> None:
        """보낸 말풍선을 저장하고 커밋해 턴 잠금을 풉니다. 여러 번 불러도 한 번만 합니다.

        스트림이 첫 이벤트 전에 끊기면 events()가 시작되지 않아 finally가 돌지 않으므로,
        라우터가 스트림을 닫은 뒤 한 번 더 부릅니다.
        """
        if self._finished:
            return
        self._finished = True
        message_service.save_turn(self.db, self.account.user_id, assistant_bubbles(self._sent))
        self.db.commit()

    @staticmethod
    def _guarded(source: Iterator[TurnEvent]) -> Iterator[TurnEvent]:
        try:
            yield from source
        except Exception as exc:  # noqa: BLE001 - 턴 도중 실패는 error 이벤트로 알립니다
            error = gateway.to_app_error(exc)
            logger.warning("turn failed code=%s type=%s", error.code, type(exc).__name__)
            yield _error_event(error.code, error.message)


def start_turn(
    db: Session,
    account: AccountContext,
    body: MessageCreate,
    idempotency_key: str | None,
    today: date,
) -> Turn:
    """스트림 전에 막을 것을 확인하고 사용자 말풍선을 남깁니다. 실패는 HTTP 오류로 끝납니다."""
    if not repo.try_lock_turn(db, account.user_id):
        db.rollback()
        raise ConflictError(code=ErrorCode.TURN_IN_PROGRESS)
    if idempotency_key is not None:
        # 스트림은 처음 결과를 다시 보내 줄 수 없어, 같은 키는 다시 실행하지 않고 거절합니다(409).
        # 화면은 GET /messages로 결과를 다시 읽습니다.
        if idempotency_repo.get(db, account.user_id, idempotency_key) is not None:
            db.rollback()
            raise ConflictError()
        idempotency_repo.add(
            db, account.user_id, idempotency_key, request_hash(body), HTTPStatus.OK, None
        )
    message_service.save_turn(
        db,
        account.user_id,
        [TurnMessage(MessageRole.USER, MessageKind(body.input_kind), body.text)],
    )
    turn_input = responder.TurnInput(
        user_id=account.user_id,
        persona_id=account.persona_id,
        text=body.text,
        input_kind=body.input_kind,
        today=today,
        file_ids=body.file_ids,
        import_ids=body.import_ids,
        db=db,
        anchor_date=account.anchor_date,
    )
    return Turn(db, account, turn_input)
