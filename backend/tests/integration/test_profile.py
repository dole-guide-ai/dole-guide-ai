import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.clock import now_kst
from app.services.accounts import find_account
from app.services.profile import read_profile_display
from app.services.visitors import authenticate

pytestmark = pytest.mark.integration


def test_profile_display_shows_last4_only(client: TestClient, db_session: Session) -> None:
    token = client.post("/visitors").json()["visitor_token"]
    client.put("/accounts/park", headers={"Authorization": f"Bearer {token}"})
    visitor = authenticate(db_session, token, now_kst())
    account = find_account(db_session, visitor.visitor_id, "park")

    profile = read_profile_display(db_session, account.user_id)

    assert profile is not None
    assert profile.name == "박진수"
    assert profile.account_last4 == "0001"
    assert "account_number" not in profile.model_dump()


def test_profile_display_is_none_for_unknown_user(db_session: Session) -> None:
    assert read_profile_display(db_session, uuid.uuid4()) is None
