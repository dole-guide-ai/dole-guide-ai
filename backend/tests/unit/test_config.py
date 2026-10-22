import logging

import pytest
from pydantic import ValidationError

from app.core.config import Settings

LLM_KEYS = (
    "LLM_API_KEY",
    "AGENT_MODEL",
    "EXTRACT_MODEL",
    "LLM_BASE_URL",
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


def test_empty_base_url_becomes_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_BASE_URL", "")

    assert Settings(_env_file=None).llm_base_url is None


def test_non_local_env_requires_llm_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AGENT_MODEL", "test-agent-model")

    with pytest.raises(ValidationError, match="LLM_API_KEY, EXTRACT_MODEL"):
        Settings(_env_file=None)


def test_local_env_only_warns_missing_keys(caplog: pytest.LogCaptureFixture) -> None:
    settings = Settings(_env_file=None)

    with caplog.at_level(logging.WARNING):
        settings.warn_missing_keys()

    assert "LLM_API_KEY, AGENT_MODEL, EXTRACT_MODEL" in caplog.text


def test_warning_does_not_log_secret_values(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("LLM_API_KEY", "sk-test-synthetic-value")
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
    for key in ("LLM_API_KEY", "AGENT_MODEL", "EXTRACT_MODEL"):
        monkeypatch.setenv(key, "test-value")

    with pytest.raises(ValidationError, match="INTERNAL_API_SECRET, ACCOUNT_ENCRYPTION_KEY"):
        Settings(_env_file=None)


def test_runtime_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.visitor_ttl_days == 7
    assert settings.max_upload_mb == 4
    assert settings.turn_timeout_seconds == 180
