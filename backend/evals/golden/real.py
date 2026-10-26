"""골든셋 문항을 실제 대화 턴(services/chat)으로 실행합니다 (adapter.run_agent가 부름).

문항마다 새 방문자로 시연 계정에 입장하고, 말 하나마다 턴을 돌려 답 · 근거 줄을 모은 뒤
계정 상태를 결과 데이터로 돌려줍니다. 끝나면 방문자를 지워(계정 데이터 CASCADE) 흔적을
남기지 않습니다.
"""

import io
from datetime import date, datetime, time
from typing import Any

from sqlalchemy import delete

from app.agent.events import TOKEN
from app.core.clock import KST
from app.core.db import SessionLocal
from app.models import Visitor
from app.schemas.files import FilePurpose
from app.schemas.messages import InputKind, MessageCreate
from app.services import accounts as account_service
from app.services import application as application_service
from app.services import chat as chat_service
from app.services import files as file_service
from app.services import resume as resume_service
from app.services import rounds as round_service
from app.services.seed import load_personas
from app.services.visitors import authenticate, create_visitor
from evals.golden import mapping
from evals.golden.adapter import APPLICATION_PANEL_ACTION, NEXT_ACTION_BY_STAGE, AgentResult
from evals.golden.schema import FILES_DIR

DONE_EVENT = "done"
ASK_EVENT = "ask_user"
APPLICATION_PREFIX = "application."
# 이력서 서류 판독 문항(경력증명서 · 자격증 · 흐린 사진)과 활동 증빙(캡처)을 구분하는 이름 앞부분
RESUME_FILE_PREFIXES = ("career_", "license_", "resume_")


def _today(case: dict[str, Any]) -> date:
    return date.fromisoformat(case["input"]["state"]["demo_today"])


def run_real(case: dict[str, Any]) -> AgentResult:
    today = _today(case)
    now = datetime.combine(today, time(10), KST)
    persona = case["input"]["persona"]
    with SessionLocal() as db:
        load_personas(db)
        visitor = create_visitor(db, now)
        visitor_id = authenticate(db, visitor.visitor_token, now).visitor_id
        account_service.enter(db, visitor_id, persona, today)
        account = account_service.find_account(db, visitor_id, persona)
        db.commit()
        try:
            replies, cites, last_ask = [], [], None
            initial = _data(db, account, today, now)
            file_ids = _upload(db, account, case["input"]["files"])
            for index, text in enumerate(case["input"]["messages"]):
                body = MessageCreate(
                    text=text,
                    input_kind=InputKind.TEXT,
                    file_ids=file_ids if index == 0 else [],
                )
                turn = chat_service.start_turn(db, account, body, None, today)
                events = list(turn.events())
                replies.append("".join(e.data.text for e in events if e.name == TOKEN).strip())
                for event in events:
                    if event.name == DONE_EVENT and event.data.cite:
                        cites.append(event.data.cite)
                    if event.name == ASK_EVENT:
                        last_ask = event.data.question_id
            data = _data(db, account, today, now)
            stage = data["derived"]["stage"]
        finally:
            db.rollback()
            db.execute(delete(Visitor).where(Visitor.visitor_id == visitor_id))
            db.commit()
    action = NEXT_ACTION_BY_STAGE.get(stage)
    if last_ask and last_ask.startswith(APPLICATION_PREFIX):
        action = APPLICATION_PANEL_ACTION
    return AgentResult(
        replies=replies, next_action=action, data=data, cites=cites, initial_data=initial
    )


def _upload(db: Any, account: Any, names: list[str]) -> list[str]:
    ids: list[str] = []
    for name in names:
        is_resume_doc = name.startswith(RESUME_FILE_PREFIXES)
        purpose = FilePurpose.RESUME_DOC if is_resume_doc else FilePurpose.EVIDENCE
        content = (FILES_DIR / name).read_bytes()
        created = file_service.upload(db, account, name, io.BytesIO(content), purpose, None)
        ids.append(created.file_id)
    db.commit()
    return ids


def _data(db: Any, account: Any, today: date, now: datetime) -> dict[str, Any]:
    """결과 데이터. 이름은 골든셋 기대값(derived · round · resume · activities · recognition)."""
    procedure = account_service.read_procedure(db, account.user_id).model_dump(mode="json")
    try:
        raw_resume = resume_service.read_resume(db, account).model_dump(mode="json")["data"]
    except Exception:  # noqa: BLE001 - 이력서가 아직 없음(박진수 처음)
        raw_resume = {}
    try:
        round_check = round_service.read_current(db, account.user_id, today).model_dump(mode="json")
        application = application_service.read_application(db, account, "current", now)
        raw_application = application.model_dump(mode="json")
    except Exception:  # noqa: BLE001 - 회차가 없는 단계(구직등록 등)
        round_check, raw_application = {}, {}
    return {
        "derived": mapping.derived(procedure, round_check),
        "round": mapping.round_values(round_check),
        "activities": mapping.activities(round_check),
        "resume": mapping.resume(raw_resume),
        "recognition": mapping.recognition(raw_application),
    }
