from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.db import get_db
from app.models import Visitor

pytestmark = pytest.mark.integration


def test_uncommitted_writes_roll_back_when_request_fails(migrated_db: None) -> None:
    """서비스가 commit 전에 예외를 던지면 요청 세션이 닫히면서 쓰기가 남지 않습니다(N-07)."""
    now = datetime.now(UTC)
    token_hash = "rollback-test-" + "0" * 50
    sessions = get_db()
    db = next(sessions)
    db.add(Visitor(token_hash=token_hash, last_seen_at=now, expires_at=now + timedelta(days=1)))
    db.flush()

    with pytest.raises(RuntimeError):
        sessions.throw(RuntimeError("synthetic failure after flush"))

    check = get_db()
    found = next(check).scalar(select(Visitor).where(Visitor.token_hash == token_hash))
    check.close()
    assert found is None
