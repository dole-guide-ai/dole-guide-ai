import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.errors import NotFoundError, register_exception_handlers
from app.core.request_id import RequestIdMiddleware


class ItemCreate(BaseModel):
    title: str
    count: int


def build_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)
    app.add_middleware(RequestIdMiddleware)
    router = APIRouter()

    @router.get("/items/missing")
    def missing() -> None:
        raise NotFoundError("항목을 찾을 수 없어요.")

    @router.post("/items")
    def create(item: ItemCreate) -> ItemCreate:
        return item

    @router.get("/boom")
    def boom() -> None:
        raise RuntimeError("synthetic internal detail")

    app.include_router(router)
    return app


@pytest.fixture
def error_client() -> TestClient:
    return TestClient(build_app(), raise_server_exceptions=False)


def test_app_error_uses_common_format(error_client: TestClient) -> None:
    res = error_client.get("/items/missing")

    assert res.status_code == 404
    assert res.json() == {"code": "NOT_FOUND", "message": "항목을 찾을 수 없어요.", "details": None}


def test_validation_error_hides_input_values(error_client: TestClient) -> None:
    res = error_client.post("/items", json={"title": "synthetic-secret", "count": "x"})

    body = res.json()
    assert res.status_code == 422
    assert body["code"] == "VALIDATION_ERROR"
    assert body["details"] == [{"field": "count", "type": "int_parsing"}]
    assert "synthetic-secret" not in res.text


def test_unknown_route_maps_to_not_found(error_client: TestClient) -> None:
    res = error_client.get("/nope")

    assert res.status_code == 404
    assert res.json()["code"] == "NOT_FOUND"


def test_unexpected_error_hides_internal_detail(error_client: TestClient) -> None:
    res = error_client.get("/boom")

    assert res.status_code == 500
    assert res.json()["code"] == "INTERNAL_ERROR"
    assert "synthetic internal detail" not in res.text


def test_request_id_is_added_and_valid_incoming_id_is_kept(error_client: TestClient) -> None:
    assert len(error_client.get("/nope").headers["X-Request-ID"]) == 32

    kept = error_client.get("/nope", headers={"X-Request-ID": "abc12345-req"})
    assert kept.headers["X-Request-ID"] == "abc12345-req"

    replaced = error_client.get("/nope", headers={"X-Request-ID": "bad id\nINJECT"})
    assert replaced.headers["X-Request-ID"] != "bad id\nINJECT"
