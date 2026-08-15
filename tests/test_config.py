import pytest

from llm_router.config import load_settings


ENV_KEYS = (
    "OPENAI_API_KEY",
    "DATABASE_PATH",
    "INTENT_MODEL",
    "HIGH_QUALITY_MODEL",
    "BALANCED_MODEL",
    "ECONOMY_MODEL",
    "CONTEXT_TOKEN_BUDGET",
    "SUMMARY_TRIGGER_TOKENS",
    "RECENT_CONTEXT_TOKENS",
    "SUMMARY_MAX_OUTPUT_TOKENS",
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
    assert settings.context_token_budget == 8000
    assert settings.summary_trigger_tokens == 6000
    assert settings.recent_context_tokens == 3000
    assert settings.summary_max_output_tokens == 600
    assert "test-secret" not in repr(settings)


def test_load_settings_reads_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    ignore_local_dotenv(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret")
    monkeypatch.setenv("INTENT_MODEL", "intent-test")
    monkeypatch.setenv("DATABASE_PATH", "custom/router.db")
    monkeypatch.setenv("HIGH_QUALITY_MODEL", "quality-test")
    monkeypatch.setenv("CONTEXT_TOKEN_BUDGET", "7000")
    monkeypatch.setenv("SUMMARY_TRIGGER_TOKENS", "5000")
    monkeypatch.setenv("RECENT_CONTEXT_TOKENS", "2500")
    monkeypatch.setenv("SUMMARY_MAX_OUTPUT_TOKENS", "500")

    settings = load_settings()

    assert settings.openai_api_key == "test-secret"
    assert settings.intent_model == "intent-test"
    assert settings.database_path == "custom/router.db"
    assert settings.high_quality_model == "quality-test"
    assert settings.context_token_budget == 7000
    assert settings.summary_trigger_tokens == 5000
    assert settings.recent_context_tokens == 2500
    assert settings.summary_max_output_tokens == 500


def test_load_settings_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    ignore_local_dotenv(monkeypatch)

    with pytest.raises(ValueError, match="OPENAI_API_KEY is missing"):
        load_settings()


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("SUMMARY_TRIGGER_TOKENS", "9000", "cannot exceed"),
        ("RECENT_CONTEXT_TOKENS", "9000", "cannot exceed"),
        ("SUMMARY_MAX_OUTPUT_TOKENS", "0", "must be positive"),
    ],
)
def test_load_settings_rejects_invalid_context_budgets(
    monkeypatch: pytest.MonkeyPatch,
    key: str,
    value: str,
    message: str,
) -> None:
    ignore_local_dotenv(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret")
    monkeypatch.setenv(key, value)

    with pytest.raises(ValueError, match=message):
        load_settings()
