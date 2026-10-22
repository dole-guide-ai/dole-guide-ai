import logging
from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# local이 아닌 환경에서 비어 있으면 서버가 시작되지 않는 키
REQUIRED_OUTSIDE_LOCAL = (
    "llm_api_key",
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
    llm_provider: str = "openai"
    llm_api_key: str = ""
    llm_base_url: str | None = None
    agent_model: str = ""
    extract_model: str = ""
    # 평가(골든셋) LLM 판정 모델. 서버는 쓰지 않고, 비우면 agent_model을 씁니다.
    judge_model: str = ""

    # BFF(Next)가 붙이는 X-Internal-Secret 값. local에서 비우면 확인하지 않습니다.
    internal_api_secret: str = ""
    # 계좌 암호화 키(Fernet). local에서 비우면 개발용 키를 씁니다.
    account_encryption_key: str = ""
    # 고용24 OpenAPI 인증키. 비우면 스냅샷만 씁니다.
    work24_api_key: str = ""
    # LangSmith 관측. 키가 없으면 꺼집니다.
    langsmith_api_key: str = ""
    langsmith_project: str = "dole-guide-ai"
    langsmith_tracing: bool = False

    visitor_ttl_days: int = 7
    upload_dir: str = "./uploads"
    max_upload_mb: int = 4
    turn_timeout_seconds: int = 180

    @field_validator("llm_base_url", "cors_origin_regex", mode="before")
    @classmethod
    def empty_to_none(cls, value: str | None) -> str | None:
        # .env의 빈 값(`LLM_BASE_URL=`)은 "설정 안 함"(None)으로 봅니다.
        return value or None

    @model_validator(mode="after")
    def check_required_keys(self) -> Settings:
        if not self.database_url:
            raise ValueError("DATABASE_URL이 비어 있습니다. backend/.env를 확인하세요.")
        if self.app_env != "local" and (missing := self.missing_required_keys()):
            names = ", ".join(name.upper() for name in missing)
            raise ValueError(f"APP_ENV={self.app_env}에서는 {names} 값이 필요합니다.")
        return self

    def missing_required_keys(self) -> list[str]:
        return [name for name in REQUIRED_OUTSIDE_LOCAL if not getattr(self, name)]

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
