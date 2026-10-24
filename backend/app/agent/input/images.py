"""사진 입력 처리 (설계 초안 결정 ⑥, 실험 C).

- vision: 답하는 모델에 사진을 그대로 붙입니다(`as_image_part`).
- transcribe: 사진 속 글자만 받아쓰게 한 뒤(`transcribe`), 팀 공용 pii.mask로 가려 글로 넘깁니다.

어느 방식이든 사진은 외부 모델로 나갑니다. 사진 속 개인정보까지 밖으로 보내지 않으려면
로컬 OCR이 필요합니다(이 파일의 다음 후보).
"""

import base64
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from app.agent import gateway
from app.agent.prompts import load_prompt

TRANSCRIBE_REQUEST = "사진 속 글자를 보이는 그대로 옮겨 적어 주세요."
# 파일 첫 바이트 → 형식 (WEBP는 RIFF 컨테이너라 따로 봅니다)
IMAGE_SIGNATURES = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)


def image_mime(raw: bytes) -> str | None:
    """파일 앞부분(시그니처)으로 본 이미지 형식. 모르는 형식이면 None."""
    for signature, mime in IMAGE_SIGNATURES:
        if raw.startswith(signature):
            return mime
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "image/webp"
    return None


def as_image_part(path: str) -> dict:
    """LangChain 메시지에 넣는 이미지 조각(data URL).

    형식은 확장자가 아니라 파일 내용으로 정합니다. 모르는 형식은 다른 형식으로 꾸며 보내지 않고
    거절합니다.
    """
    raw = Path(path).read_bytes()
    if (mime := image_mime(raw)) is None:
        raise ValueError("지원하지 않는 사진 형식입니다.")
    data = base64.b64encode(raw).decode("ascii")
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}}


def transcribe(path: str) -> str:
    """사진 속 글자를 받아씁니다(추출 역할 모델). 가리기는 부르는 쪽이 합니다."""
    model = gateway.get_chat_model("extract")
    response = model.invoke([
        SystemMessage(load_prompt("turn/transcribe_image")),
        HumanMessage([{"type": "text", "text": TRANSCRIBE_REQUEST}, as_image_part(path)]),
    ])  # fmt: skip
    return str(response.content).strip()
