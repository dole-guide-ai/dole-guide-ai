from pathlib import Path

from app.agent.input import images
from app.agent.input.pii import mask
from app.agent.schemas import AgentState
from app.core.config import get_settings

TRANSCRIPT_HEADER = "[사진에서 읽은 글]"


def read_images(state: AgentState) -> AgentState:
    """첨부 사진을 IMAGE_MODE에 따라 처리합니다.

    transcribe면 사진 글자를 받아써 가린 뒤 사용자 말 뒤에 붙이고 사진은 비웁니다.
    vision이면 사진을 그대로 두어 respond가 모델에 붙입니다. off면 사진을 무시합니다.
    """
    mode = get_settings().image_mode
    # 모르는 형식(사진이 아닌 파일)은 어느 방식이든 모델에 보내지 않습니다.
    paths = [p for p in state.get("images") or [] if images.image_mime(Path(p).read_bytes())]
    skipped = len(paths) != len(state.get("images") or [])
    if not paths or mode == "vision":
        return {"images": paths} if skipped else {}
    if mode == "off":
        return {"images": []}
    texts = [mask(images.transcribe(path))[0] for path in paths]
    message = "\n\n".join([state["message"], TRANSCRIPT_HEADER, *texts])
    return {"message": message, "images": []}
