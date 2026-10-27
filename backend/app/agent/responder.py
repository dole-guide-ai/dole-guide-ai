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
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from sqlalchemy.orm import Session

from app.agent import checkpointer as checkpointer_module
from app.agent import gateway
from app.agent.events import TurnEvent
from app.agent.graph import TOOL_CONTEXT_KEY, TURN_KEY, build_graph
from app.agent.nodes.finish import done_event
from app.agent.nodes.preprocess import BLOCKED_REPLY, gate
from app.agent.tools.registry import ToolContext
from app.schemas.messages import DoneEvent, InputKind, TokenEvent
from app.services import files as files_service
from app.services.accounts import AccountContext


@dataclass(frozen=True)
class TurnInput:
    user_id: uuid.UUID
    persona_id: str
    text: str
    input_kind: InputKind
    # 턴의 지금 시각(KST). 날짜·마감·다음 할 일이 모두 이 값 하나에서 나옵니다.
    now: datetime
    file_ids: list[str] = field(default_factory=list)
    import_ids: list[str] = field(default_factory=list)
    # 도구가 쓰는 DB 세션과 계정 기준일. 대화 턴 서비스가 넣습니다(단위 테스트는 비워 둠).
    db: Session | None = None
    anchor_date: date | None = None

    @property
    def today(self) -> date:
        return self.now.date()


Responder = Callable[[TurnInput], Iterator[TurnEvent]]


def tool_context(turn: TurnInput) -> ToolContext | None:
    if turn.db is None or turn.anchor_date is None:
        return None
    account = AccountContext(turn.user_id, turn.persona_id, turn.anchor_date)
    evidence = files_service.evidence_ids(turn.db, account, turn.file_ids) if turn.file_ids else []
    return ToolContext(
        db=turn.db, account=account, today=turn.today, now=turn.now, evidence_file_ids=evidence
    )


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


def turn_input(graph: CompiledStateGraph, turn: TurnInput, config: RunnableConfig) -> Any:
    """새 말이면 처음부터, 그래프가 질문(interrupt)에서 멈춰 있으면 그 답으로 재개합니다.

    재개하는 답도 preprocess와 같은 개인정보 검사를 거쳐 가린 글만 넘깁니다.
    0등급 번호가 있으면 재개하지 않고(None) 질문을 그대로 기다립니다.
    """
    if not graph.get_state(config).interrupts:
        return {"panel": None}
    answer, blocked = gate(turn.text)
    if blocked:
        return None
    # 재개한 턴도 호출 상한은 새로 셉니다.
    return Command(resume=answer, update={"loop_calls": 0, "tool_calls": 0})


def restore_evidence(graph: CompiledStateGraph, config: RunnableConfig) -> None:
    """질문에 답하는 재개 요청에는 첨부가 없으므로, 멈추기 전에 올린 증빙을 도구 문맥에 되살립니다.

    파일이 그사이 지워졌거나 다른 계정 것이면 빠집니다(evidence_ids가 다시 확인). 답과 함께 새
    증빙을 올렸으면 앞서 올린 것 뒤에 이어 붙입니다.
    """
    ctx = config["configurable"].get(TOOL_CONTEXT_KEY)
    pending = graph.get_state(config).values.get("pending_evidence") or []
    if ctx is not None and pending:
        kept = files_service.evidence_ids(ctx.db, ctx.account, pending)
        ctx.evidence_file_ids = list(dict.fromkeys([*kept, *ctx.evidence_file_ids]))


def graph_responder(
    turn: TurnInput, checkpointer: BaseCheckpointSaver | None = None
) -> Iterator[TurnEvent]:
    """노드가 낸 이벤트를 흘려보냅니다.

    `done`은 그래프가 체크포인트 저장까지 끝낸 뒤 보냅니다. 노드가 낸 `done`(근거 줄)은
    잡아 두었다가 그때 보내고, 노드가 내지 않았으면 빈 `done`을 보냅니다.
    질문(interrupt)에서 멈춘 턴도 같은 방식으로 `done`으로 끝납니다.
    도중에 실패하면 `done` 없이 오류로 끝납니다.
    """
    graph = build_graph(checkpointer or checkpointer_module.get_checkpointer())
    config = run_config(turn)
    done = TurnEvent(DoneEvent())
    payload = turn_input(graph, turn, config)
    if isinstance(payload, Command):
        restore_evidence(graph, config)
    if payload is None:
        yield TurnEvent(TokenEvent(text=BLOCKED_REPLY))
        yield done
        return
    try:
        for event in graph.stream(payload, config, stream_mode="custom"):
            if not isinstance(event, TurnEvent):
                continue
            if isinstance(event.data, DoneEvent):
                done = event
            else:
                yield event
    finally:
        # 질문에 답하는 재개 턴은 preprocess를 거치지 않아 첨부를 읽지 않으므로 지우지 않습니다.
        # 연결이 끊겨 스트림이 닫혀도(close) 읽은 이력서 서류는 지웁니다.
        read_files = turn.file_ids and not isinstance(payload, Command)
        if read_files and (ctx := tool_context(turn)) is not None:
            files_service.discard_resume_docs(ctx.db, ctx.account, turn.file_ids)
    snapshot = graph.get_state(config)
    if snapshot.next and snapshot.values:
        # 질문에서 멈춘 턴은 finish를 거치지 않습니다. 질문 앞에 안내한 내용의 근거 줄과
        # 다음 할 일이 빠지지 않게 지금 상태로 만듭니다.
        done = TurnEvent(done_event(snapshot.values))
    yield done


def get_responder() -> Responder:
    return graph_responder
