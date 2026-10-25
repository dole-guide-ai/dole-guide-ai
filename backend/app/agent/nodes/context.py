"""이번 턴에 확정된 사실을 DB에서 읽습니다. 확정 값은 대화 기억이 아니라 DB가 기준입니다(노션 8.3).

LLM은 이 숫자를 계산하지 않고 그대로 옮깁니다. 개인정보(user_profiles)는 읽지 않습니다.
"""

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.agent.graph import AgentState, tool_context_of
from app.agent.nodes.route import Panel
from app.core.config import get_settings
from app.core.errors import AppError
from app.rules.rule_cards import search_cards
from app.schemas.procedure import Stage
from app.services import accounts as account_service
from app.services import knowledge as knowledge_service
from app.services import resume as resume_service
from app.services import rounds as round_service

# 미리 붙이는 카드 수(lookup_rules가 돌려주는 수와 같게 해 두 방식을 같은 조건으로 비교)
INJECT_LIMIT = 3


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
                "remaining_job_search": check.remaining_job_search,
                "attendance_required": check.attendance_required,
            }
    return {"facts": facts}


def attach_knowledge(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """미리 붙이는 방식(RULE_CARDS_MODE=inject)일 때 사용자 말로 근거를 찾아 붙입니다.

    - 규칙 카드: 모든 패널. 서류를 쓰다가도 증빙·마감을 물을 수 있습니다.
    - 정책·FAQ 조각: 안내(guide) 패널만. 서류 작업 중에는 필요 없고 엉뚱한 근거만 늘어납니다.
    검색은 단어+벡터 하이브리드이고 관련도가 낮으면 아무것도 붙이지 않습니다(services/knowledge).
    붙인 근거는 실제로 답에 썼는지 알 수 없어 모두 근거 후보로 둡니다(이 방식의 한계).
    도구 방식(tool)이면 모델이 lookup_rules로 직접 찾으므로 아무것도 하지 않습니다.
    """
    settings = get_settings()
    if settings.rule_cards_mode != "inject":
        return {}
    text = str(state["messages"][-1].content)
    ctx = tool_context_of(config)
    if ctx is None:  # DB 없이 그래프만 도는 단위 테스트: 단어 검색만
        cards, guides = search_cards(text, INJECT_LIMIT), []
    else:
        guide_limit = settings.retrieval_guide_limit if state.get("panel") == Panel.GUIDE else 0
        found = knowledge_service.search(ctx.db, text, INJECT_LIMIT, guide_limit)
        cards, guides = knowledge_service.rule_cards_of(found.rules), found.guides
    facts = {**state.get("facts", {}), "rules": [c.for_model() for c in cards]}
    if guides:
        facts["guides"] = [knowledge_service.guide_for_model(g) for g in guides]
    return {
        "facts": facts,
        "cited": [c.rule_id for c in cards],
        "cited_sources": [knowledge_service.guide_source_label(g) for g in guides],
    }
