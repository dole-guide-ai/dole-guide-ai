"""방문자 발급, 시연 계정 카드, 계정 입장 결과의 응답 스키마입니다.

입장 결과(AccountRead)에는 절차 상태, 지금 회차, 그리고 첫 화면을 그리는 진입 결과(Entry)가 들어
있습니다.
진입 결과는 템플릿으로 만들고 LLM은 쓰지 않습니다.
"""

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel

from app.schemas.application import SubmitMode
from app.schemas.messages import AskUserEvent
from app.schemas.procedure import ProcedureRead
from app.schemas.rounds import RoundSummary


class VisitorCreated(BaseModel):
    visitor_token: str
    expires_at: datetime


class PersonaDisplay(BaseModel):
    name: str
    age: int
    job: str
    quote: str
    summary: str


class PersonaCard(BaseModel):
    persona_id: str
    display: PersonaDisplay
    progress_summary: str | None = None


class PersonaList(BaseModel):
    items: list[PersonaCard]
    total: int


class EntryMessage(BaseModel):
    template_id: str
    text: str
    cite: str | None = None


class Progress(BaseModel):
    current: int
    done: list[int] = []


class EntryUi(BaseModel):
    big_text: bool = False


class EntryFlags(BaseModel):
    m1: bool = False


class Entry(BaseModel):
    """입장할 때 정하는 첫 화면. 템플릿으로 만들고 LLM은 쓰지 않습니다."""

    branch_id: str
    panel: str
    progress: Progress
    title: str
    next_step_text: str
    messages: list[EntryMessage] = []
    choices: list[str] = []
    # 첫 안내가 서류·사진을 요청하면 파일 올리기를 켭니다 (2-0.4 accepts_file)
    accepts_file: bool = False
    ui: EntryUi = EntryUi()
    flags: EntryFlags = EntryFlags()
    rule_refs: list[str] = []


class RoundDeadline(BaseModel):
    """지금 회차의 인정일까지 남은 날과 지금 시각의 제출 방식. 판정은 서버(rules/application)만."""

    d_day: int
    submit_mode: SubmitMode
    # 인정일 당일 18시가 지나 변경 신청만 할 수 있음(submit_mode가 change)
    overdue: bool


class NoticeKind(StrEnum):
    VISIT = "visit"  # 수급자격 신청은 센터 방문 (PROC-048)
    OVERDUE = "overdue"  # 인정일이 지나 변경 신청 (DUE-089·094)
    ATTEND = "attend"  # 출석 회차 (ACT-040)


class Notice(BaseModel):
    """대시보드 알림 하나. 문구는 템플릿(data/templates/notices.json), 근거는 rule_refs."""

    kind: NoticeKind
    key: str  # 같은 알림을 닫았는지 기억하는 키(예: overdue-2026-10-27)
    title: str
    text: str
    rule_refs: list[str] = []


class AccountRead(BaseModel):
    persona_id: str
    today: date
    procedure: ProcedureRead
    current_round: RoundSummary | None = None
    deadline: RoundDeadline | None = None
    notices: list[Notice] = []
    entry: Entry
    # 답을 기다리던 질문. 대화 턴의 ask_user 이벤트와 같은 모양입니다 (F-03).
    pending_ask: AskUserEvent | None = None
