"""만료된 방문자 데이터를 정리하는 서비스입니다.

마지막 접속 후 7일이 지난 방문자를 지우면 계정과 모든 데이터가 함께 지워지고, 업로드 폴더도
지웁니다.
24시간 지난 멱등성 키도 함께 지웁니다. 다른 프로세스가 이미 돌고 있으면 건너뜁니다.
"""

import logging
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.repositories import maintenance as repo

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CleanupResult:
    ran: bool
    visitors: int = 0
    idempotency_keys: int = 0


def run_cleanup(db: Session, now: datetime) -> CleanupResult:
    """다른 프로세스가 이미 돌고 있으면 건너뜁니다(advisory lock)."""
    if not repo.try_lock(db):
        return CleanupResult(ran=False)
    user_ids = repo.expired_user_ids(db, now)
    visitors = repo.delete_expired_visitors(db, now)
    keys = repo.delete_old_idempotency_keys(db, now - timedelta(hours=24))
    db.commit()
    upload_root = Path(get_settings().upload_dir)
    for user_id in user_ids:
        shutil.rmtree(upload_root / str(user_id), ignore_errors=True)
    logger.info("cleanup visitors=%d idempotency_keys=%d", visitors, keys)
    return CleanupResult(ran=True, visitors=visitors, idempotency_keys=keys)
