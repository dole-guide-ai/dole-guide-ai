"""이력서는 코드가 대화를 이끕니다: 다음 질문은 턴 끝에 코드가, 정해진 선택지 답은 LLM 없이.

- ask_next: 이력서 패널 턴이 끝나면 규칙 함수(next_resume_question)로 다음 빈 칸을 고르고
  템플릿 문구(rules/question_text)로 질문 카드를 냅니다. 모델은 질문을 쓰지 않고 저장한 것만
  확인하므로 질문이 두 번 나오거나 순서가 흔들리지 않습니다. 첫 경력을 채운 뒤에는 그 전 경력이
  있는지 한 번 묻습니다.
- answer_fixed: 지난 질문의 선택지 중 답이 정해진 것("자격증 없어요" 등)은 코드가 저장하고
  짧게 확인합니다(LLM 0회).
되묻기는 interrupt로 멈추지 않고 질문을 낸 채 턴을 끝냅니다. 다음 말은 새 턴이고,
낸 질문은 pending_question과 대화 기록에 남습니다.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from app.agent.events import emit
from app.agent.graph import AgentState, tool_context_of
from app.agent.nodes.route import Panel
from app.rules import question_text as qt
from app.rules.resume import ResumeQuestion, suggest_resume_title
from app.rules.resume_facts import CERTIFICATIONS_STATUS, COMPETENCIES_STATUS, not_applicable
from app.schemas.common import FieldSource, FieldStatus
from app.schemas.forms.resume import ResumeData
from app.schemas.imports import ImportKind
from app.schemas.messages import AskUserEvent, TokenEvent
from app.schemas.resume import FieldWrite
from app.services import resume as resume_service

# 사진을 올려 답할 수 있는 질문, 고용24에서 불러와 답할 수 있는 질문
FILE_QUESTIONS = {"resume.doc_retry", "resume.career_new", "resume.license"}
IMPORT_QUESTIONS = {"resume.career_new": ImportKind.CAREER_CERTIFICATE}
CAREER_PREFIX = "resume.career"


# 같은 질문을 연달아 낸 횟수 상한. 답을 저장하지 못해 같은 칸이 계속 비어 있어도 세 번째는
# 내지 않고 모델 답에 맡깁니다(같은 질문 되풀이 방지).
MAX_SAME_QUESTION = 2
# 선택지 답을 비교할 때 빼는 글자(공백·문장부호). "없었어요."도 "없었어요"로 봅니다.
_IGNORED = re.compile(r"[\s.,!?~…]")


Writes = Callable[[ResumeData, dict[str, Any]], list[FieldWrite]]


@dataclass(frozen=True)
class FixedAnswer:
    ack: str
    # (지금 이력서, 질문 문구 변수) → 저장할 칸. 없으면 확인만 합니다.
    writes: Writes | None = None


def _said(path: str, value: Any) -> FieldWrite:
    return FieldWrite(
        path=path, value=value, status=FieldStatus.CONFIRMED, source=FieldSource.USER_ANSWER
    )


def _none_section(path: str) -> Writes:
    return lambda data, vars_: [not_applicable(path)]


def _preference(name: str, value: Any) -> Writes:
    return lambda data, vars_: [_said(f"/job_preferences/{name}", value)]


def _career_field(name: str, value: Any) -> Writes:
    """질문의 회사(변수 company) 경력 항목에 씁니다. 못 찾으면 가장 최근 경력."""

    def writes(data: ResumeData, vars_: dict[str, Any]) -> list[FieldWrite]:
        careers = data.careers
        match = next((c for c in careers if c.company_name.value == vars_.get("company")), None)
        target = match or (careers[-1] if careers else None)
        return [_said(f"/careers/{target.item_id}/{name}", value)] if target else []

    return writes


def _wish_experience(value: str) -> Writes:
    """질문의 희망 직종(변수 occupation) 항목에 경력 여부를 씁니다."""

    def writes(data: ResumeData, vars_: dict[str, Any]) -> list[FieldWrite]:
        items = data.job_preferences.desired_occupations
        name = vars_.get("occupation")
        match = next(
            (
                o
                for o in items
                if isinstance(o.occupation.value, dict) and o.occupation.value.get("name") == name
            ),
            items[0] if items else None,
        )
        path = f"/job_preferences/desired_occupations/{match.item_id}/experience_type"
        return [_said(path, value)] if match else []

    return writes


def _title(data: ResumeData, vars_: dict[str, Any]) -> list[FieldWrite]:
    return [_said("/resume_title", vars_.get("title") or suggest_resume_title(data))]


# 희망 월급을 "면접 후 결정"으로 둘 때의 값(금액 없음, 협의 가능)
NEGOTIABLE_SALARY = {"amount": None, "unit": "monthly", "currency": "KRW", "negotiable": True}

# (질문 ID, 답) → 코드가 처리하는 답. 선택지 버튼과 같은 답만 여기서 처리하고, 나머지 말은
# 모델이 record_resume_facts·save_resume_fields로 저장합니다. 값은 고용24 칸 선택지와 같습니다.
FIXED_ANSWERS: dict[tuple[str, str], FixedAnswer] = {
    ("resume.license", "없어요"): FixedAnswer(
        "자격증·면허는 없는 것으로 적었어요.", _none_section(CERTIFICATIONS_STATUS)
    ),
    ("resume.optional_sections", "없어요"): FixedAnswer(
        "더 적을 역량은 없는 것으로 적었어요.", _none_section(COMPETENCIES_STATUS)
    ),
    ("resume.career_more", "없어요"): FixedAnswer("경력은 지금 적은 회사까지로 둘게요."),
    ("resume.career_position", "없었어요"): FixedAnswer(
        "직급·직책은 없음으로 적었어요.", _career_field("position", "없음")
    ),
    ("resume.wish_experience", "네, 맞아요"): FixedAnswer(
        "희망 직종은 경력으로 적었어요.", _wish_experience("경력")
    ),
    ("resume.wish_experience", "아니요"): FixedAnswer(
        "희망 직종은 신입으로 적었어요.", _wish_experience("신입")
    ),
    ("resume.wish_wage", "면접 후 결정할게요"): FixedAnswer(
        "희망 월급은 면접 후 결정으로 적었어요.",
        _preference("desired_salary", NEGOTIABLE_SALARY),
    ),
    ("resume.wish_employment", "정해지지 않은 일"): FixedAnswer(
        "고용형태는 기간의 정함이 없는 근로계약으로 적었어요.",
        _preference("employment_contract_type", "기간의 정함이 없는 근로계약"),
    ),
    ("resume.wish_employment", "정해진 일"): FixedAnswer(
        "고용형태는 기간의 정함이 있는 근로계약으로 적었어요.",
        _preference("employment_contract_type", "기간의 정함이 있는 근로계약"),
    ),
    ("resume.wish_employment", "상관없어요"): FixedAnswer(
        "고용형태는 관계없음으로 적었어요.", _preference("employment_contract_type", "관계없음")
    ),
    ("resume.wish_military", "네, 맞아요"): FixedAnswer(
        "병역대체 근무는 해당 없음으로 적었어요.",
        _preference("military_alternative", "해당 없음"),
    ),
    ("resume.resume_title", "네, 좋아요"): FixedAnswer("이력서 제목을 적었어요.", _title),
}


def _norm(text: str) -> str:
    return _IGNORED.sub("", text)


def fixed_answer_of(state: AgentState) -> FixedAnswer | None:
    pending = state.get("pending_question")
    last = state["messages"][-1] if state.get("messages") else None
    if not pending or not isinstance(last, HumanMessage):
        return None
    answer = _norm(str(last.content))
    return next(
        (
            f
            for (qid, choice), f in FIXED_ANSWERS.items()
            if qid == pending["id"] and _norm(choice) == answer
        ),
        None,
    )


def after_context(state: AgentState) -> str:
    return "answer_fixed" if fixed_answer_of(state) else "route_turn"


def answer_fixed(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    fixed = fixed_answer_of(state)
    ctx = tool_context_of(config)
    if fixed is None or ctx is None:
        return {}
    if fixed.writes:
        data = resume_service.read_resume(ctx.db, ctx.account).data
        pending_vars = (state.get("pending_question") or {}).get("vars", {})
        if writes := fixed.writes(data, pending_vars):
            saved = resume_service.save_resume_fields(
                ctx.db, ctx.account.user_id, writes, today=ctx.today
            )
            for update in saved.updates:
                emit(update)
    emit(TokenEvent(text=fixed.ack))
    return {"panel": Panel.RESUME, "messages": [AIMessage(fixed.ack)]}


def _oldest_company(careers: list[Any]) -> str | None:
    dated = sorted(careers, key=lambda c: str(c.start_date.value or "9999"))
    return dated[0].company_name.value if dated else None


def ask_next(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    ctx = tool_context_of(config)
    if ctx is None or state.get("blocked") or state.get("panel") != Panel.RESUME:
        return {"pending_question": None}
    q: ResumeQuestion = resume_service.read_next_question(ctx.db, ctx.account)
    update: dict[str, Any] = {}
    if not state.get("asked_more_careers") and not q.id.startswith(CAREER_PREFIX):
        careers = resume_service.read_resume(ctx.db, ctx.account).data.careers
        if careers:
            q = qt.career_more(_oldest_company(careers))
            update["asked_more_careers"] = True
    text = qt.question_text(q)
    if text is None:
        return {**update, "pending_question": None}
    choices = qt.question_choices(q)
    previous = state.get("pending_question") or {}
    times = previous.get("times", 0) + 1 if previous.get("id") == q.id else 1
    pending = {"id": q.id, "choices": choices, "vars": q.vars, "times": times}
    if times > MAX_SAME_QUESTION:
        return {**update, "pending_question": pending}
    kind = IMPORT_QUESTIONS.get(q.id)
    emit(
        AskUserEvent(
            question_id=q.id,
            text=text,
            choices=choices,
            import_kind=kind.value if kind else None,
            accepts_file=q.id in FILE_QUESTIONS,
        )
    )
    return {**update, "pending_question": pending, "messages": [AIMessage(text)]}
