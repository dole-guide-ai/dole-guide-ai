import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# LLM·임베딩 공급자. 둘 다 OpenAI 호환 API라 gateway가 주소만 바꿔 부릅니다.
Provider = Literal["openai", "upstage"]
ModelRole = Literal["agent", "extract", "judge"]


@dataclass(frozen=True)
class ProviderSpec:
    """AI 공급자 하나의 고정값."""

    key_setting: str  # Settings에서 API 키를 담는 필드 이름
    base_url: str | None  # None이면 OpenAI 기본 주소
    embedding_batch_size: int  # 임베딩 요청 하나에 담는 문서 수
    # 임베딩 전 토큰 길이 검사. OpenAI 토크나이저(tiktoken) 기준이라 다른 공급자는 끕니다.
    checks_token_length: bool


PROVIDERS: dict[str, ProviderSpec] = {
    "openai": ProviderSpec("openai_api_key", None, 1000, checks_token_length=True),
    # Upstage는 임베딩 요청 하나에 100개까지 받습니다(공식 API 문서).
    "upstage": ProviderSpec(
        "upstage_api_key", "https://api.upstage.ai/v1", 100, checks_token_length=False
    ),
}

# local이 아닌 환경에서 비어 있으면 서버가 시작되지 않는 키.
# 공급자 키는 agent·extract가 고른 공급자의 것만 필요합니다(missing_required_keys).
REQUIRED_OUTSIDE_LOCAL = (
    "agent_model",
    "extract_model",
    "internal_api_secret",
    "account_encryption_key",
)


class Settings(BaseSettings):
    # hide_input_in_errors: 검증 오류 메시지에 API 키 같은 입력값이 찍히지 않게 합니다.
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", hide_input_in_errors=True
    )

    app_env: str = "local"
    database_url: str = "postgresql+psycopg://dole:dole@localhost:5432/dole"
    cors_origins: list[str] = ["http://localhost:3000"]
    # Vercel 미리보기처럼 주소가 바뀌는 프론트를 허용할 때 씁니다. 비우면 사용하지 않습니다.
    cors_origin_regex: str | None = None

    # 모델명은 코드에 직접 쓰지 않고 여기(.env)에서만 지정합니다.
    # 공급자 키는 둘 다 넣어 두고 *_PROVIDER만 바꿔 같은 흐름을 비교할 수 있습니다.
    openai_api_key: str = ""
    upstage_api_key: str = ""
    agent_provider: Provider = "openai"
    agent_model: str = ""
    extract_provider: Provider = "openai"
    extract_model: str = ""
    # 평가(골든셋) LLM 판정. 서버는 쓰지 않고, 비우면 agent 설정을 씁니다.
    # 모델끼리 비교할 때는 판정 모델을 고정해야 점수를 견줄 수 있습니다.
    judge_provider: Provider | None = None
    judge_model: str = ""
    # 임베딩(RAG). 질문용 모델이 따로 있는 공급자(Upstage)는 EMBEDDING_QUERY_MODEL에 넣습니다.
    embedding_provider: Provider = "openai"
    embedding_model: str = ""
    embedding_query_model: str = ""

    # BFF(Next)가 붙이는 X-Internal-Secret 값. local에서 비우면 확인하지 않습니다.
    internal_api_secret: str = ""
    # 계좌 암호화 키(Fernet). local에서 비우면 개발용 키를 씁니다.
    account_encryption_key: str = ""
    # 고용24 OpenAPI 인증키. API마다 따로 발급됩니다.
    # 공통코드는 scripts/fetch_work24_codes.py만 씁니다(서비스는 저장된 JSON을 읽음).
    # 훈련과정·취업역량 프로그램 키를 비우면 그 조회는 스냅샷만 씁니다.
    work24_code_api_key: str = ""
    work24_training_api_key: str = ""
    work24_program_api_key: str = ""
    # 고용24 OpenAPI 호출 하나의 대기 시간과 실패 시 다시 부르는 횟수 (설계 3.11: 5초·재시도 1회)
    external_api_timeout_seconds: float = 5
    external_api_retries: int = 1
    # 대화 에이전트 (노션 「AI 설계」 2-4: agent ⇄ tools 왕복 상한, 2-3: 기억할 최근 대화 수)
    agent_max_tool_rounds: int = 4
    agent_history_messages: int = 12
    # RAG 근거 검색 (노션 「RAG 설계 (복사본)」 4.2 · 7.4 · 7.7). 값은 평가로 조정합니다.
    rag_bm25_top_k: int = 20
    rag_vector_top_k: int = 20
    rag_rrf_k: int = 60
    rag_result_top_n: int = 5
    # '찾지 못함' 기준: 벡터 코사인 유사도 / 벡터가 없을 때 첫 자료가 질문 낱말을 덮는 비율
    rag_min_similarity: float = 0.4
    rag_min_bm25_coverage: float = 0.6
    # 리랭커는 CPU에서 느려 기본 끔. 켜려면 uv sync --extra rerank
    reranker_enabled: bool = False
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    reranker_top_n: int = 20
    # 보안 가드 백엔드 (쉼표 목록, rules는 늘 켜짐): prompt_guard, llama_guard
    guard_backends: str = "rules"
    guard_block_threshold: float = 0.8
    prompt_guard_model: str = "meta-llama/Llama-Prompt-Guard-2-86M"
    # Llama Guard를 부를 OpenAI 호환 주소·키·모델. 비우면 그 판정은 꺼집니다.
    guard_llm_base_url: str = ""
    guard_llm_api_key: str = ""
    guard_llm_model: str = ""
    # LangSmith 관측. 키가 없으면 꺼집니다.
    langsmith_api_key: str = ""
    langsmith_project: str = "dole-guide-ai"
    # 계정 지역의 API 주소. 비우면 US 기본값. 다른 지역 키는 US 주소에서 403이 납니다.
    # 예: APAC https://apac.api.smith.langchain.com, EU https://eu.api.smith.langchain.com
    langsmith_endpoint: str = ""
    langsmith_tracing: bool = False
    # 트레이스에 입력·출력 원문을 남기지 않습니다. 지금은 합성 데이터라 운영도 끄고,
    # 실서비스(실제 개인정보) 전에는 운영에서 켭니다(설계 D6).
    langsmith_hide_io: bool = False

    visitor_ttl_days: int = 7
    upload_dir: str = "./uploads"
    max_upload_mb: int = 4
    turn_timeout_seconds: int = 180
    # 모델 호출 하나의 대기 시간. 턴 타임아웃보다 짧아야 턴 안에서 실패를 알릴 수 있습니다.
    llm_timeout_seconds: int = 60
    # POST 재시도 방지 키(Idempotency-Key)를 보관하는 시간
    idempotency_ttl_hours: int = 24

    @field_validator("judge_provider", "cors_origin_regex", mode="before")
    @classmethod
    def empty_to_none(cls, value: str | None) -> str | None:
        # .env의 빈 값(`JUDGE_PROVIDER=`)은 "설정 안 함"(None)으로 봅니다.
        return value or None

    @model_validator(mode="after")
    def check_required_keys(self) -> Settings:
        if not self.database_url:
            raise ValueError("DATABASE_URL이 비어 있습니다. backend/.env를 확인하세요.")
        if self.app_env != "local" and (missing := self.missing_required_keys()):
            names = ", ".join(name.upper() for name in missing)
            raise ValueError(f"APP_ENV={self.app_env}에서는 {names} 값이 필요합니다.")
        return self

    def chat_target(self, role: ModelRole) -> tuple[Provider, str]:
        """역할별 (공급자, 모델명). judge는 비어 있으면 agent 설정을 따릅니다."""
        if role == "judge":
            return (
                self.judge_provider or self.agent_provider,
                self.judge_model or self.agent_model,
            )
        if role == "extract":
            return self.extract_provider, self.extract_model
        return self.agent_provider, self.agent_model

    def api_key_for(self, provider: Provider) -> str:
        return getattr(self, PROVIDERS[provider].key_setting)

    def has_llm_key(self, role: ModelRole = "agent") -> bool:
        return bool(self.api_key_for(self.chat_target(role)[0]))

    def missing_required_keys(self) -> list[str]:
        providers = [self.agent_provider, self.extract_provider]
        if self.embedding_model:
            # 임베딩 모델을 정했으면 그 공급자 키도 시작할 때 확인합니다(첫 검색에서 실패하지 않게).
            providers.append(self.embedding_provider)
        used = dict.fromkeys(PROVIDERS[p].key_setting for p in providers)
        names = [*used, *REQUIRED_OUTSIDE_LOCAL]
        return [name for name in names if not getattr(self, name)]

    def warn_missing_keys(self) -> None:
        """local에서 비어 있는 키 이름만 경고합니다. 값은 로그에 남기지 않습니다."""
        if missing := self.missing_required_keys():
            names = ", ".join(name.upper() for name in missing)
            logger.warning(
                "비어 있는 설정: %s — 운영에서는 필수입니다. backend/.env에 채우세요.",
                names,
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
