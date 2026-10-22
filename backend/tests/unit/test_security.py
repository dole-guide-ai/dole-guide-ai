from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.crypto import decrypt, encrypt, last4
from app.core.security import InternalSecretMiddleware, hash_token, new_visitor_token


def build_client(secret: str) -> TestClient:
    app = FastAPI()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/personas")
    def personas() -> list[str]:
        return []

    app.add_middleware(InternalSecretMiddleware, secret=secret)
    return TestClient(app)


def test_missing_secret_is_401() -> None:
    res = build_client("synthetic-secret").get("/personas")

    assert res.status_code == 401
    assert res.json()["code"] == "INTERNAL_AUTH_FAILED"


def test_correct_secret_passes() -> None:
    res = build_client("synthetic-secret").get(
        "/personas", headers={"X-Internal-Secret": "synthetic-secret"}
    )

    assert res.status_code == 200


def test_health_is_open() -> None:
    assert build_client("synthetic-secret").get("/health").status_code == 200


def test_empty_secret_disables_check() -> None:
    assert build_client("").get("/personas").status_code == 200


def test_token_hash_is_stable_and_not_the_token() -> None:
    token = new_visitor_token()

    assert hash_token(token) == hash_token(token)
    assert hash_token(token) != token
    assert len(token) >= 40


def test_account_round_trip_and_last4() -> None:
    sealed = encrypt("000-1234-5678")

    assert b"5678" not in sealed
    assert decrypt(sealed) == "000-1234-5678"
    assert last4("000-1234-5678") == "5678"
