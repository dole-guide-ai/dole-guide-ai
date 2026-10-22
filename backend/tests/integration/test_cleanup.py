from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import now_kst
from app.models import User, Visitor
from app.services.maintenance import run_cleanup

pytestmark = pytest.mark.integration


def test_cleanup_removes_expired_visitors(client: TestClient, db_session: Session) -> None:
    token = client.post("/visitors").json()["visitor_token"]
    client.put("/accounts/park", headers={"Authorization": f"Bearer {token}"})

    result = run_cleanup(db_session, now_kst() + timedelta(days=8))

    assert result.ran
    assert result.visitors >= 1
    assert db_session.scalar(select(User)) is None
    assert db_session.scalar(select(Visitor)) is None


def test_cleanup_keeps_active_visitors(client: TestClient, db_session: Session) -> None:
    client.post("/visitors")

    run_cleanup(db_session, now_kst())

    assert db_session.scalar(select(Visitor)) is not None
