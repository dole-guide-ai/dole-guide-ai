"""대화 기록 조회와 메시지 보내기를 맡는 라우터입니다.

메시지를 보내는 요청 하나가 곧 대화 턴 하나이고, 응답은 SSE 스트림으로 흘려보냅니다.
턴 안의 처리는 LangGraph가 맡을 예정이며, 메시지 보내기는 아직 501 틀입니다.
대화 기록 조회(새로고침 복원, F-03)는 동작합니다.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentAccount, IdempotencyKey, get_current_account
from app.api.responses import error_responses
from app.core.db import DbSession
from app.core.errors import NotImplementedYetError
from app.schemas.messages import MessageCreate, MessageList
from app.services import messages as message_service

router = APIRouter(
    prefix="/accounts/{persona_id}", tags=["messages"], dependencies=[Depends(get_current_account)]
)


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
        **error_responses(401, 404, 409, 503, 501),
    },
)
def send_message(body: MessageCreate, idempotency_key: IdempotencyKey = None) -> None:
    """사용자 메시지 하나를 보내면 대화 턴이 하나 시작되고, 응답은 SSE 스트림(text/event-stream)으로
    흘려보냅니다.

    이벤트 순서: tool_call → form_update(여러 번) → token(여러 번) → done → ask_user. 이름은
    shared/sse-events.json을 따릅니다.
    같은 계정의 턴이 이미 진행 중이면 409 TURN_IN_PROGRESS, 턴 도중 실패는 error 이벤트로 보냅니다.
    턴은 3분을 넘기지 않습니다.
    (아직 구현 전이라 501)
    """
    raise NotImplementedYetError()
