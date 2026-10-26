"""말하기 버튼의 녹음을 글로 바꾸는 서비스입니다.

녹음은 메모리에서만 다루고 디스크·DB·로그에 남기지 않습니다(음성 원본은 판독 후 지움).
받아쓴 글은 바로 대화로 보내지 않고 화면이 입력창에 넣어 사용자가 확인한 뒤 보냅니다.
보낼 때 다른 글과 똑같이 preprocess가 개인정보를 검사합니다.
"""

from typing import BinaryIO

from app.agent import gateway
from app.core.config import get_settings
from app.core.errors import PayloadTooLargeError, UnsupportedMediaError
from app.schemas.transcriptions import TranscriptionRead

BYTES_PER_MB = 1024 * 1024
# 브라우저 녹음 형식의 파일 첫 바이트. 크롬·엣지는 webm, 사파리는 mp4(m4a)로 녹음합니다.
AUDIO_SIGNATURES = (
    (b"\x1a\x45\xdf\xa3", "webm"),
    (b"OggS", "ogg"),
    (b"ID3", "mp3"),
    (b"\xff\xfb", "mp3"),
    (b"\xff\xf3", "mp3"),
)


def audio_format(content: bytes) -> str | None:
    """파일 내용으로 본 녹음 형식(확장자). 모르는 형식이면 None."""
    for signature, extension in AUDIO_SIGNATURES:
        if content.startswith(signature):
            return extension
    if content[4:8] == b"ftyp":
        return "m4a"
    if content[:4] == b"RIFF" and content[8:12] == b"WAVE":
        return "wav"
    return None


def transcribe(stream: BinaryIO) -> TranscriptionRead:
    limit = get_settings().max_upload_mb * BYTES_PER_MB
    content = stream.read(limit + 1)
    if len(content) > limit:
        raise PayloadTooLargeError()
    if (extension := audio_format(content)) is None:
        raise UnsupportedMediaError()
    return TranscriptionRead(text=gateway.transcribe_audio(content, f"voice.{extension}"))
