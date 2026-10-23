"""대화 턴 서비스와 에이전트가 만나는 자리입니다.

서비스는 `gateway`처럼 이 모듈을 통해 `get_responder()`를 불러, 받은 응답기에 사용자 말을 넘기고
`TurnEvent`를 차례로 받습니다. 지금은 받은 말을 되돌려주는 임시 응답기이고, 에이전트(LangGraph)를
붙일 때 `get_responder()`가 그래프 실행기를 돌려주게 바꿉니다. 테스트는 이 함수를 바꿔 끼웁니다.

응답기에는 개인정보 컬럼(user_profiles)을 넘기지 않습니다.
"""

import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import date

from app.agent.events import TurnEvent
from app.schemas.messages import DoneEvent, InputKind, TokenEvent


@dataclass(frozen=True)
class TurnInput:
    user_id: uuid.UUID
    persona_id: str
    text: str
    input_kind: InputKind
    today: date
    file_ids: list[str] = field(default_factory=list)
    import_ids: list[str] = field(default_factory=list)


Responder = Callable[[TurnInput], Iterator[TurnEvent]]

_ECHO_REPLY = "말씀하신 내용을 받았어요. AI 답변은 곧 연결돼요."


def echo_responder(turn: TurnInput) -> Iterator[TurnEvent]:
    """에이전트를 붙이기 전 임시 응답기. 사용자 말은 되풀이하지 않습니다(로그·화면 노출 최소화)."""
    for word in _ECHO_REPLY.split(" "):
        yield TurnEvent(TokenEvent(text=word + " "))
    yield TurnEvent(DoneEvent())


def get_responder() -> Responder:
    return echo_responder
