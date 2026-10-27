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
# 근거 카드 재정렬은 실제 모델(extract)을 부르므로 테스트에서는 끕니다(검색 순위 그대로).
# 실제 모델 평가는 evals/conftest.py가 .env·기본값으로 되돌립니다.
os.environ["RETRIEVAL_RERANK"] = "false"
# 테스트는 고용24 OpenAPI를 실제로 부르지 않습니다. 인증키를 비워 늘 스냅샷을 씁니다.
os.environ["WORK24_API_KEY"] = ""

from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from langchain_core.language_models import BaseChatModel  # noqa: E402
from langchain_core.language_models.fake_chat_models import FakeListChatModel  # noqa: E402
from langchain_core.messages import AIMessage  # noqa: E402
from langchain_core.outputs import ChatGeneration, ChatResult  # noqa: E402
from langchain_core.runnables import RunnableLambda  # noqa: E402
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


class FakeAgentModel(BaseChatModel):
    """도구 호출까지 흉내 내는 가짜 모델.

    replies를 차례로 돌려주고, 분류(구조화 출력)에는 route를 답합니다.
    """

    replies: list[AIMessage]
    route: str = "guide"
    # 구조화 출력(분류 말고)에 차례로 돌려줄 값. 비면 schema의 기본값(이력서 읽기는 kind=none)
    structured: list[dict] = []
    calls: int = 0

    @property
    def _llm_type(self) -> str:
        return "fake-agent"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:  # noqa: ANN001
        reply = self.replies[min(self.calls, len(self.replies) - 1)]
        self.calls += 1
        return ChatResult(generations=[ChatGeneration(message=reply)])

    def bind_tools(self, tools, **kwargs) -> FakeAgentModel:  # noqa: ANN001
        return self

    def with_structured_output(self, schema, **kwargs) -> RunnableLambda:  # noqa: ANN001
        if "panel" in schema.model_fields:
            return RunnableLambda(lambda _: schema(panel=self.route))

        def answer(_):  # noqa: ANN001, ANN202
            data = self.structured.pop(0) if self.structured else {}
            return schema.model_validate(data)

        return RunnableLambda(answer)


@pytest.fixture
def fake_agent_llm(monkeypatch: pytest.MonkeyPatch):
    """그래프 테스트용: 도구 호출이 담긴 AIMessage를 순서대로 돌려주는 모델을 주입합니다.

    사용: fake_agent_llm([AIMessage("", tool_calls=[...]), AIMessage("답")], route="round")
    """

    def _install(
        replies: list[AIMessage], route: str = "guide", structured: list[dict] | None = None
    ) -> FakeAgentModel:
        model = FakeAgentModel(replies=replies, route=route, structured=list(structured or []))
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
