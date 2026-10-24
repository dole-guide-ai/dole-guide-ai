"""만료된 방문자 데이터를 지우는 정리 작업을 실행."""

import asyncio
import logging

from app.core.clock import now_kst
from app.core.db import SessionLocal
from app.services.maintenance import CleanupResult, run_cleanup

logger = logging.getLogger(__name__)
INTERVAL_SECONDS = 24 * 60 * 60
FIRST_DELAY_SECONDS = 10 * 60


def run_once() -> CleanupResult:
    with SessionLocal() as db:
        return run_cleanup(db, now_kst())


async def run_forever() -> None:
    await asyncio.sleep(FIRST_DELAY_SECONDS)
    while True:
        try:
            await asyncio.to_thread(run_once)
        except Exception as exc:  # noqa: BLE001 - 정리 실패가 서버를 멈추면 안 됩니다
            logger.error("cleanup failed type=%s", type(exc).__name__)
        await asyncio.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    print(run_once())
