import httpx
import openai
import pytest

from app.agent import gateway
from app.core.config import Settings
from app.core.errors import LlmUnavailableError, RateLimitedError


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch):
    """gateway가 읽을 설정을 테스트 값으로 바꿉니다. 키는 합성 값입니다."""

    def _set(**values: str) -> Settings:
        fixed = Settings(_env_file=None, **values)
        monkeypatch.setattr(gateway, "get_settings", lambda: fixed)
        return fixed

    return _set


def test_fake_llm_replaces_gateway_model(fake_llm) -> None:
    fake_llm(["안녕하세요"])

    reply = gateway.get_chat_model().invoke("테스트")

    assert reply.content == "안녕하세요"


def test_openai_chat_model_uses_default_url(settings) -> None:
    settings(openai_api_key="sk-test-openai", agent_model="test-agent-model")

    model = gateway.get_chat_model()

    assert model.model_name == "test-agent-model"
    assert model.openai_api_base is None
    assert model.openai_api_key.get_secret_value() == "sk-test-openai"


def test_upstage_chat_model_uses_upstage_url_and_key(settings) -> None:
    settings(
        openai_api_key="sk-test-openai",
        upstage_api_key="up-test-upstage",
        extract_provider="upstage",
        extract_model="test-extract-model",
    )

    model = gateway.get_chat_model("extract")

    assert model.model_name == "test-extract-model"
    assert model.openai_api_base == "https://api.upstage.ai/v1"
    assert model.openai_api_key.get_secret_value() == "up-test-upstage"


def test_embeddings_single_model(settings) -> None:
    settings(openai_api_key="sk-test-openai", embedding_model="test-embed")

    embeddings = gateway.get_embeddings()

    assert embeddings.model == "test-embed"
    assert embeddings.check_embedding_ctx_length is True


def test_upstage_embeddings_split_query_and_passage(settings) -> None:
    settings(
        upstage_api_key="up-test-upstage",
        embedding_provider="upstage",
        embedding_model="test-passage",
        embedding_query_model="test-query",
    )

    embeddings = gateway.get_embeddings()

    assert embeddings.documents.model == "test-passage"
    assert embeddings.query.model == "test-query"
    assert embeddings.documents.openai_api_base == "https://api.upstage.ai/v1"
    assert embeddings.documents.check_embedding_ctx_length is False


def test_to_app_error_maps_rate_limit_and_others() -> None:
    request = httpx.Request("POST", "https://example.invalid")
    response = httpx.Response(429, request=request)
    rate_limited = openai.RateLimitError("limit", response=response, body=None)

    assert isinstance(gateway.to_app_error(rate_limited), RateLimitedError)
    assert isinstance(gateway.to_app_error(RuntimeError("boom")), LlmUnavailableError)


LANGSMITH_ENV = (
    "LANGSMITH_TRACING",
    "LANGSMITH_API_KEY",
    "LANGSMITH_PROJECT",
    "LANGSMITH_ENDPOINT",
    "LANGSMITH_HIDE_INPUTS",
    "LANGSMITH_HIDE_OUTPUTS",
)


@pytest.fixture
def clean_langsmith_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # configure_tracing이 바꾼 os.environ을 테스트 뒤에 되돌립니다.
    for key in LANGSMITH_ENV:
        monkeypatch.setenv(key, "")
        monkeypatch.delenv(key)


def test_tracing_off_without_key(settings, clean_langsmith_env) -> None:
    settings(langsmith_tracing=True)

    assert gateway.configure_tracing() is False
    assert gateway.os.environ["LANGSMITH_TRACING"] == "false"
    assert "LANGSMITH_API_KEY" not in gateway.os.environ


def test_tracing_on_with_key_and_hidden_io(settings, clean_langsmith_env) -> None:
    settings(
        langsmith_tracing=True,
        langsmith_api_key="ls-test-synthetic",
        langsmith_project="test-project",
        langsmith_hide_io=True,
        langsmith_endpoint="https://apac.api.smith.langchain.com/",
    )

    assert gateway.configure_tracing() is True
    env = gateway.os.environ
    assert env["LANGSMITH_TRACING"] == "true"
    assert env["LANGSMITH_PROJECT"] == "test-project"
    assert env["LANGSMITH_ENDPOINT"] == "https://apac.api.smith.langchain.com"
    assert env["LANGSMITH_HIDE_INPUTS"] == env["LANGSMITH_HIDE_OUTPUTS"] == "true"


def test_upstage_embeddings_send_at_most_100_per_request(settings) -> None:
    settings(upstage_api_key="up-test-upstage", embedding_provider="upstage", embedding_model="m")

    assert gateway.get_embeddings().chunk_size == 100


def test_tracing_env_is_pure_and_off_without_key(clean_langsmith_env) -> None:
    env = gateway.tracing_env(Settings(_env_file=None, langsmith_tracing=True))

    assert env == {"LANGSMITH_TRACING": "false"}


def test_trace_config_carries_request_id() -> None:
    from app.agent import gateway
    from app.core.request_id import current_request_id

    token = current_request_id.set("req-12345678")
    try:
        assert gateway.trace_config() == {"metadata": {"request_id": "req-12345678"}}
    finally:
        current_request_id.reset(token)


def test_trace_callbacks_mask_personal_info(settings) -> None:
    """트레이스가 켜지면 개인정보를 가리는 트레이서를 붙입니다 (N-02)."""
    settings(langsmith_tracing=False, langsmith_api_key="")
    assert gateway.trace_callbacks() == []

    settings(langsmith_tracing=True, langsmith_api_key="lsv2-test")
    (tracer,) = gateway.trace_callbacks()
    masked = tracer.client._anonymizer({"text": "제 번호는 010-1234-5678이에요"})

    assert "010-1234-5678" not in masked["text"]
