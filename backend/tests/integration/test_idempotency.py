import pytest
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.errors import ConflictError
from app.services.idempotency import run_once

pytestmark = pytest.mark.integration


class Created(BaseModel):
    n: int


def test_same_key_replays_first_result(db_session: Session, entered_account) -> None:
    account = entered_account("park")
    calls = []

    def create() -> Created:
        calls.append(1)
        return Created(n=len(calls))

    first = run_once(db_session, account.user_id, "k1", {"a": 1}, Created, create)
    again = run_once(db_session, account.user_id, "k1", {"a": 1}, Created, create)

    assert first == again == Created(n=1)
    assert len(calls) == 1


def test_same_key_different_body_is_conflict(db_session: Session, entered_account) -> None:
    account = entered_account("park")
    run_once(db_session, account.user_id, "k1", {"a": 1}, Created, lambda: Created(n=1))

    with pytest.raises(ConflictError) as exc:
        run_once(db_session, account.user_id, "k1", {"a": 2}, Created, lambda: Created(n=2))
    assert exc.value.code == "IDEMPOTENCY_MISMATCH"


def test_no_key_runs_every_time(db_session: Session, entered_account) -> None:
    account = entered_account("park")
    results = [
        run_once(db_session, account.user_id, None, {}, Created, lambda i=i: Created(n=i))
        for i in range(2)
    ]

    assert [r.n for r in results] == [0, 1]


def test_entered_headers_fixture(client, entered_headers) -> None:
    res = client.get("/accounts/lee/rounds", headers=entered_headers("lee"))

    assert res.status_code == 200
