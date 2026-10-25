"""이번 턴에 확정된 사실을 DB에서 읽습니다. 확정 값은 대화 기억이 아니라 DB가 기준입니다(노션 8.3).

LLM은 이 숫자를 계산하지 않고 그대로 옮깁니다. 개인정보(user_profiles)는 읽지 않습니다.
"""

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.agent.graph import AgentState, tool_context_of
from app.core.errors import AppError
from app.schemas.procedure import Stage
from app.services import accounts as account_service
from app.services import resume as resume_service
from app.services import rounds as round_service


def load_context(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    ctx = tool_context_of(config)
    if ctx is None:  # DB 없이 그래프만 도는 단위 테스트
        return {"facts": {"today": None, "stage": None}}
    user_id = ctx.account.user_id
    procedure = account_service.read_procedure(ctx.db, user_id, ctx.today)
    resume = resume_service.read_resume(ctx.db, ctx.account)
    facts: dict[str, Any] = {
        "today": ctx.today.isoformat(),
        "stage": procedure.stage.value,
        "age_at_separation": procedure.age_at_separation,
        "education_done": procedure.education_done,
        "resume_status": resume.status.value,
        "resume_next_question": resume.next_question,
    }
    if procedure.stage == Stage.RECOGNITION:
        try:
            check = round_service.read_current(ctx.db, user_id, ctx.today)
        except AppError:  # 남은 회차가 없음(종료 직전)
            check = None
        if check is not None:
            facts["round"] = {
                "round": check.round,
                "period_start": check.period_start.isoformat(),
                "period_end": check.period_end.isoformat(),
                "recognition_date": check.recognition_date.isoformat(),
                "d_day": check.d_day,
                "required": check.required,
                "counted": check.counted,
                "remaining": check.remaining,
                "attendance_required": check.attendance_required,
            }
    return {"facts": facts}
