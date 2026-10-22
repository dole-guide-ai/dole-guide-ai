"""로그 형식. 시각은 서버 시간대와 상관없이 한국 시간(+09:00)으로, 줄마다 요청 ID를 붙입니다.
로그에 이름·연락처·발화 원문 등 개인정보를 남기지 않습니다.
"""

import logging
from datetime import datetime

from app.core.clock import KST
from app.core.request_id import current_request_id

FORMAT = "%(asctime)s %(levelname)s [%(request_id)s] %(name)s %(message)s"


class KstFormatter(logging.Formatter):
    """시각을 `2026-10-22T17:00:00.123+09:00` 형태로 찍습니다."""

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:  # noqa: N802
        return datetime.fromtimestamp(record.created, KST).isoformat(timespec="milliseconds")


class RequestIdFilter(logging.Filter):
    """요청 밖(시작·정리 작업)에서 남긴 로그는 `-`로 표시합니다."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = current_request_id.get()
        return True


def setup_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(KstFormatter(FORMAT))
    handler.addFilter(RequestIdFilter())
    logging.basicConfig(level=level, handlers=[handler], force=True)
