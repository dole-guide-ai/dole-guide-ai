"""tests/와 evals/가 함께 쓰는 공용 픽스처입니다."""

import os
from collections.abc import Callable, Iterator
from datetime import date, datetime, time

import pytest
from sqlalchemy.engine import make_url

# 앱(엔진)을 import하기 전에 테스트 DB로 바꿉니다. 개발 DB를 건드리지 않습니다.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://dole:dole@localhost:5432/dole_test"
)
if not (make_url(TEST_DATABASE_URL).database or "").endswith("_test"):
    raise RuntimeError("TEST_DATABASE_URL의 DB 이름은 _test로 끝나야 합니다. (예: dole_test)")
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
# 테스트가 .env의 LangSmith 설정으로 트레이스를 보내지 않게 끕니다.
# 실제 모델 평가는 evals/conftest.py가 .env 값으로 되돌립니다.
os.environ["LANGSMITH_TRACING"] = "false"
# 테스트는 고용24 OpenAPI를 실제로 부르지 않습니다. 인증키를 비워 늘 스냅샷을 씁니다.
for _key in ("WORK24_CODE_API_KEY", "WORK24_TRAINING_API_KEY", "WORK24_PROGRAM_API_KEY"):
    os.environ[_key] = ""

from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from langchain_core.language_models import BaseChatModel  # noqa: E402
from langchain_core.language_models.fake_chat_models import FakeListChatModel  # noqa: E402
from langchain_core.messages import AIMessage, BaseMessage  # noqa: E402
from langchain_core.outputs import ChatGeneration, ChatResult  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from alembic import command  # noqa: E402
from app.agent import gateway  # noqa: E402
from app.core.clock import KST, get_today  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.db import engine, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services import accounts as account_service  # noqa: E402
from app.services.accounts import AccountContext  # noqa: E402
from app.services.seed import load_personas  # noqa: E402
from app.services.visitors import authenticate, create_visitor  # noqa: E402

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


class ScriptedChatModel(BaseChatModel):
    """도구 호출까지 흉내 내는 가짜 모델. 정해 둔 AIMessage를 순서대로 돌려줍니다.

    `calls`에 받은 메시지 목록을 남겨, 모델에 무엇이 넘어갔는지(개인정보 가림 등) 확인합니다.
    """

    script: list[AIMessage]
    calls: list[list[BaseMessage]] = []

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):  # noqa: ANN001, ANN003, ANN201
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ANN001, ANN003, ANN202
        self.calls.append(list(messages))
        message = self.script.pop(0) if self.script else AIMessage("알겠어요.")
        return ChatResult(generations=[ChatGeneration(message=message)])


@pytest.fixture
def scripted_llm(monkeypatch: pytest.MonkeyPatch):
    """도구 호출을 포함한 응답 순서를 정합니다.

    사용: scripted_llm([AIMessage("", tool_calls=[{"name": ..., "args": ..., "id": "c1"}]),
                        AIMessage("답")])
    """

    def _install(script: list[AIMessage]) -> ScriptedChatModel:
        model = ScriptedChatModel(script=list(script), calls=[])
        monkeypatch.setattr(gateway, "get_chat_model", lambda role="agent": model)
        return model

    return _install


TEST_TODAY = date(2026, 10, 21)


@pytest.fixture
def entered_headers(client: TestClient) -> Callable[[str], dict[str, str]]:
    """API 테스트용: 새 방문자로 시연 계정에 입장하고 요청 헤더를 돌려줍니다.

    사용: headers = entered_headers("lee"); client.get("/accounts/lee/rounds", headers=headers)
    오늘 날짜는 TEST_TODAY로 고정됩니다.
    """
    app.dependency_overrides[get_today] = lambda: TEST_TODAY

    def _enter(persona_id: str) -> dict[str, str]:
        token = client.post("/visitors").json()["visitor_token"]
        headers = {"Authorization": f"Bearer {token}"}
        res = client.put(f"/accounts/{persona_id}", headers=headers)
        assert res.status_code in (200, 201), res.text
        return headers

    return _enter


@pytest.fixture
def entered_account(db_session: Session) -> Callable[[str], AccountContext]:
    """서비스 테스트용: HTTP 없이 시연 계정을 만들고 AccountContext를 돌려줍니다.

    오늘 날짜는 TEST_TODAY로 봅니다.
    """
    load_personas(db_session)

    def _enter(persona_id: str) -> AccountContext:
        now = datetime.combine(TEST_TODAY, time(9), KST)
        visitor = create_visitor(db_session, now)
        ctx = authenticate(db_session, visitor.visitor_token, now)
        account_service.enter(db_session, ctx.visitor_id, persona_id, TEST_TODAY)
        return account_service.find_account(db_session, ctx.visitor_id, persona_id)

    return _enter
