import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


@pytest.fixture
def headers(client: TestClient) -> dict[str, str]:
    token = client.post("/visitors").json()["visitor_token"]
    return {"Authorization": f"Bearer {token}"}


def test_regions_list_all(client: TestClient, headers: dict[str, str]) -> None:
    res = client.get("/codes/regions", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == len(body["items"]) > 200
    assert {"code": "41550", "name": "경기 안성시", "parent": "41000", "depth": 2} in body["items"]


def test_occupation_search(client: TestClient, headers: dict[str, str]) -> None:
    res = client.get("/codes/occupations", params={"q": "지게차", "limit": 1}, headers=headers)
    assert res.status_code == 200
    assert res.json()["items"] == [
        {"code": "623004", "name": "지게차 운전원", "parent": "07B", "depth": 3}
    ]


def test_codes_need_visitor_token(client: TestClient) -> None:
    res = client.get("/codes/regions")
    assert res.status_code == 401
    assert res.json()["code"] == "UNAUTHORIZED"
