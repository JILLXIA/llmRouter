from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from llm_router.models import ChatResult, Intent

APP_PATH = Path(__file__).parents[1] / "app.py"


def test_app_renders_chat_controls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    app = AppTest.from_file(str(APP_PATH)).run(timeout=10)

    assert not app.exception
    assert app.title[0].value == "LLM Router Chat"
    assert app.chat_input[0].placeholder == "Ask me anything..."
    assert app.button[0].label == "Clear chat"


def test_app_explains_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("llm_router.config.load_dotenv", lambda: False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    app = AppTest.from_file(str(APP_PATH)).run(timeout=10)

    assert not app.exception
    assert "OPENAI_API_KEY is missing" in app.error[0].value


def test_mocked_chat_submission(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeRouter:
        def __init__(self, settings: object) -> None:
            pass

        def chat(self, prompt: str, history: list[object]) -> ChatResult:
            assert prompt == "Implement a Python endpoint"
            assert history == []
            return ChatResult(
                response="Mock implementation",
                intent=Intent.CODE_GENERATION,
                classifier_source="keyword",
                model="test-code-model",
                latency_ms=1.5,
            )

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("llm_router.router.LLMRouter", FakeRouter)

    app = AppTest.from_file(str(APP_PATH)).run(timeout=10)
    app.chat_input[0].set_value("Implement a Python endpoint").run(timeout=10)

    assert not app.exception
    assert any(item.value == "Mock implementation" for item in app.markdown)
    assert "Intent: CODE_GENERATION" in app.caption[0].value
    assert "Model: test-code-model" in app.caption[0].value
    assert "Tokens: 0 in + 0 out = 0 total" in app.caption[0].value


def test_clear_chat(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    app = AppTest.from_file(str(APP_PATH))
    app.session_state["messages"] = [{"role": "user", "content": "Hello"}]

    app.run(timeout=10)
    app.button[0].click().run(timeout=10)

    assert not app.exception
    assert app.session_state["messages"] == []
