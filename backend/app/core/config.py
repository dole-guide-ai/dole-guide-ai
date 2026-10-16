from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    database_url: str = "postgresql+psycopg://dole:dole@localhost:5432/dole"
    cors_origins: list[str] = ["http://localhost:3000"]

    # 모델명은 코드에 직접 쓰지 않고 여기(.env)에서만 지정합니다.
    llm_provider: str = "openai"
    llm_api_key: str = ""
    llm_base_url: str | None = None
    agent_model: str = ""
    extract_model: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
