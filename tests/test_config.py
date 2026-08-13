import pytest

from llm_router.config import load_settings


ENV_KEYS = (
    "OPENAI_API_KEY",
    "DATABASE_PATH",
    "INTENT_MODEL",
    "HIGH_QUALITY_MODEL",
    "BALANCED_MODEL",
    "ECONOMY_MODEL",
    "CHAT_HISTORY_MESSAGES",
)


def ignore_local_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("llm_router.config.load_dotenv", lambda: False)
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_load_settings_uses_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    ignore_local_dotenv(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret")

    settings = load_settings()

    assert settings.intent_model == "gpt-5.4-nano"
    assert settings.database_path == "data/llm_router.db"
    assert settings.high_quality_model == "gpt-5.6-sol"
    assert settings.balanced_model == "gpt-5.6-terra"
    assert settings.economy_model == "gpt-5.6-luna"
    assert settings.chat_history_messages == 10
    assert "test-secret" not in repr(settings)


def test_load_settings_reads_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    ignore_local_dotenv(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret")
    monkeypatch.setenv("INTENT_MODEL", "intent-test")
    monkeypatch.setenv("DATABASE_PATH", "custom/router.db")
    monkeypatch.setenv("HIGH_QUALITY_MODEL", "quality-test")
    monkeypatch.setenv("CHAT_HISTORY_MESSAGES", "7")

    settings = load_settings()

    assert settings.openai_api_key == "test-secret"
    assert settings.intent_model == "intent-test"
    assert settings.database_path == "custom/router.db"
    assert settings.high_quality_model == "quality-test"
    assert settings.chat_history_messages == 7


def test_load_settings_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    ignore_local_dotenv(monkeypatch)

    with pytest.raises(ValueError, match="OPENAI_API_KEY is missing"):
        load_settings()
