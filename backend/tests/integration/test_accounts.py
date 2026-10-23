from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.clock import get_today
from app.main import app

pytestmark = pytest.mark.integration

TODAY = date(2026, 10, 21)


@pytest.fixture(autouse=True)
def fixed_today():
    app.dependency_overrides[get_today] = lambda: TODAY
    yield
    app.dependency_overrides.pop(get_today, None)


def new_visitor(client: TestClient) -> dict[str, str]:
    res = client.post("/visitors")
    assert res.status_code == 201
    return {"Authorization": f"Bearer {res.json()['visitor_token']}"}


def test_requires_visitor_token(client: TestClient) -> None:
    res = client.get("/personas")

    assert res.status_code == 401
    assert res.json()["code"] == "UNAUTHORIZED"


def test_persona_cards(client: TestClient) -> None:
    res = client.get("/personas", headers=new_visitor(client))

    assert res.status_code == 200
    assert [p["persona_id"] for p in res.json()["items"]] == ["park", "choi", "lee"]
    assert res.json()["items"][0]["progress_summary"] is None


def test_enter_creates_then_resumes(client: TestClient) -> None:
    headers = new_visitor(client)

    first = client.put("/accounts/park", headers=headers)
    again = client.put("/accounts/park", headers=headers)

    assert first.status_code == 201
    assert first.headers["Location"] == "/accounts/park"
    assert again.status_code == 200
    body = first.json()
    assert body["entry"]["branch_id"] == "E7a"
    assert body["procedure"]["recipient_group"] == "age_60_64"
    assert body["procedure"]["separation_date"] == str(TODAY - timedelta(days=21))


def test_lee_is_in_round_four_with_relative_dates(client: TestClient) -> None:
    headers = new_visitor(client)

    body = client.put("/accounts/lee", headers=headers).json()

    assert body["entry"]["branch_id"] == "E4b"
    assert body["current_round"]["round"] == 4
    assert body["current_round"]["attendance_required"] is True
    assert body["procedure"]["benefit_days"] == 270
    rounds = client.get("/accounts/lee/rounds", headers=headers).json()["items"]
    assert [r["application_status"] for r in rounds[:4]] == [
        "submitted",
        "submitted",
        "submitted",
        "draft",
    ]
    assert [r["status"] for r in rounds[:4]] == ["closed", "closed", "closed", "current"]


def test_choi_old_resume_is_outdated(client: TestClient) -> None:
    body = client.put("/accounts/choi", headers=new_visitor(client)).json()

    assert body["entry"]["branch_id"] == "E7b"
    assert body["entry"]["ui"]["big_text"] is True


def test_other_visitor_cannot_see_account(client: TestClient) -> None:
    owner = new_visitor(client)
    client.put("/accounts/lee", headers=owner)

    res = client.get("/accounts/lee", headers=new_visitor(client))

    assert res.status_code == 404
    assert res.json()["code"] == "ACCOUNT_NOT_FOUND"


def test_unknown_persona_is_404(client: TestClient) -> None:
    res = client.put("/accounts/nobody", headers=new_visitor(client))

    assert res.status_code == 404
    assert res.json()["code"] == "PERSONA_NOT_FOUND"


def test_delete_then_enter_recreates(client: TestClient) -> None:
    headers = new_visitor(client)
    client.put("/accounts/park", headers=headers)

    assert client.delete("/accounts/park", headers=headers).status_code == 204
    assert client.get("/accounts/park", headers=headers).status_code == 404
    assert client.put("/accounts/park", headers=headers).status_code == 201


def test_progress_summary_after_enter(client: TestClient) -> None:
    headers = new_visitor(client)
    client.put("/accounts/lee", headers=headers)

    cards = client.get("/personas", headers=headers).json()["items"]

    assert {c["persona_id"]: c["progress_summary"] for c in cards}["lee"] == "실업인정 중"


def test_skeleton_endpoint_is_501_after_auth(client: TestClient) -> None:
    headers = new_visitor(client)
    client.put("/accounts/park", headers=headers)

    assert client.get("/accounts/park/trainings").status_code == 401
    res = client.get("/accounts/park/trainings", headers=headers)
    assert res.status_code == 501
    assert res.json()["code"] == "NOT_IMPLEMENTED"
