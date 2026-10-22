"""방문자 발급, 시연 계정 카드, 계정 입장 결과의 응답 스키마입니다.

입장 결과(AccountRead)에는 절차 상태, 지금 회차, 그리고 첫 화면을 그리는 진입 결과(Entry)가 들어
있습니다.
진입 결과는 템플릿으로 만들고 LLM은 쓰지 않습니다.
"""

from datetime import date, datetime

from pydantic import BaseModel

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
    ui: EntryUi = EntryUi()
    flags: EntryFlags = EntryFlags()
    rule_refs: list[str] = []


class AskUser(BaseModel):
    question_id: str
    text: str
    choices: list[str] = []
    import_kind: str | None = None
    # 서류·사진을 요청한 질문이면 true (새로고침 뒤에도 파일 올리기를 켭니다, F-03)
    accepts_file: bool = False


class AccountRead(BaseModel):
    persona_id: str
    today: date
    procedure: ProcedureRead
    current_round: RoundSummary | None = None
    entry: Entry
    pending_ask: AskUser | None = None
