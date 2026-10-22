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
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.agent import gateway, responder
from app.agent.events import ASK_USER, DONE, ERROR, TOKEN, TurnEvent
from app.core.config import get_settings
from app.core.errors import DEFAULT_MESSAGES, ConflictError
from app.repositories import idempotency as idempotency_repo
from app.repositories import messages as repo
from app.schemas.common import ErrorCode
from app.schemas.messages import ErrorEvent, MessageCreate, MessageList, MessageRead
from app.services.accounts import AccountContext
from app.services.idempotency import request_hash

logger = logging.getLogger(__name__)

PAGE_SIZE = 50


@dataclass
class Turn:
    db: Session
    account: AccountContext
    turn_input: responder.TurnInput
    started: float = field(default_factory=time.monotonic)
    _texts: list[str] = field(default_factory=list)
    _ask: dict[str, Any] | None = None
    _done: dict[str, Any] | None = None
    _error: dict[str, Any] | None = None

    def events(self) -> Iterator[TurnEvent]:
        timeout = get_settings().turn_timeout_seconds
        source = responder.get_responder()(self.turn_input)
        try:
            for event in self._guarded(source):
                self._collect(event)
                yield event
                if event.name == ERROR:
                    return
                if time.monotonic() - self.started > timeout:
                    timed_out = TurnEvent(
                        ErrorEvent(
                            code=ErrorCode.TIMEOUT, message=DEFAULT_MESSAGES[ErrorCode.TIMEOUT]
                        )
                    )
                    self._collect(timed_out)
                    yield timed_out
                    return
        finally:
            # 끝까지 갔든, 실패했든, 연결이 끊겨 닫혔든 응답기를 멈추고 말풍선을 남깁니다.
            source.close()
            self._save()

    def _guarded(self, source: Iterator[TurnEvent]) -> Iterator[TurnEvent]:
        try:
            yield from source
        except Exception as exc:  # noqa: BLE001 - 턴 도중 실패는 error 이벤트로 알립니다
            error = gateway.to_app_error(exc)
            logger.warning("turn failed code=%s type=%s", error.code, type(exc).__name__)
            yield TurnEvent(ErrorEvent(code=error.code, message=error.message))

    def _collect(self, event: TurnEvent) -> None:
        payload = event.data.model_dump(mode="json", exclude_none=True)
        if event.name == TOKEN:
            self._texts.append(payload["text"])
        elif event.name == ASK_USER:
            self._ask = payload
        elif event.name == DONE:
            self._done = payload
        elif event.name == ERROR:
            self._error = payload

    def _save(self) -> None:
        user_id = self.account.user_id
        text = "".join(self._texts).strip() or None
        if text or self._done:
            repo.add(self.db, user_id, "assistant", "text", text, self._done)
        if self._ask:
            repo.add(self.db, user_id, "assistant", "ask_user", self._ask["text"], self._ask)
        if self._error:
            repo.add(self.db, user_id, "assistant", "error", self._error["message"], self._error)
        self.db.commit()


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
        # 스트림은 처음 결과를 다시 보내 줄 수 없어, 같은 키는 다시 실행하지 않고 거절합니다.
        # 화면은 GET /messages로 결과를 다시 읽습니다.
        if idempotency_repo.get(db, account.user_id, idempotency_key) is not None:
            db.rollback()
            raise ConflictError("이미 보낸 메시지예요.")
        idempotency_repo.add(db, account.user_id, idempotency_key, request_hash(body), 200, None)
    repo.add(db, account.user_id, "user", body.input_kind.value, body.text)
    turn_input = responder.TurnInput(
        user_id=account.user_id,
        persona_id=account.persona_id,
        text=body.text,
        input_kind=body.input_kind.value,
        today=today,
        file_ids=body.file_ids,
        import_ids=body.import_ids,
    )
    return Turn(db, account, turn_input)


def list_messages(db: Session, account: AccountContext, cursor: int | None) -> MessageList:
    rows, total = repo.list_after(db, account.user_id, cursor or 0, PAGE_SIZE)
    items = [MessageRead.model_validate(row, from_attributes=True) for row in rows]
    newest = repo.last(db, account.user_id)
    has_more = bool(items) and newest is not None and items[-1].seq < newest.seq
    return MessageList(items=items, total=total, next_cursor=items[-1].seq if has_more else None)
