"""에이전트 연결부: 이 브랜치의 실제 대화 서비스(services/chat.start_turn)로 한 턴씩 보냅니다.

설계가 다른 브랜치와 견줄 때는 이 파일만 그 브랜치의 진입점에 맞춰 바꿉니다.
"""

from datetime import date, datetime, time
from typing import Any

from sqlalchemy.orm import Session

from app.core.clock import KST
from app.schemas.messages import MessageCreate
from app.services import chat as chat_service
from evals.golden.presets import resolve_input
from evals.golden.runner import _enter, _snapshot

PERSONA = "park"  # 구직등록 단계, 이력서 없음


class AgentDriver:
    def __init__(self, db: Session, case_id: str) -> None:
        case_input = resolve_input(
            {"persona": PERSONA, "state": {}, "activities": None, "messages": [], "files": []}
        )
        state = case_input["state"]
        self.db = db
        self.today = date.fromisoformat(state["demo_today"])
        self.now = datetime.combine(self.today, time.fromisoformat(state["demo_time"]), KST)
        self.account = _enter(db, f"interview_{case_id}", case_input, self.today, self.now)

    def send(self, text: str) -> str:
        """사용자 말 하나 → 화면에 보인 답(글자 + 질문 카드 문장·선택지)."""
        turn = chat_service.start_turn(
            self.db, self.account, MessageCreate(text=text), None, self.now
        )
        events = list(turn.events())
        turn.finish()
        parts: list[str] = []
        for e in events:
            if e.name == "token":
                parts.append(e.data.text)
            elif e.name == "ask_user":
                choices = f" (선택지: {' / '.join(e.data.choices)})" if e.data.choices else ""
                parts.append(f"\n{e.data.text}{choices}")
        return "".join(parts).strip()

    def resume(self) -> dict[str, Any]:
        return _snapshot(self.db, self.account, self.today, self.now)["resume"]
