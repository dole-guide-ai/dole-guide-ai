import logging

import pytest
from pydantic import ValidationError

from app.core.config import Settings

LLM_KEYS = (
    "OPENAI_API_KEY",
    "UPSTAGE_API_KEY",
    "AGENT_PROVIDER",
    "AGENT_MODEL",
    "EXTRACT_PROVIDER",
    "EXTRACT_MODEL",
    "JUDGE_PROVIDER",
    "JUDGE_MODEL",
    "INTERNAL_API_SECRET",
    "ACCOUNT_ENCRYPTION_KEY",
)


@pytest.fixture(autouse=True)
def clear_llm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (*LLM_KEYS, "APP_ENV"):
        monkeypatch.delenv(key, raising=False)


def test_settings_reads_model_names_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_MODEL", "test-agent-model")
    monkeypatch.setenv("EXTRACT_MODEL", "test-extract-model")

    settings = Settings(_env_file=None)

    assert settings.agent_model == "test-agent-model"
    assert settings.extract_model == "test-extract-model"


def test_empty_judge_provider_follows_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_PROVIDER", "upstage")
    monkeypatch.setenv("AGENT_MODEL", "test-agent-model")
    monkeypatch.setenv("JUDGE_PROVIDER", "")

    assert Settings(_env_file=None).chat_target("judge") == ("upstage", "test-agent-model")


def test_chat_target_by_role(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_PROVIDER", "upstage")
    monkeypatch.setenv("AGENT_MODEL", "test-agent-model")
    monkeypatch.setenv("EXTRACT_MODEL", "test-extract-model")
    monkeypatch.setenv("JUDGE_PROVIDER", "openai")
    monkeypatch.setenv("JUDGE_MODEL", "test-judge-model")
    settings = Settings(_env_file=None)

    assert settings.chat_target("agent") == ("upstage", "test-agent-model")
    assert settings.chat_target("extract") == ("openai", "test-extract-model")
    assert settings.chat_target("judge") == ("openai", "test-judge-model")


def test_has_llm_key_checks_chosen_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-synthetic-value")
    monkeypatch.setenv("AGENT_PROVIDER", "upstage")
    settings = Settings(_env_file=None)

    assert not settings.has_llm_key("agent")
    assert settings.has_llm_key("extract")


def test_unknown_provider_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_PROVIDER", "unknown")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_non_local_env_requires_llm_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AGENT_MODEL", "test-agent-model")

    with pytest.raises(ValidationError, match="OPENAI_API_KEY, EXTRACT_MODEL"):
        Settings(_env_file=None)


def test_local_env_only_warns_missing_keys(caplog: pytest.LogCaptureFixture) -> None:
    settings = Settings(_env_file=None)

    with caplog.at_level(logging.WARNING):
        settings.warn_missing_keys()

    assert "OPENAI_API_KEY, AGENT_MODEL, EXTRACT_MODEL" in caplog.text


def test_warning_does_not_log_secret_values(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-synthetic-value")
    settings = Settings(_env_file=None)

    with caplog.at_level(logging.WARNING):
        settings.warn_missing_keys()

    assert "sk-test-synthetic-value" not in caplog.text


def test_cors_origin_regex_reads_env_and_empty_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGIN_REGEX", r"^https://dole-guide-[a-z0-9]+-team\.vercel\.app$")
    assert Settings(_env_file=None).cors_origin_regex is not None

    monkeypatch.setenv("CORS_ORIGIN_REGEX", "")
    assert Settings(_env_file=None).cors_origin_regex is None


def test_cors_origins_reads_json_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", '["https://a.example.com","https://b.example.com"]')

    assert Settings(_env_file=None).cors_origins == [
        "https://a.example.com",
        "https://b.example.com",
    ]


def test_non_local_env_requires_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    for key in ("OPENAI_API_KEY", "AGENT_MODEL", "EXTRACT_MODEL"):
        monkeypatch.setenv(key, "test-value")

    with pytest.raises(ValidationError, match="INTERNAL_API_SECRET, ACCOUNT_ENCRYPTION_KEY"):
        Settings(_env_file=None)


def test_non_local_env_requires_only_used_provider_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AGENT_PROVIDER", "upstage")
    monkeypatch.setenv("EXTRACT_PROVIDER", "upstage")
    for key in ("AGENT_MODEL", "EXTRACT_MODEL", "INTERNAL_API_SECRET", "ACCOUNT_ENCRYPTION_KEY"):
        monkeypatch.setenv(key, "test-value")

    with pytest.raises(ValidationError, match="APP_ENV=production에서는 UPSTAGE_API_KEY 값이"):
        Settings(_env_file=None)


def test_runtime_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.visitor_ttl_days == 7
    assert settings.max_upload_mb == 4
    assert settings.turn_timeout_seconds == 180


def test_embedding_provider_key_required_when_model_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    for key in (
        "OPENAI_API_KEY",
        "AGENT_MODEL",
        "EXTRACT_MODEL",
        "INTERNAL_API_SECRET",
        "ACCOUNT_ENCRYPTION_KEY",
    ):
        monkeypatch.setenv(key, "test-value")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "upstage")
    monkeypatch.setenv("EMBEDDING_MODEL", "test-embed")

    with pytest.raises(ValidationError, match="UPSTAGE_API_KEY"):
        Settings(_env_file=None)


def test_embedding_key_not_required_without_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMBEDDING_PROVIDER", "upstage")

    assert "upstage_api_key" not in Settings(_env_file=None).missing_required_keys()


def test_each_work24_api_uses_its_own_key_then_the_old_shared_key() -> None:
    from app.core.config import Settings

    settings = Settings(
        work24_code_api_key="code-key", work24_training_api_key="", work24_api_key="old-key"
    )
    assert settings.work24_key("code") == "code-key"
    # 훈련과정 키가 비었으면 예전 공용 키를 씁니다(이미 배포된 설정이 깨지지 않게).
    assert settings.work24_key("training") == "old-key"
    assert Settings(work24_program_api_key="", work24_api_key="").work24_key("program") == ""
