from collections.abc import Callable
from pathlib import Path
from uuid import UUID

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from llm_router.models import ChatResult, ConversationSummary, Intent
from llm_router.router import RouterError
from llm_router.storage import (
    get_or_create_session,
    load_messages,
    load_summary,
    save_message,
    save_summary,
)

APP_PATH = Path(__file__).parents[1] / "app.py"


def configure_app(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Path:
    database = tmp_path / "router.db"
    st.cache_resource.clear()
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("DATABASE_PATH", str(database))
    return database


def query_session_id(app: AppTest) -> str:
    value = app.query_params["session_id"]
    return value[-1] if isinstance(value, list) else value


def test_app_creates_url_session_and_renders_controls(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_app(monkeypatch, tmp_path)

    app = AppTest.from_file(str(APP_PATH)).run(timeout=10)

    assert not app.exception
    assert UUID(query_session_id(app)).version == 4
    assert app.title[0].value == "LLM Router Chat"
    assert app.chat_input[0].placeholder == "Ask me anything..."
    assert app.button[0].label == "Clear chat"


def test_app_explains_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("llm_router.config.load_dotenv", lambda: False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    app = AppTest.from_file(str(APP_PATH)).run(timeout=10)

    assert not app.exception
    assert "OPENAI_API_KEY is missing" in app.error[0].value


def test_invalid_url_session_is_replaced(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_app(monkeypatch, tmp_path)
    app = AppTest.from_file(str(APP_PATH))
    app.query_params["session_id"] = "invalid"

    app.run(timeout=10)

    assert not app.exception
    assert UUID(query_session_id(app)).version == 4


def test_persisted_session_is_restored_from_url(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database = configure_app(monkeypatch, tmp_path)
    session_id = get_or_create_session(database)
    save_message(database, session_id, "user", "Persisted question")
    save_message(database, session_id, "assistant", "Persisted answer")
    save_summary(
        database,
        session_id,
        ConversationSummary("Compacted memory", 2, "economy-model"),
    )

    app = AppTest.from_file(str(APP_PATH))
    app.query_params["session_id"] = session_id
    app.run(timeout=10)

    assert not app.exception
    assert any(item.value == "Persisted question" for item in app.markdown)
    assert any(item.value == "Persisted answer" for item in app.markdown)
    assert not any(item.value == "Compacted memory" for item in app.markdown)
    assert query_session_id(app) == session_id


def test_mocked_chat_submission_is_persisted(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database = configure_app(monkeypatch, tmp_path)

    class FakeRouter:
        def __init__(self, settings: object) -> None:
            pass

        def chat(
            self,
            prompt: str,
            history: list[object],
            conversation_summary: ConversationSummary | None = None,
            on_chunk: Callable[[str], None] | None = None,
        ) -> ChatResult:
            assert prompt == "Implement a Python endpoint"
            assert history == []
            assert conversation_summary is None
            assert on_chunk is not None
            on_chunk("Mock ")
            on_chunk("implementation")
            return ChatResult(
                response="Mock implementation",
                intent=Intent.CODE_GENERATION,
                classifier_source="keyword",
                model="test-code-model",
                latency_ms=1.5,
                summary_update=ConversationSummary(
                    "Remember the API requirement.",
                    1,
                    "economy-model",
                    12,
                    4,
                ),
            )

    monkeypatch.setattr("llm_router.router.LLMRouter", FakeRouter)

    app = AppTest.from_file(str(APP_PATH)).run(timeout=10)
    session_id = query_session_id(app)
    app.chat_input[0].set_value("Implement a Python endpoint").run(timeout=10)

    assert not app.exception
    assert any(item.value == "Mock implementation" for item in app.markdown)
    assert "Intent: CODE_GENERATION" in app.caption[0].value
    assert "Model: test-code-model" in app.caption[0].value
    assert "Tokens: 0 in + 0 out = 0 total" in app.caption[0].value
    assert [message["role"] for message in load_messages(database, session_id)] == [
        "user",
        "assistant",
    ]
    assert load_summary(database, session_id) == ConversationSummary(
        "Remember the API requirement.",
        1,
        "economy-model",
        12,
        4,
    )


def test_clear_chat_deletes_only_current_session_messages(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database = configure_app(monkeypatch, tmp_path)
    session_id = get_or_create_session(database)
    save_message(database, session_id, "user", "Hello")

    app = AppTest.from_file(str(APP_PATH))
    app.query_params["session_id"] = session_id
    app.run(timeout=10)
    app.button[0].click().run(timeout=10)

    assert not app.exception
    assert load_messages(database, session_id) == []
    assert query_session_id(app) == session_id


def test_failed_model_call_keeps_user_message(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database = configure_app(monkeypatch, tmp_path)

    class FailingRouter:
        def __init__(self, settings: object) -> None:
            pass

        def chat(
            self,
            prompt: str,
            history: list[object],
            conversation_summary: ConversationSummary | None = None,
            on_chunk: Callable[[str], None] | None = None,
        ) -> ChatResult:
            assert on_chunk is not None
            on_chunk("Partial answer")
            raise RouterError(
                "The model request could not be completed. Please try again."
            )

    monkeypatch.setattr("llm_router.router.LLMRouter", FailingRouter)

    app = AppTest.from_file(str(APP_PATH)).run(timeout=10)
    session_id = query_session_id(app)
    app.chat_input[0].set_value("Please answer this").run(timeout=10)

    assert not app.exception
    assert app.error[0].value == (
        "The model request could not be completed. Please try again."
    )
    assert not any(item.value == "Partial answer" for item in app.markdown)
    messages = load_messages(database, session_id)
    assert [(item["role"], item["content"]) for item in messages] == [
        ("user", "Please answer this")
    ]
