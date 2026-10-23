"""모든 LLM·임베딩 호출."""

import os

import openai
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.core.config import PROVIDERS, ModelRole, Provider, Settings, get_settings
from app.core.errors import AppError, LlmUnavailableError, RateLimitedError

MAX_RETRIES = 1


def get_chat_model(role: ModelRole = "agent") -> BaseChatModel:
    settings = get_settings()
    provider, model = settings.chat_target(role)
    return ChatOpenAI(
        model=model,
        api_key=settings.api_key_for(provider),
        base_url=PROVIDERS[provider].base_url,
        timeout=settings.llm_timeout_seconds,
        max_retries=MAX_RETRIES,
    )


def get_embeddings() -> Embeddings:
    """문서·질문 임베딩. 질문용 모델이 따로 지정되면 질문만 그 모델로 보냅니다."""
    settings = get_settings()
    provider = settings.embedding_provider
    documents = _embeddings(provider, settings.embedding_model)
    query_model = settings.embedding_query_model
    if not query_model or query_model == settings.embedding_model:
        return documents
    return _SplitEmbeddings(documents, _embeddings(provider, query_model))


def tracing_env(settings: Settings) -> dict[str, str]:
    """LangSmith가 읽는 환경변수 값(순수 함수).

    키와 LANGSMITH_TRACING=true가 둘 다 있을 때만 켭니다.
    """
    enabled = settings.langsmith_tracing and bool(settings.langsmith_api_key)
    env = {"LANGSMITH_TRACING": _flag(enabled)}
    if not enabled:
        return env
    env |= {
        "LANGSMITH_API_KEY": settings.langsmith_api_key,
        "LANGSMITH_PROJECT": settings.langsmith_project,
        "LANGSMITH_HIDE_INPUTS": _flag(settings.langsmith_hide_io),
        "LANGSMITH_HIDE_OUTPUTS": _flag(settings.langsmith_hide_io),
    }
    if settings.langsmith_endpoint:
        env["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint.rstrip("/")
    return env


def configure_tracing() -> bool:
    """LangSmith 트레이스를 켜거나 끕니다. 앱 시작·실제 모델 평가 때 한 번 부릅니다.

    LangChain·LangGraph는 os.environ의 LANGSMITH_* 값을 읽으므로 설정(.env)을 여기서 옮겨 둡니다.
    개인정보 가림(anonymizer)은 N-02에서 붙입니다.
    """
    env = tracing_env(get_settings())
    os.environ.update(env)
    return env["LANGSMITH_TRACING"] == "true"


def _flag(value: bool) -> str:
    return "true" if value else "false"


def to_app_error(exc: Exception) -> AppError:
    """공급자 SDK 예외를 공통 오류로 바꿉니다. 메시지에 원문을 넣지 않습니다."""
    if isinstance(exc, openai.RateLimitError):
        return RateLimitedError()
    return LlmUnavailableError()


def _embeddings(provider: Provider, model: str) -> OpenAIEmbeddings:
    settings = get_settings()
    return OpenAIEmbeddings(
        model=model,
        api_key=settings.api_key_for(provider),
        base_url=PROVIDERS[provider].base_url,
        timeout=settings.llm_timeout_seconds,
        max_retries=MAX_RETRIES,
        chunk_size=PROVIDERS[provider].embedding_batch_size,
        check_embedding_ctx_length=PROVIDERS[provider].checks_token_length,
    )


class _SplitEmbeddings(Embeddings):
    """문서와 질문을 서로 다른 모델로 임베딩하는 공급자(Upstage passage/query)용."""

    def __init__(self, documents: Embeddings, query: Embeddings) -> None:
        self.documents = documents
        self.query = query

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.documents.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return self.query.embed_query(text)
