"""이번 턴에 확정된 사실을 DB에서 읽습니다. 확정 값은 대화 기억이 아니라 DB가 기준입니다(노션 8.3).

LLM은 이 숫자를 계산하지 않고 그대로 옮깁니다. 개인정보(user_profiles)는 읽지 않습니다.
"""

from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from app.agent.graph import AgentState, tool_context_of
from app.agent.nodes.route import Panel
from app.agent.retrieval import rerank_cards, rewrite_query
from app.agent.tools import guide
from app.core.config import get_settings
from app.core.errors import AppError
from app.rules.briefing import build_briefing, interval_days, person_lines, resume_items
from app.rules.next_action import next_action
from app.rules.rule_cards import GROUP_LABELS, Profile, cards_by_id, cards_for, search_cards
from app.schemas.procedure import Stage
from app.schemas.rounds import ActivityStatus
from app.services import accounts as account_service
from app.services import knowledge as knowledge_service
from app.services import resume as resume_service
from app.services import rounds as round_service

# 소정급여일수 표가 나뉘는 나이(이직 당시)
OVER_50_AGE = 50
# 검색 문장을 바꿀 때 넣는 앞선 사용자 말 수
REWRITE_HISTORY = 2
COUNT_RULE_NOTE = "필요 건수는 rules의 이 수급자 유형·회차 카드를 따른다"
# 브리핑이 "왜 인정되지 않았는지"를 설명하는 활동 상태
NOT_COUNTED_REASONS = (ActivityStatus.SAME_DAY, ActivityStatus.OUT_OF_PERIOD)


def load_context(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    ctx = tool_context_of(config)
    if ctx is None:  # DB 없이 그래프만 도는 단위 테스트
        return {"facts": {"today": None, "stage": None}}
    user_id = ctx.account.user_id
    procedure = account_service.read_procedure(ctx.db, user_id, ctx.today)
    resume = resume_service.read_resume(ctx.db, ctx.account)
    facts: dict[str, Any] = {
        "today": ctx.today.isoformat(),
        # 인정일 당일 마감(17시) 같은 질문에 답하려면 지금 시각이 근거로 있어야 합니다.
        "now_time": ctx.now.strftime("%H:%M"),
        "stage": procedure.stage.value,
        "age_at_separation": procedure.age_at_separation,
        # 수급자 유형마다 회차별 활동 횟수·출석 규칙이 다릅니다(일반·만 60~64세·65세 이상·반복).
        "recipient_group": GROUP_LABELS.get(procedure.recipient_group, procedure.recipient_group),
        "has_disability": procedure.has_disability,
        "education_done": procedure.education_done,
        "resume_status": resume.status.value,
        # 전체 순서와 그 근거 카드. 답이 순서를 설명하면 finish가 근거 줄에 넣습니다.
        "procedure_steps": guide.overview(),
        # save_resume_fields가 반복 항목을 가리킬 item_id(이력서 칸 값, 개인정보 아님)
        "resume_items": resume_items(resume.data),
    }
    check = None
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
                "required_job_search": check.required_job_search,
                # 기록했지만 인정되지 않은 활동(같은 날·대상기간 밖)의 날짜와 이유
                "not_counted": [
                    {"date": a.activity_date.isoformat(), "status": a.status.value}
                    for a in check.activities
                    if a.status in NOT_COUNTED_REASONS
                ],
                "now_time": facts["now_time"],
                "interval_days": interval_days(procedure.recipient_group, check.round),
                "job_search_only": bool(check.required)
                and check.required_job_search == check.required,
                "attendance_required": check.attendance_required,
                # 회차 숫자를 계산한 규칙(활동 횟수·기간). 답이 이 숫자를 쓰면 근거 줄에 넣습니다.
                "rule_refs": check.rule_refs,
            }
            if check.required is None:
                # 코드가 필요 건수를 셀 수 없는 수급자 유형(반복수급자 등). "부족 0건"으로
                # 보이지 않게 건수를 비우고, 유형별 규칙 카드를 따르라고 적어 둡니다.
                facts["round"] |= {"remaining": None, "remaining_job_search": None}
                facts["round"]["count_rule"] = COUNT_RULE_NOTE
    question = resume_service.read_next_question(ctx.db, ctx.account)
    facts["resume_ready"] = account_service.resume_ready(ctx.db, user_id, procedure)
    action = next_action(
        facts["stage"],
        facts.get("round"),
        resume_ready=facts["resume_ready"],
        education_done=procedure.education_done,
    )
    # 모델이 JSON을 해석하지 않아도 되게 코드가 결론을 문장으로 씁니다(rules/briefing).
    facts["briefing"] = build_briefing(
        facts["stage"],
        round_=facts.get("round"),
        action=action,
        resume_question=question,
        education_done=procedure.education_done,
        age=procedure.age_at_separation,
        group=procedure.recipient_group,
        person=person_lines(
            age=procedure.age_at_separation,
            separation_date=procedure.separation_date,
            group_label=facts["recipient_group"],
            has_disability=procedure.has_disability,
            resume=resume.data,
        ),
    )
    facts["next_action"] = action.value if action else None
    situation = account_service.situation_rules(
        ctx.db, user_id, procedure, check, check.d_day if check else None
    )
    profile = {
        "group": procedure.recipient_group,
        "round_no": check.round if check else None,
        "over_50": procedure.age_at_separation >= OVER_50_AGE or procedure.has_disability,
    }
    return {"facts": facts, "situation_rules": situation, "profile": profile}


def attach_knowledge(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """미리 붙이는 방식(RULE_CARDS_MODE=inject)일 때 사용자 말로 근거를 찾아 붙입니다.

    - 규칙 카드: 모든 패널. 서류를 쓰다가도 증빙·마감을 물을 수 있고, 구직등록 단계의 절차 질문은
      이력서 패널로 가기도 합니다(이력서 패널에서 빼 보니 절차 영역 근거 줄 누락이 두 배로 늘었음).
    - 정책·FAQ 조각: 안내(guide) 패널만. 서류 작업 중에는 필요 없고 엉뚱한 근거만 늘어납니다.
    검색은 단어+벡터 하이브리드이고 관련도가 낮으면 아무것도 붙이지 않습니다(services/knowledge).
    붙인 카드는 attached에 두고, 답에 실제로 나온 카드만 finish가 근거 줄에 남깁니다.
    도구 방식(tool)이면 모델이 lookup_rules로 직접 찾으므로 지금 단계 규칙만 붙입니다.
    지금 단계·회차 규칙(situation_rules)은 질문과 상관없이 맨 앞에 붙이고, 검색은 사용자 조건
    (수급자 유형·회차)에 맞는 카드만 찾습니다(rule_cards.applies_to).
    """
    settings = get_settings()
    text = str(state["messages"][-1].content)
    profile = Profile(**state["profile"]) if state.get("profile") else None
    # 질문과 상관없이 먼저 붙이는 카드: 지금 단계의 규칙(첫 안내와 같은 분기)과 이 수급자 유형·
    # 회차에 정해진 규칙(질문에 "4차"가 있으면 그 회차).
    cards = [c for i in state.get("situation_rules", []) if (c := cards_by_id().get(i))]
    if profile:
        cards += cards_for(profile.for_query(text))
    cards = list({c.rule_id: c for c in cards}.values())
    guides = []
    calls = state.get("model_calls", 0)
    if settings.rule_cards_mode == "inject":
        ctx = tool_context_of(config)
        if ctx is None:  # DB 없이 그래프만 도는 단위 테스트: 단어 검색만
            found_cards = search_cards(text, settings.retrieval_inject_limit, profile)
        else:
            guide_limit = settings.retrieval_guide_limit if state.get("panel") == Panel.GUIDE else 0
            query, calls = search_text(state, text)
            limit = settings.retrieval_inject_limit
            # 재정렬하면 후보를 넉넉히 찾고 모델이 limit장을 고릅니다.
            wanted = settings.retrieval_rerank_candidates if settings.retrieval_rerank else limit
            found = knowledge_service.search(ctx.db, query, wanted, guide_limit, profile=profile)
            found_cards, guides = knowledge_service.rule_cards_of(found.rules), found.guides
            if settings.retrieval_rerank and found_cards:
                found_cards = rerank_cards(query, found_cards, limit)
                calls += 1
        cards += [c for c in found_cards if c.rule_id not in {x.rule_id for x in cards}]
    if not cards and not guides:
        return {"attached": [], "model_calls": calls}
    facts = {**state.get("facts", {}), "rules": [c.for_model() for c in cards]}
    if guides:
        facts["guides"] = [knowledge_service.guide_for_model(g) for g in guides]
    # 붙인 근거 중 답에 실제로 쓴 것만 finish가 근거 줄에 남깁니다(agent/grounding.used_in_answer).
    return {"facts": facts, "attached": [c.rule_id for c in cards], "model_calls": calls}


def search_text(state: AgentState, text: str) -> tuple[str, int]:
    """검색할 문장과 이번 턴 모델 호출 수. 이어지는 말만 앞선 사용자 말을 넣어 바꿉니다.

    앞선 말은 preprocess가 가린 뒤 저장한 글이라 개인정보가 없습니다.
    """
    calls = state.get("model_calls", 0)
    earlier = [str(m.content) for m in state["messages"][:-1] if isinstance(m, HumanMessage)]
    if not get_settings().retrieval_rewrite or not earlier:
        return text, calls
    return rewrite_query(text, earlier[-REWRITE_HISTORY:]), calls + 1
