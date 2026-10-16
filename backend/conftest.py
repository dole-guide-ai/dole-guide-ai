"""tests/와 evals/가 함께 쓰는 공용 픽스처입니다."""

import os
from collections.abc import Iterator

import pytest
from sqlalchemy.engine import make_url

# 앱(엔진)을 import하기 전에 테스트 DB로 바꿉니다. 개발 DB를 건드리지 않습니다.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://dole:dole@localhost:5432/dole_test"
)
if not (make_url(TEST_DATABASE_URL).database or "").endswith("_test"):
    raise RuntimeError("TEST_DATABASE_URL의 DB 이름은 _test로 끝나야 합니다. (예: dole_test)")
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from langchain_core.language_models.fake_chat_models import FakeListChatModel  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from alembic import command  # noqa: E402
from app.agent import gateway  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.db import engine, get_db  # noqa: E402
from app.main import app  # noqa: E402

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))


def _ensure_test_database() -> None:
    url = make_url(TEST_DATABASE_URL)
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": url.database}
        )
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin.dispose()


@pytest.fixture(scope="session")
def migrated_db() -> None:
    """테스트 DB를 만들고 최신 마이그레이션을 적용합니다. (integration 테스트 전용)"""
    get_settings.cache_clear()
    try:
        _ensure_test_database()
    except OperationalError:
        pytest.skip("Postgres에 연결할 수 없습니다. `docker compose up -d db`를 먼저 실행하세요.")
    cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "alembic"))
    command.upgrade(cfg, "head")


@pytest.fixture
def db_session(migrated_db: None) -> Iterator[Session]:
    """테스트마다 트랜잭션을 열고 끝나면 롤백합니다.

    서비스 코드의 commit은 savepoint로 처리되어 테스트 간 데이터가 남지 않습니다.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def fake_llm(monkeypatch: pytest.MonkeyPatch):
    """실제 LLM 대신 정해진 응답을 순서대로 돌려주는 모델을 주입합니다.

    사용: fake_llm(["첫 응답", "두 번째 응답"])
    에이전트 코드는 `gateway.get_chat_model()`처럼 모듈을 통해 호출해야 대체됩니다.
    """

    def _install(responses: list[str]) -> FakeListChatModel:
        model = FakeListChatModel(responses=responses)
        monkeypatch.setattr(gateway, "get_chat_model", lambda role="agent": model)
        return model

    return _install
