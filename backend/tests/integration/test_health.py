import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def test_get_health(client: TestClient) -> None:
    res = client.get("/health")

    assert res.status_code == 200
    assert res.json() == {"status": "ok", "db": "ok"}
