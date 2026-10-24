"""사진 입력 처리 (설계 초안 결정 ⑥, 실험 C).

- vision: 답하는 모델에 사진을 그대로 붙입니다(`as_image_part`).
- transcribe: 사진 속 글자만 받아쓰게 한 뒤(`transcribe`), 팀 공용 pii.mask로 가려 글로 넘깁니다.

어느 방식이든 사진은 외부 모델로 나갑니다. 사진 속 개인정보까지 밖으로 보내지 않으려면
로컬 OCR이 필요합니다(이 파일의 다음 후보).
"""

import base64
import mimetypes
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from app.agent import gateway
from app.agent.prompts import load_prompt

TRANSCRIBE_REQUEST = "사진 속 글자를 보이는 그대로 옮겨 적어 주세요."


def as_image_part(path: str) -> dict:
    """LangChain 메시지에 넣는 이미지 조각(data URL)."""
    mime = mimetypes.guess_type(path)[0] or "image/png"
    data = base64.b64encode(Path(path).read_bytes()).decode("ascii")
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}}


def transcribe(path: str) -> str:
    """사진 속 글자를 받아씁니다(추출 역할 모델). 가리기는 부르는 쪽이 합니다."""
    model = gateway.get_chat_model("extract")
    response = model.invoke([
        SystemMessage(load_prompt("turn/transcribe_image")),
        HumanMessage([{"type": "text", "text": TRANSCRIBE_REQUEST}, as_image_part(path)]),
    ])  # fmt: skip
    return str(response.content).strip()
