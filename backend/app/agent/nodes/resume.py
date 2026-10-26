"""이력서 대화. 모델에게 "할지 말지"를 맡기지 않고 "무엇인지"만 맡깁니다.

한 턴(이력서 패널):
- `apply_choice`: 지난 질문의 버튼 답은 모델 없이 코드가 저장·미룹니다. 질문은 낼 때 정의를 통째로
  작업 기억에 남기고(`ResumeStep.to_pending`), 답은 그것만 보고 처리합니다.
- `read_answer`(모델 ①, 구조화 출력): 사용자 말을 "기다리는 칸의 값 / 모름 / 딴 얘기 / 맡김 /
  그만 / 수정 / 함께 말한 사실"로만 읽습니다. 저장하지 않습니다. 이어서 `save_answer`(코드)가
  읽은 값을 스키마로 검증해 저장하거나 미루고, 결과를 `outcome`에 둡니다.
- `speak`(모델 ③): outcome과 진행표 첫 칸을 받아 확인 문장(스트리밍)을 씁니다. 다음 질문 카드는
  문장·선택지·파일 여부 모두 코드가 진행표 템플릿으로 냅니다(모델이 묻지 않음).

무엇을 어떤 순서로 묻는지, 제안 값, 검증은 `rules/resume/steps.py`와 스키마가 정합니다.
작업 기억은 `AgentState.resume`(체크포인트)에 둡니다. 칸 값은 DB가 기준이고, 여기에는 대화에서만
알 수 있는 것(대기 질문·물은 횟수·미룬 칸·이번 턴 결과)만 둡니다.
"""

import json
import re
from typing import Any, Literal, NotRequired, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from app.agent import gateway
from app.agent.events import emit
from app.agent.graph import AgentState, tool_context_of
from app.agent.output import SentenceStream
from app.agent.prompts import load_prompt
from app.agent.tools.registry import ToolContext
from app.rules import entry_text
from app.rules import resume as rules
from app.rules.resume.facts import ResumeFacts, answer_writes, plan_writes
from app.rules.resume.fields import said
from app.rules.resume.steps import (
    DEFERRED_REVIEW,
    DONT_KNOW,
    FILL_NOW,
    FOLLOW_UPS,
    ResumeStep,
)
from app.schemas.forms.resume import choices_of
from app.schemas.messages import AskUserEvent, TokenEvent
from app.schemas.resume import FieldWrite
from app.services import accounts as account_service
from app.services import resume as resume_service

# 모델에 넘기는 진행표 칸 수. 다음 칸 하나만 주면 묶어서 제안하거나 앞을 내다볼 수 없습니다.
PLAN_SIZE = 3
READ_PROMPT = "resume/read_answer"
SPEAK_PROMPT = "resume/speak"
# 읽기에 함께 주는 최근 대화 수(사람 말·도우미 말)
READ_HISTORY = 4
GUIDE_PANEL = "guide"
RESET_RESUME = "reset_resume"
# 버튼 답을 비교할 때 빼는 글자(공백·문장부호). "없었어요."도 "없었어요"로 봅니다.
_IGNORED = re.compile(r"[\s.,!?~…]")

Kind = Literal["value", "not_known", "stop", "delegate", "correction", "off_topic", "none"]


class Correction(BaseModel):
    path: str = Field(pattern=r"^/", description="고칠 칸 경로(resume_items의 item_id 포함)")
    value: Any = None


class FieldValue(BaseModel):
    """기다리는 칸 밖에서 함께 말한 값 하나. 경로는 writable_fields 목록에서 고릅니다."""

    path: str = Field(pattern=r"^/")
    value: Any = None


class Reading(BaseModel):
    """모델 ①이 돌려주는 것. 저장 여부는 코드가 정합니다."""

    kind: Kind = "none"
    value: Any = None
    facts: ResumeFacts | None = None
    # 희망 월급·고용형태·병역·운전처럼 facts에 없는 칸은 경로로(스키마 전체 칸 목록에서 고름)
    fields: list[FieldValue] | None = None
    correction: Correction | None = None
    note: str | None = None


class Outcome(TypedDict, total=False):
    reset: bool  # "새로 쓸래요"로 이력서를 비움
    saved: dict[str, Any]
    deferred: list[str]
    rejected: list[str]
    clarify: str | None
    off_topic: bool
    delegate: bool
    stop: bool


class ResumeMemory(TypedDict):
    asked: dict[str, int]
    deferred: list[str]
    # 지금 답을 기다리는 질문의 정의(ResumeStep.to_pending). 답은 이것만 보고 처리합니다.
    pending: NotRequired[dict[str, Any] | None]
    # 이번 턴 결과. 말하기는 이것만 보고 확인 문장을 씁니다. 턴마다 비웁니다.
    outcome: NotRequired[Outcome]
    # 이번 턴에 버튼 답을 코드가 처리해 읽기를 건너뛰는지
    handled: NotRequired[bool]
    # 마지막으로 사용자에게 알린 진행("꼭 채울 5개 중 n개")
    told_progress: NotRequired[str | None]
    # "있어요" 같은 버튼 뒤에 이어 물을 질문 ID(steps.FOLLOW_UPS). 답을 읽으면 비웁니다.
    follow: NotRequired[str | None]


def memory_of(state: AgentState) -> ResumeMemory:
    memory = state.get("resume") or {}
    return {
        "asked": dict(memory.get("asked", {})),
        "deferred": list(memory.get("deferred", [])),
        "pending": memory.get("pending"),
        "outcome": dict(memory.get("outcome", {})),
        "handled": bool(memory.get("handled", False)),
        "told_progress": memory.get("told_progress"),
        "follow": memory.get("follow"),
    }


def _steps(ctx: ToolContext, memory: ResumeMemory) -> list[ResumeStep]:
    return resume_service.read_steps(
        ctx.db,
        ctx.account,
        deferred=frozenset(memory["deferred"]),
        asked=memory["asked"],
        follow=memory.get("follow"),
    )


def _norm(text: str) -> str:
    return _IGNORED.sub("", text)


def _last_user_text(state: AgentState) -> str:
    last = next((m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), None)
    return str(last.content) if last else ""


# ── 진행표 ───────────────────────────────────────────────


def step_view(step: ResumeStep) -> dict[str, Any]:
    """모델이 읽는 단계 하나. 선택 칸은 고를 수 있는 값을, 제안은 칸 값과 근거를 붙입니다."""
    view: dict[str, Any] = {
        "key": step.key,
        "required": step.required,
        "question": rules.question_text(step),
        "paths": list(step.paths),
    }
    if step.choices:
        view["choices"] = list(step.choices)
    if allowed := {p: list(c) for p in step.paths if (c := choices_of(p))}:
        view["allowed"] = allowed
    if step.proposal:
        view["proposal"] = {w.path: w.value for w in step.proposal}
        view["reason"] = step.reason
    return view


def plan_facts(ctx: ToolContext, state: AgentState, filled: int) -> dict[str, Any]:
    memory = memory_of(state)
    steps = _steps(ctx, memory)
    plan: dict[str, Any] = {
        "progress": f"꼭 채울 {len(rules.REQUIRED_SECTIONS)}개 중 {filled}개",
        "steps": [step_view(s) for s in steps[:PLAN_SIZE]],
    }
    if memory["deferred"]:
        plan["deferred"] = memory["deferred"]
    return plan


def first_step(ctx: ToolContext, state: AgentState) -> ResumeStep | None:
    steps = _steps(ctx, memory_of(state))
    return steps[0] if steps else None


# ── 버튼 답 ─────────────────────────────────────────────


def apply_choice(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """지난 질문의 버튼 답을 코드가 처리합니다. 버튼이 아닌 말은 읽기(모델)로 갑니다."""
    memory = memory_of(state)
    memory["outcome"] = {}
    memory["handled"] = False
    ctx = tool_context_of(config)
    if ctx is None:
        return {"resume": memory}
    if action := entry_text.action_of(_last_user_text(state)):
        _entry_action(ctx, memory, action)  # 첫 안내 보기("새로 쓸래요")는 코드가 바로 합니다.
        memory["handled"], memory["pending"] = True, None
        return {"resume": memory}
    step = pending_step(memory)
    if step is None:
        return {"resume": memory}
    answer = _last_user_text(state)
    choice = _matching_choice(step, answer)
    if step.id == DEFERRED_REVIEW and choice:
        if choice == FILL_NOW:
            memory["deferred"], memory["asked"] = [], {}  # 두 번 물어 넘긴 칸도 다시 묻습니다.
        else:
            memory["deferred"].append(DEFERRED_REVIEW)
        memory["handled"], memory["pending"] = True, None
        return {"resume": memory}
    if _norm(answer) == _norm(DONT_KNOW):
        _defer(memory, [step.key])
        memory["handled"], memory["pending"] = True, None
        return {"resume": memory}
    writes = step.answer_writes(choice) if choice else None
    if writes is None:
        return {"resume": memory}  # 버튼 답이 아니면 모델이 읽습니다.
    _save(ctx, memory, list(writes))
    memory["follow"] = FOLLOW_UPS.get((step.id, choice))
    memory["handled"], memory["pending"] = True, None
    return {"resume": memory}


def pending_step(memory: ResumeMemory) -> ResumeStep | None:
    """작업 기억에 저장해 둔 "지금 기다리는 질문". 진행표를 다시 계산하지 않습니다."""
    pending = memory.get("pending")
    return ResumeStep.from_pending(pending) if pending else None


def _matching_choice(step: ResumeStep, answer: str) -> str | None:
    return next((c for c in step.choices if _norm(c) == _norm(answer)), None)


def _entry_action(ctx: ToolContext, memory: ResumeMemory, action: str) -> None:
    if action == RESET_RESUME:
        for update in resume_service.reset_resume(ctx.db, ctx.account):
            emit(update)
        memory["deferred"], memory["asked"] = [], {}
        memory["outcome"]["reset"] = True


def _defer(memory: ResumeMemory, keys: list[str]) -> None:
    new = [k for k in keys if k not in memory["deferred"]]
    memory["deferred"] += new
    memory["outcome"].setdefault("deferred", []).extend(new)


def _save(ctx: ToolContext, memory: ResumeMemory, writes: list[FieldWrite]) -> None:
    if not writes:
        return
    saved = resume_service.save_resume_fields(ctx.db, ctx.account.user_id, writes, today=ctx.today)
    for update in saved.updates:
        emit(update)
    memory["outcome"].setdefault("saved", {}).update({w.path: w.value for w in writes})


# ── 읽기 (모델 ①) ───────────────────────────────────────


def _read_input(state: AgentState, memory: ResumeMemory) -> str:
    facts = state.get("facts", {})
    pending = memory.get("pending")
    waiting = (
        {
            "question": pending["text"],
            "paths": pending["paths"],
            "allowed": {p: list(c) for p in pending["paths"] if (c := choices_of(p))},
        }
        if pending
        else None
    )
    recent = [
        f"{'사용자' if isinstance(m, HumanMessage) else '도우미'}: {m.text}"
        for m in state["messages"][-READ_HISTORY - 1 : -1]
        if isinstance(m, HumanMessage | AIMessage) and m.text
    ]
    payload = {
        "waiting": waiting,
        "resume_items": facts.get("resume_items"),
        "fields": facts.get("resume_fields"),
        "recent": recent,
    }
    return (
        f"## 기다리는 질문·칸\n{json.dumps(payload, ensure_ascii=False)}\n\n"
        f"<user_message>\n{_last_user_text(state)}\n</user_message>"
    )


def read_answer(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """사용자 말을 구조화 출력으로 읽고(모델 ①) 코드가 저장합니다(save_answer)."""
    memory = memory_of(state)
    ctx = tool_context_of(config)
    if ctx is None or memory["handled"]:
        return {"resume": memory}
    # value가 어떤 모양이든(글자·목록·사전) 받으므로 엄격한 JSON 스키마 대신 함수 호출 방식을 씀
    model = gateway.get_chat_model("extract").with_structured_output(
        Reading, method="function_calling"
    )
    reading: Reading = model.invoke(
        [SystemMessage(load_prompt(READ_PROMPT)), HumanMessage(_read_input(state, memory))]
    )
    memory = save_answer(ctx, memory, pending_step(memory), reading)
    update: dict[str, Any] = {"resume": memory, "model_calls": state.get("model_calls", 0) + 1}
    if memory["outcome"].get("off_topic"):
        update["panel"] = GUIDE_PANEL  # 제도 질문은 안내 패널이 답하고, 대기 질문은 남겨 둡니다.
    return update


def save_answer(
    ctx: ToolContext, memory: ResumeMemory, step: ResumeStep | None, reading: Reading
) -> ResumeMemory:
    """읽은 것을 스키마로 검증해 저장·미루기하고 outcome에 적습니다. 딴 얘기면 대기 질문을 둠."""
    outcome = memory["outcome"]
    if reading.kind == "off_topic":
        outcome["off_topic"] = True
        return memory
    if reading.kind == "not_known" and step:
        _defer(memory, [step.key])
    elif reading.kind == "stop":
        outcome["stop"] = True
    elif reading.kind == "delegate":
        outcome["delegate"] = True
    writes: list[FieldWrite] = []
    if reading.kind == "value" and step:
        writes += _value_writes(ctx, memory, step, reading.value)
    if reading.kind == "correction" and reading.correction:
        writes += _correction_writes(ctx, reading.correction)
    if reading.fields:
        procedure = account_service.read_procedure(ctx.db, ctx.account.user_id)
        current = resume_service.read_resume(ctx.db, ctx.account).data
        known = {p for p, _ in rules.form_fields(current)}
        for item in reading.fields:
            if item.path not in known:
                continue  # 스키마에 없는 경로는 버립니다(지어낸 칸 방지).
            plan = answer_writes((item.path,), item.value, ctx.today, procedure.separation_date)
            writes += plan.writes
            if plan.rejected:
                outcome.setdefault("rejected", []).extend(plan.rejected)
    if reading.facts:
        procedure = account_service.read_procedure(ctx.db, ctx.account.user_id)
        current = resume_service.read_resume(ctx.db, ctx.account).data
        plan = plan_writes(current, reading.facts, ctx.today, procedure.separation_date)
        writes += plan.writes
        if plan.asks:
            outcome["clarify"] = " / ".join([*filter(None, [outcome.get("clarify")]), *plan.asks])
    if reading.note and not writes:
        outcome["clarify"] = reading.note
    _save(ctx, memory, writes)
    if reading.kind in ("value", "not_known", "stop", "delegate", "correction"):
        memory["pending"] = None
        memory["follow"] = None  # 이어 묻던 질문에 답했으니 진행표로 돌아갑니다.
    return memory


def _value_writes(
    ctx: ToolContext, memory: ResumeMemory, step: ResumeStep, value: Any
) -> list[FieldWrite]:
    """대기 칸의 값을 칸 쓰기로(rules/resume/facts.answer_writes). 되묻기·거절은 outcome에."""
    procedure = account_service.read_procedure(ctx.db, ctx.account.user_id)
    plan = answer_writes(step.paths, value, ctx.today, procedure.separation_date)
    outcome = memory["outcome"]
    if plan.asks:
        outcome["clarify"] = " / ".join(plan.asks)
    if plan.rejected:
        outcome.setdefault("rejected", []).extend(plan.rejected)
    return plan.writes


def _correction_writes(ctx: ToolContext, correction: Correction) -> list[FieldWrite]:
    data = resume_service.read_resume(ctx.db, ctx.account).data
    known = {path for path, _ in rules.form_fields(data)}
    return [said(correction.path, correction.value)] if correction.path in known else []


def after_read(state: AgentState) -> str:
    return "attach_knowledge" if memory_of(state)["outcome"].get("off_topic") else "speak"


# ── 말하기 (모델 ③) ─────────────────────────────────────


def _speak_input(state: AgentState, memory: ResumeMemory, step: ResumeStep | None) -> str:
    facts = dict(state.get("facts", {}))
    briefing = "\n".join(f"- {line}" for line in facts.pop("briefing", []))
    plan = facts.get("resume_plan", {})
    next_view = step_view(step) if step else None
    if next_view and memory["outcome"].get("delegate"):
        next_view["bundle"] = [v for v in plan.get("steps", []) if v.get("proposal")]
    # 진행(5개 중 n개)은 바뀐 턴에만 넘겨 매 턴 되풀이하지 않게 합니다.
    progress = plan.get("progress")
    payload = {
        "outcome": memory["outcome"],
        "progress": progress if progress != memory.get("told_progress") else None,
        "next": next_view,
        "user_said": _last_user_text(state),
    }
    memory["told_progress"] = progress
    return (
        f"## 지금 상황\n{briefing}\n\n## 이번 턴 결과와 다음 칸\n"
        f"{json.dumps(payload, ensure_ascii=False, default=str)}"
    )


def speak(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """확인 문장을 스트리밍하고, 다음 질문 카드는 진행표 템플릿으로 냅니다."""
    memory = memory_of(state)
    ctx = tool_context_of(config)
    if ctx is None:
        return {"resume": memory}
    step = first_step(ctx, {**state, "resume": memory})
    if memory["outcome"].get("stop") and step and not step.required:
        step = None
    model = gateway.get_chat_model("agent")
    messages = [
        SystemMessage(load_prompt(SPEAK_PROMPT)),
        HumanMessage(_speak_input(state, memory, step)),
    ]
    sentences = SentenceStream()
    spoken: list[str] = []
    for chunk in model.stream(messages):
        spoken += _stream(sentences.feed(chunk.text))
    spoken += _stream(sentences.close())
    text = "".join(spoken).strip()
    out: list[Any] = [AIMessage(text)] if text else []
    if step is not None:
        # 질문 카드는 문장도 버튼도 코드(템플릿)가 정합니다.
        # (모델이 묻게 하면 다른 칸을 묻거나 범위를 바꿔 버튼과 어긋나기 때문)
        if card := rules.question_text(step):
            memory = _ask(memory, step, card)
            out.append(AIMessage(card))
    else:
        memory["pending"] = None
    return {"messages": out, "resume": memory, "model_calls": state.get("model_calls", 0) + 1}


def _stream(pieces: list[str]) -> list[str]:
    for piece in pieces:
        emit(TokenEvent(text=piece))
    return pieces


def _ask(memory: ResumeMemory, step: ResumeStep, text: str) -> ResumeMemory:
    kind = step.import_kind
    emit(
        AskUserEvent(
            question_id=step.key,
            text=text,
            choices=list(step.choices),
            import_kind=kind.value if kind else None,
            accepts_file=step.accepts_file,
        )
    )
    memory["asked"][step.key] = memory["asked"].get(step.key, 0) + 1
    memory["pending"] = step.to_pending(text)
    return memory
