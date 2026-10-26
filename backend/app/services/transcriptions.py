"""말하기 버튼의 녹음을 글로 바꾸는 서비스입니다.

녹음은 메모리에서만 다루고 디스크·DB·로그에 남기지 않습니다(음성 원본은 판독 후 지움).
받아쓴 글은 바로 대화로 보내지 않고 화면이 입력창에 넣어 사용자가 확인한 뒤 보냅니다.
보낼 때 다른 글과 똑같이 preprocess가 개인정보를 검사합니다.
"""

import re
import threading
import time
import uuid
from collections import defaultdict, deque
from typing import BinaryIO

from app.agent import gateway
from app.core.config import get_settings
from app.core.errors import PayloadTooLargeError, RateLimitedError, UnsupportedMediaError
from app.schemas.transcriptions import TranscriptionRead

BYTES_PER_MB = 1024 * 1024
_HANGUL = re.compile(r"[가-힣]")
# 한글·숫자·기호가 아닌 글자(라틴·가나·한자·키릴 등)
_OTHER_LETTERS = re.compile(r"[^\W\d_가-힣ㄱ-ㅎㅏ-ㅣ]")
WINDOW_SECONDS = 60.0


class _MinuteLimiter:
    """계정마다 최근 1분 호출 시각을 세는 메모리 제한기. 서버 한 대(운영 구성)에서만 정확합니다."""

    def __init__(self) -> None:
        self._calls: dict[uuid.UUID, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, user_id: uuid.UUID, limit: int, now: float) -> None:
        with self._lock:
            calls = self._calls[user_id]
            while calls and now - calls[0] >= WINDOW_SECONDS:
                calls.popleft()
            if len(calls) >= limit:
                raise RateLimitedError()
            calls.append(now)


_limiter = _MinuteLimiter()
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


def transcribe(user_id: uuid.UUID, stream: BinaryIO) -> TranscriptionRead:
    """녹음을 글로. 형식·크기에서 거절된 요청은 횟수에 넣지 않고, 모델을 부르기 전에 셉니다."""
    settings = get_settings()
    limit = settings.max_upload_mb * BYTES_PER_MB
    content = stream.read(limit + 1)
    if len(content) > limit:
        raise PayloadTooLargeError()
    if (extension := audio_format(content)) is None:
        raise UnsupportedMediaError()
    _limiter.check(user_id, settings.stt_rate_limit_per_minute, time.monotonic())
    text = gateway.transcribe_audio(content, f"voice.{extension}")
    return TranscriptionRead(text=text if heard_korean(text) else "")


def heard_korean(text: str) -> bool:
    """받아쓴 글이 한국어인지. 잡음이 많으면 모델이 다른 언어 문장을 지어내므로(평가 V-08·V-14),
    한글이 없고 다른 글자만 있으면 못 들은 것으로 봅니다(화면은 "잘 듣지 못했어요").
    숫자·기호만 있는 말("250만")은 그대로 둡니다."""
    return bool(_HANGUL.search(text)) or not _OTHER_LETTERS.search(text)
