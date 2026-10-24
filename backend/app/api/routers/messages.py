"""대화 기록 조회와 메시지 보내기를 맡는 라우터입니다.

메시지를 보내는 요청 하나가 곧 대화 턴 하나이고, 응답은 SSE 스트림으로 흘려보냅니다.
막을 것(턴 진행 중·같은 요청 재전송)은 스트림을 열기 전에 HTTP 오류로 끝내고, 턴 도중 실패는
`error` 이벤트로 보냅니다. 실제 처리는 services/chat.py가 합니다.
"""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Query, Request
from sse_starlette import EventSourceResponse
from starlette.concurrency import run_in_threadpool

from app.api.deps import CurrentAccount, IdempotencyKey
from app.api.responses import error_responses
from app.core.clock import Today
from app.core.db import DbSession
from app.schemas.messages import MessageCreate, MessageList
from app.services import chat as chat_service
from app.services import messages as message_service

router = APIRouter(prefix="/accounts/{persona_id}", tags=["messages"])

_END = object()


@router.get("/messages", summary="대화 기록", responses=error_responses(401, 404))
def list_messages(
    db: DbSession,
    account: CurrentAccount,
    cursor: Annotated[int | None, Query(ge=0)] = None,
) -> MessageList:
    """화면에 보일 대화 말풍선을 순서대로 돌려줍니다. 새로고침했을 때 대화를 그대로 복원하는 데
    씁니다.

    한 번에 100개까지 돌려주고, 더 있으면 next_cursor를 줍니다. cursor를 주면 그 다음부터 이어서
    돌려줍니다. 답을 기다리던 질문은 계정 조회(`GET /accounts/{id}`)의 pending_ask로 옵니다.
    """
    return message_service.list_messages(db, account.user_id, cursor)


@router.post(
    "/messages",
    summary="메시지 보내기 (대화 턴, SSE)",
    responses={
        200: {
            "description": "SSE 스트림 (shared/sse-events.json)",
            "content": {"text/event-stream": {}},
        },
        **error_responses(401, 404, 409),
    },
    response_class=EventSourceResponse,
)
async def send_message(
    request: Request,
    db: DbSession,
    account: CurrentAccount,
    today: Today,
    body: MessageCreate,
    idempotency_key: IdempotencyKey = None,
) -> EventSourceResponse:
    """사용자 메시지 하나를 보내면 대화 턴이 하나 시작되고, 응답은 SSE 스트림(text/event-stream)으로
    흘려보냅니다.

    이벤트 순서: tool_call → form_update(여러 번) → token(여러 번) → done → ask_user. 이름은
    shared/sse-events.json을 따릅니다.
    같은 계정의 턴이 이미 진행 중이면 409 TURN_IN_PROGRESS입니다. 같은 Idempotency-Key로 다시 보내면
    턴을 다시 돌리지 않고 409입니다(결과는 GET /messages로 다시 읽음).
    턴 도중 실패는 error 이벤트로 보내고, 3분을 넘으면 error{TIMEOUT}으로 끝납니다.
    연결이 끊기면(멈추기·탭 닫기) 턴을 멈추고 그때까지의 말풍선을 저장합니다.
    """
    turn = await run_in_threadpool(
        chat_service.start_turn, db, account, body, idempotency_key, today
    )
    return EventSourceResponse(_stream(request, turn), headers={"X-Accel-Buffering": "no"})


async def _stream(request: Request, turn: chat_service.Turn) -> AsyncIterator[dict[str, str]]:
    # 서비스는 동기(DB 세션)라 이벤트 하나씩 스레드에서 꺼내고, 사이마다 연결 끊김을 확인합니다.
    events = turn.events()
    try:
        while not await request.is_disconnected():
            event = await run_in_threadpool(next, events, _END)
            if event is _END:
                break
            yield event.to_sse()
    finally:
        # 끊겼거나 끝났으면 제너레이터를 닫아 응답기를 멈추고, 첫 이벤트 전에 끊겼어도 저장합니다.
        await run_in_threadpool(events.close)
        await run_in_threadpool(turn.finish)
