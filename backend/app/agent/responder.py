"""대화 턴 서비스와 에이전트가 만나는 자리입니다.

서비스는 `gateway`처럼 이 모듈을 통해 `get_responder()`를 불러, 받은 응답기에 사용자 말을 넘기고
`TurnEvent`를 차례로 받습니다. 기본 응답기는 LangGraph 그래프(`graph.build_graph`)를 Postgres
체크포인터와 함께 실행하고, 노드가 `events.emit`으로 낸 이벤트를 그대로 내보냅니다.
테스트는 이 함수를 바꿔 끼웁니다.

응답기에는 개인정보 컬럼(user_profiles)을 넘기지 않습니다.
"""

import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import date, datetime

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from sqlalchemy.orm import Session

from app.agent import checkpointer as checkpointer_module
from app.agent import gateway
from app.agent.events import TurnEvent
from app.agent.graph import TOOL_CONTEXT_KEY, TURN_KEY, build_graph
from app.agent.tools.registry import ToolContext
from app.core.clock import KST
from app.schemas.messages import DoneEvent, InputKind, TokenEvent
from app.services.accounts import AccountContext


@dataclass(frozen=True)
class TurnInput:
    user_id: uuid.UUID
    persona_id: str
    text: str
    input_kind: InputKind
    today: date
    file_ids: list[str] = field(default_factory=list)
    import_ids: list[str] = field(default_factory=list)
    # 도구가 쓰는 DB 세션과 계정 기준일. 대화 턴 서비스가 넣습니다(단위 테스트는 비워 둠).
    db: Session | None = None
    anchor_date: date | None = None


Responder = Callable[[TurnInput], Iterator[TurnEvent]]

_ECHO_REPLY = "말씀하신 내용을 받았어요. AI 답변은 곧 연결돼요."


def echo_responder(turn: TurnInput) -> Iterator[TurnEvent]:
    """에이전트를 붙이기 전 임시 응답기. 사용자 말은 되풀이하지 않습니다(로그·화면 노출 최소화)."""
    for word in _ECHO_REPLY.split(" "):
        yield TurnEvent(TokenEvent(text=word + " "))
    yield TurnEvent(DoneEvent())


def tool_context(turn: TurnInput) -> ToolContext | None:
    if turn.db is None or turn.anchor_date is None:
        return None
    account = AccountContext(turn.user_id, turn.persona_id, turn.anchor_date)
    now = datetime.combine(turn.today, datetime.now(KST).time(), KST)
    return ToolContext(db=turn.db, account=account, today=turn.today, now=now)


def run_config(turn: TurnInput) -> RunnableConfig:
    """계정 하나에 대화 하나(thread_id=user_id).

    턴 정보·도구 문맥은 체크포인트에 남지 않는 config로 넘깁니다.
    """
    return {
        "configurable": {
            "thread_id": str(turn.user_id),
            TURN_KEY: turn,
            TOOL_CONTEXT_KEY: tool_context(turn),
        },
        **gateway.trace_config(),
    }


def graph_responder(
    turn: TurnInput, checkpointer: BaseCheckpointSaver | None = None
) -> Iterator[TurnEvent]:
    graph = build_graph(checkpointer or checkpointer_module.get_checkpointer())
    for event in graph.stream(
        {"messages": [HumanMessage(turn.text)]}, run_config(turn), stream_mode="custom"
    ):
        if isinstance(event, TurnEvent):
            yield event


def get_responder() -> Responder:
    return graph_responder
