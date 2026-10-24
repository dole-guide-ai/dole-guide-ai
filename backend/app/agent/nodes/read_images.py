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
    paths = state.get("images") or []
    mode = get_settings().image_mode
    if not paths or mode == "vision":
        return {}
    if mode == "off":
        return {"images": []}
    texts = [mask(images.transcribe(path))[0] for path in paths]
    message = "\n\n".join([state["message"], TRANSCRIPT_HEADER, *texts])
    return {"message": message, "images": []}
