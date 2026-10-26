"""load_context 노드와 패널 라우터 (노션 「AI 설계」 2-1·2-2-1·2-3·2-3-1).

- 절차 단계와 직전 질문으로 패널(서브그래프)을 고릅니다. LLM이 고르지 않습니다.
- 다음 질문(question_id)과 쓸 수 있는 칸(allowed_paths)을 규칙 함수로 정합니다.
- LLM 없이 끝나는 고정 경로를 처리합니다: 전체 순서 안내, 인사·잡담, 다른 단계 서류 고치기,
  신청서 선택지 답, 이력서 확인 질문의 "네, 맞아요".
"""

import re
from typing import Any

from langchain_core.runnables import RunnableConfig
from pydantic import ValidationError

from app.agent import questions, replies
from app.agent.events import emit
from app.agent.graph_config import tool_context_of, turn_of
from app.agent.panels import RESUME_PATHS, Panel
from app.agent.state import AgentState, Question
from app.agent.tools.guide import OVERVIEW
from app.agent.tools.registry import ToolContext, ToolError, run_tool
from app.core.errors import AppError
from app.schemas.common import FormUpdate
from app.schemas.procedure import Stage
from app.services import accounts as account_service
from app.services import application as application_service
from app.services import resume as resume_service

OVERVIEW_CHOICE = "전체 순서가 궁금해요"
CONFIRM_CHOICE = "네, 맞아요"
VALUE_CONFIRM = "resume.value_confirm"
APPLICATION_PREFIX = "application."

_GREETING = re.compile(r"^\s*(안녕(하세요|하십니까)?|반가워요|처음 뵙겠습니다)[\s.!~]*$")
_THANKS = re.compile(r"^\s*(고마워요?|고맙습니다|감사(합니다|해요)|땡큐)[\s.!~]*$")
_SMALL_TALK = re.compile(r"(날씨|점심|저녁|주식|코인|로또|연예인|야구|축구|드라마|노래 불러)")
_EDUCATION = re.compile(r"(교육|훈련과정|훈련|강의|특강|집단상담|국비|배울|배우고)")
_APPLICATION = re.compile(r"(신청서|본인 답변|실업크레딧|근로|소득)")
_EDIT = re.compile(r"(고칠게요|고쳐|수정|바꿀게요|바꿔)")
_DOC_WORDS: dict[Panel, re.Pattern[str]] = {
    Panel.RESUME: re.compile(r"이력서"),
    Panel.APPLICATION: re.compile(r"신청서"),
    Panel.ROUND: re.compile(r"활동"),
}


def route_panel(stage: str, question: Question | None, text: str) -> Panel | None:
    """절차 단계와 직전 질문으로 서브그래프를 고릅니다. 맡는 서브그래프가 없으면 None."""
    if _EDUCATION.search(text):
        return Panel.EDUCATION
    if stage == Stage.JOB_REGISTRATION:
        return Panel.RESUME
    if stage == Stage.RECOGNITION:
        asked = (question or {}).get("id", "")
        if asked.startswith(APPLICATION_PREFIX) or _APPLICATION.search(text):
            return Panel.APPLICATION
        return Panel.ROUND
    # 교육 · 수급자격 · 종료 단계의 대화는 MVP 밖 (노션 2-2-1 알고 남겨 둔 빈 곳)
    return None


def _other_stage_edit(panel: Panel, text: str) -> bool:
    """지금 단계가 아닌 서류를 대화로 고치려는 말 (2-2-1: 안내만 하고 고치지 않음)."""
    if not _EDIT.search(text):
        return False
    return any(p != panel and word.search(text) for p, word in _DOC_WORDS.items())


def next_question(ctx: ToolContext, panel: Panel, doc_failed: bool = False) -> Question | None:
    """규칙 함수가 고른 다음 질문. 활동 기록 · 교육은 정해진 질문 순서가 없어 None."""
    if panel == Panel.RESUME:
        q = resume_service.next_question(ctx.db, ctx.account.user_id, doc_failed=doc_failed)
        return questions.resume_question(q) if q else None
    if panel == Panel.APPLICATION:
        q = application_service.next_answer_question(ctx.db, ctx.account, ctx.today)
        return questions.application_question(q) if q else None
    return None


def _allowed(panel: Panel, question: Question | None) -> tuple[str, ...]:
    if panel == Panel.RESUME:
        return RESUME_PATHS
    if panel == Panel.APPLICATION:
        path = (question or {}).get("path")
        return (path,) if path else ()
    return ()


def _fixed(text: str, **extra: Any) -> dict[str, Any]:
    return {"reply": text, "fixed": True, **extra}


def load_context(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    if state.get("fixed"):
        return {}
    turn = turn_of(config)
    ctx = tool_context_of(config)
    text = state.get("text", "")
    previous = state.get("question")

    if text.strip() == OVERVIEW_CHOICE:
        return _fixed(OVERVIEW)
    if _GREETING.match(text):
        return _fixed(replies.reply("greeting"))
    if _THANKS.match(text):
        return _fixed(replies.reply("thanks"))
    if _SMALL_TALK.search(text):
        return _fixed(replies.reply("small_talk"))
    if ctx is None:
        # 도구 문맥이 없는 실행(단위 테스트)은 판단할 서류가 없어 고정 답으로 끝냅니다.
        return _fixed(replies.reply("fallback"))

    stage = account_service.read_procedure(ctx.db, ctx.account.user_id).stage
    panel = route_panel(stage, previous, text)
    if panel is None:
        return _fixed(replies.reply("stage_not_supported"), panel=None, question=None)
    if _other_stage_edit(panel, text):
        return _fixed(replies.reply("other_stage_edit"), panel=panel)

    question = previous if previous and state.get("panel") == panel else None
    if question is None:
        question = next_question(ctx, panel, state.get("doc_failed", False))
    ctx.allowed_paths = _allowed(panel, question)
    ctx.defer_commit = True

    answered = _answer_choice(ctx, question, turn.text)
    if answered is not None:
        return answered | {"panel": panel}
    return {"panel": panel, "question": question}


def _answer_choice(ctx: ToolContext, question: Question | None, text: str) -> dict[str, Any] | None:
    """선택지 글자 그대로의 답은 LLM 없이 저장합니다 (2-3 고정 경로)."""
    if not question:
        return None
    choice = text.strip()
    try:
        if choice in question.get("values", {}) and question.get("path"):
            result = run_tool(
                ctx,
                "record_user_answer",
                {"path": question["path"], "value": question["values"][choice]},
            )
            _emit_updates(result)
            return _fixed(replies.reply("recorded_answer"))
        if (
            question.get("id") == VALUE_CONFIRM
            and choice == CONFIRM_CHOICE
            and question.get("path")
        ):
            result = run_tool(ctx, "confirm_resume_field", {"path": question["path"]})
            _emit_updates(result)
            return _fixed(replies.reply("confirmed"))
    except ToolError, ValidationError, AppError:
        return None  # 고정 경로가 안 되면 LLM 서브그래프가 처리합니다
    return None


def _emit_updates(result: dict[str, Any]) -> None:
    for update in result.get("updates", []):
        emit(FormUpdate.model_validate(update))
