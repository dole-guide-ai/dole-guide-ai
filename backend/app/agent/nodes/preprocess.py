"""사용자 말을 모델·체크포인트에 넣기 전에 개인정보를 검사합니다 (노션 AI 설계 5.3, pii.py).

- 0등급(주민등록번호·카드·계좌)이 있으면 모델에 보내지 않고 안내 문장으로 끝냅니다.
- 1등급(전화·이메일)은 [전화]·[이메일]로 바꿔서 넣습니다.
상태에는 가린 글만 남습니다. 원문은 턴 정보(config)에만 있고 체크포인트에 저장되지 않습니다.

첨부 문서(pdf·docx·hwpx)는 글자를 뽑고, IMAGE_MODE=transcribe면 사진도 받아써서 가린 뒤
사용자 말 뒤에 붙입니다. vision 모드의 사진은 call_model이 모델 입력에만 붙입니다(panel.py).
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

from app.agent.events import emit
from app.agent.graph import AgentState, tool_context_of, turn_of
from app.agent.input import documents, images, pii
from app.core.config import get_settings
from app.schemas.messages import TokenEvent, ToolCallEvent
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


# 첨부에서 읽은 글은 사용자 말과 구분해 감쌉니다. 그 안의 지시는 따르지 않습니다(base.md).
ATTACHMENT_OPEN = "<첨부>"
ATTACHMENT_CLOSE = "</첨부>"
_ATTACHMENT_TAG = re.compile(r"</?\s*첨부\s*>")


def wrap_attachment(text: str) -> str:
    """첨부 글을 표시로 감쌉니다. 글 안의 표시는 지워 감싼 범위를 벗어나지 못하게 합니다."""
    return f"{ATTACHMENT_OPEN}\n{_ATTACHMENT_TAG.sub('', text)}\n{ATTACHMENT_CLOSE}"


UNREADABLE_DOCUMENT = "(글자를 읽지 못한 파일. 사진으로 찍어 다시 올려 달라고 안내할 것)"
UNREADABLE_PHOTO = "(글자를 읽지 못한 사진. 밝은 곳에서 다시 찍어 올려 달라고 안내할 것)"
# 판독 중 화면 진행 표시(tool_call 이벤트 이름, 프론트 TOOL_LABEL과 같음)
PARSE_FILE = "parse_file"


@dataclass
class Attachments:
    """이번 턴 첨부에서 읽은 글(가림)과 답하는 모델에 사진째 보낼 파일."""

    text: str = ""
    vision_files: list[str] = field(default_factory=list)


def _read_photo(path: Path) -> tuple[str, bool]:
    """사진을 받아써 가린 글과, 사진째 보내도 되는지(등급 0이 없고 vision 모드)."""
    try:
        transcript = images.transcribe(str(path))
    except Exception:  # 깨진 사진·모델 실패는 턴을 막지 않고 다시 찍어 달라고 합니다.
        return UNREADABLE_PHOTO, False
    if not transcript.strip():
        return UNREADABLE_PHOTO, False
    masked, findings = pii.mask(transcript)
    safe = not any(f.blocking for f in findings)
    return masked, safe and get_settings().image_mode == "vision"


def read_attachments(config: RunnableConfig) -> Attachments:
    """이번 턴 첨부를 읽습니다. 사진도 먼저 받아써 가린 글로 대화 기록에 남겨 다음 턴에도 씁니다.

    사진째 보내기(vision)는 받아쓴 글에 주민번호 같은 등급 0이 없을 때만 합니다. 글로 쓴 등급 0은
    보내지 않는데(gateway) 사진은 그 검사를 거치지 않기 때문입니다. 열 수 없는 파일은 건너뜁니다.
    """
    ctx = tool_context_of(config)
    file_ids = dict.fromkeys(getattr(turn_of(config), "file_ids", None) or [])
    result = Attachments()
    if ctx is None or not file_ids:
        return result
    emit(ToolCallEvent(name=PARSE_FILE, status="started"))
    texts = []
    for file_id in file_ids:
        path = files_service.open_attachment(ctx.db, ctx.account, file_id)
        if path is None:
            continue
        if not images.is_image(str(path)):
            texts.append(pii.mask(documents.extract_text(str(path)) or UNREADABLE_DOCUMENT)[0])
        elif get_settings().image_mode != "off":
            text, send_photo = _read_photo(path)
            texts.append(text)
            if send_photo:
                result.vision_files.append(file_id)
    emit(ToolCallEvent(name=PARSE_FILE, status="finished"))
    result.text = "\n\n".join(texts)
    return result


def preprocess(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    text, blocked = gate(turn_of(config).text)
    attachments = Attachments()
    if blocked:
        emit(TokenEvent(text=BLOCKED_REPLY))
    else:
        attachments = read_attachments(config)
        if attachments.text:
            text = f"{text}\n\n{wrap_attachment(attachments.text)}"
    repairs = close_dangling_tool_calls(state.get("messages", []))
    return {
        "messages": [*repairs, HumanMessage(text)],
        "blocked": blocked,
        "panel": None,
        "model_calls": 0,
        "tool_calls": 0,
        "cited": [],
        "attached": [],
        "vision_files": attachments.vision_files,
    }


def after_preprocess(state: AgentState) -> str:
    return "finish" if state.get("blocked") else "load_context"
