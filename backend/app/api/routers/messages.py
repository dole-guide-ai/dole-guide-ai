"""대화 기록 조회와 메시지 보내기를 맡는 라우터입니다.

메시지를 보내는 요청 하나가 곧 대화 턴 하나이고, 응답은 SSE 스트림으로 흘려보냅니다.
턴 안의 처리는 LangGraph가 맡을 예정이며, 지금은 501 틀입니다.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import IdempotencyKey, get_current_account
from app.api.responses import error_responses
from app.core.errors import NotImplementedYetError
from app.schemas.messages import MessageCreate, MessageList

router = APIRouter(
    prefix="/accounts/{persona_id}", tags=["messages"], dependencies=[Depends(get_current_account)]
)


@router.get("/messages", summary="대화 기록", responses=error_responses(401, 404, 501))
def list_messages(cursor: Annotated[int | None, Query(ge=0)] = None) -> MessageList:
    """화면에 보일 대화 말풍선을 순서대로 돌려줍니다. 새로고침했을 때 대화를 그대로 복원하는 데
    씁니다.

    cursor를 주면 그 다음부터 이어서 돌려줍니다. (아직 구현 전이라 501)
    """
    raise NotImplementedYetError()


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
