"""사진 입력 처리 (설계 초안 결정 ⑥, 실험 C, #244).

사진은 먼저 받아써서(`transcribe`, 추출 모델) 가린 글을 대화 기록에 남깁니다(preprocess).
그래야 다음 턴에도 사진 내용을 쓸 수 있습니다. IMAGE_MODE=vision이면 받아쓴 글에
등급 0(주민번호·계좌·카드)이 없을 때만 답하는 모델에 사진도 붙입니다(`as_image_part`).
받아쓰기는 사진째 외부 모델로 나가므로, 사진 속 개인정보까지 막으려면 로컬 OCR이 필요합니다.

휴대폰 사진은 크기가 커서 긴 변을 줄인 JPEG로 한 번만 만들어 받아쓰기와 vision에 같이 씁니다.
"""

import base64
import io
from functools import lru_cache
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from PIL import Image, ImageOps

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
# 모델에 보낼 사진의 긴 변. 서류 글자를 읽기에 충분하고 요청 크기를 크게 줄입니다.
MAX_SIDE = 1600
JPEG_QUALITY = 85
# 같은 턴의 받아쓰기·모델 호출(최대 4번)이 같은 사진을 다시 줄이지 않게 몇 장만 기억합니다.
CACHED_IMAGES = 8


def image_mime(raw: bytes) -> str | None:
    """파일 앞부분(시그니처)으로 본 이미지 형식. 모르는 형식이면 None."""
    for signature, mime in IMAGE_SIGNATURES:
        if raw.startswith(signature):
            return mime
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "image/webp"
    return None


def is_image(path: str) -> bool:
    with Path(path).open("rb") as f:
        return image_mime(f.read(16)) is not None


@lru_cache(maxsize=CACHED_IMAGES)
def _data_url(path: str, mtime_ns: int) -> str:
    """사진을 돌리고(EXIF 방향) 긴 변을 줄인 JPEG data URL.

    mtime_ns는 캐시를 파일 변경에 묶습니다. 깨진 사진은 ValueError(읽을 수 없는 사진)입니다.
    """
    del mtime_ns
    try:
        with Image.open(path) as image:
            image = ImageOps.exif_transpose(image)
            image.thumbnail((MAX_SIDE, MAX_SIDE))
            buffer = io.BytesIO()
            image.convert("RGB").save(buffer, "JPEG", quality=JPEG_QUALITY)
    except (OSError, Image.DecompressionBombError) as error:
        raise ValueError("읽을 수 없는 사진입니다.") from error
    data = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{data}"


def as_image_part(path: str) -> dict:
    """LangChain 메시지에 넣는 이미지 조각(data URL).

    형식은 확장자가 아니라 파일 내용으로 정합니다. 사진이 아니면 보내지 않고 거절합니다.
    """
    if not is_image(path):
        raise ValueError("지원하지 않는 사진 형식입니다.")
    file = Path(path)
    return {
        "type": "image_url",
        "image_url": {"url": _data_url(str(file), file.stat().st_mtime_ns)},
    }


def image_parts(paths: list[str]) -> list[dict]:
    """vision 입력으로 보낼 이미지 조각들. 사진이 아닌 파일은 모델에 보내지 않고 뺍니다."""
    return [as_image_part(path) for path in paths if is_image(path)]


def transcribe(path: str) -> str:
    """사진 속 글자를 받아씁니다(추출 역할 모델). 가리기는 부르는 쪽이 합니다."""
    model = gateway.get_chat_model("extract")
    response = model.invoke([
        SystemMessage(load_prompt("turn/transcribe_image")),
        HumanMessage([{"type": "text", "text": TRANSCRIBE_REQUEST}, as_image_part(path)]),
    ])  # fmt: skip
    return str(response.content).strip()
