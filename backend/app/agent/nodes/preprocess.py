"""사용자 말을 모델·체크포인트에 넣기 전에 개인정보를 검사합니다 (노션 AI 설계 5.3, pii.py).

- 0등급(주민등록번호·카드·계좌)이 있으면 모델에 보내지 않고 안내 문장으로 끝냅니다.
- 1등급(전화·이메일)은 [전화]·[이메일]로 바꿔서 넣습니다.
상태에는 가린 글만 남습니다. 원문은 턴 정보(config)에만 있고 체크포인트에 저장되지 않습니다.

첨부 문서(pdf·docx·hwpx)는 글자를 뽑고, IMAGE_MODE=transcribe면 사진도 받아써서 가린 뒤
사용자 말 뒤에 붙입니다. vision 모드의 사진은 call_model이 모델 입력에만 붙입니다(panel.py).
"""

from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

from app.agent.events import emit
from app.agent.graph import AgentState, tool_context_of, turn_of
from app.agent.input import documents, images, pii
from app.core.config import get_settings
from app.schemas.messages import TokenEvent
from app.services import files as files_service

BLOCKED_REPLY = (
    "주민등록번호·계좌번호·카드번호 같은 민감한 번호는 저장하지 않아요. "
    "그래서 이번 말은 보내지 않았어요. 번호는 빼고 다시 말씀해 주세요."
)
BLOCKED_PLACEHOLDER = "(민감한 번호가 있어 보내지 않은 말)"
UNFINISHED_TOOL = "(답을 받기 전에 대화가 끊겨 끝나지 않은 호출)"


def gate(text: str) -> tuple[str, bool]:
    """(모델·상태에 넣을 글, 막았는지). 재개(interrupt 답)도 같은 검사를 거칩니다."""
    if pii.has_blocking(text):
        return BLOCKED_PLACEHOLDER, True
    masked, _ = pii.mask(text)
    return masked, False


def close_dangling_tool_calls(messages: list[AnyMessage]) -> list[ToolMessage]:
    """결과가 없는 도구 호출에 결과를 채웁니다.

    질문 이벤트가 나간 직후 스트림이 끊기면 도구 호출만 저장되고 결과가 빠집니다.
    그대로 두면 다음 호출을 공급자가 거절합니다(OpenAI 400: No tool output found).
    """
    answered = {m.tool_call_id for m in messages if isinstance(m, ToolMessage)}
    return [
        ToolMessage(content=UNFINISHED_TOOL, tool_call_id=call["id"])
        for m in messages
        if isinstance(m, AIMessage)
        for call in m.tool_calls
        if call["id"] not in answered
    ]


DOCUMENT_HEADER = "[올린 파일에서 읽은 글]"
UNREADABLE_DOCUMENT = "(글자를 읽지 못한 파일. 사진으로 찍어 다시 올려 달라고 안내할 것)"


def _read_attachment(path: Path) -> str | None:
    """첨부 하나의 글(가리기 전). 사진을 모델에 그대로 보내는 경우(vision·off)는 None."""
    if images.image_mime(path.read_bytes()) is not None:
        if get_settings().image_mode != "transcribe":
            return None
        return images.transcribe(str(path))
    return documents.extract_text(str(path)) or UNREADABLE_DOCUMENT


def attachment_text(config: RunnableConfig) -> str:
    """이번 턴 첨부에서 읽은 글. 열 수 없는 파일은 건너뜁니다."""
    ctx = tool_context_of(config)
    if ctx is None:
        return ""
    texts = []
    for file_id in getattr(turn_of(config), "file_ids", None) or []:
        path = files_service.open_attachment(ctx.db, ctx.account, file_id)
        if path is not None and (text := _read_attachment(path)):
            texts.append(text)
    return "\n\n".join(texts)


def preprocess(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    text, blocked = gate(turn_of(config).text)
    if blocked:
        emit(TokenEvent(text=BLOCKED_REPLY))
    elif attached := attachment_text(config):
        masked, _ = pii.mask(attached)
        text = f"{text}\n\n{DOCUMENT_HEADER}\n{masked}"
    repairs = close_dangling_tool_calls(state.get("messages", []))
    return {
        "messages": [*repairs, HumanMessage(text)],
        "blocked": blocked,
        "panel": None,
        "model_calls": 0,
        "tool_calls": 0,
        "cited": [],
        "attached": [],
    }


def after_preprocess(state: AgentState) -> str:
    return "finish" if state.get("blocked") else "load_context"
