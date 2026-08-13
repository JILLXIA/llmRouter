import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from llm_router.storage import (
    clear_messages,
    get_or_create_session,
    initialize_database,
    load_messages,
    save_message,
)


def test_database_initialization_is_idempotent(tmp_path: Path) -> None:
    database = tmp_path / "nested" / "router.db"

    initialize_database(database)
    initialize_database(database)

    with closing(sqlite3.connect(database)) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert {"sessions", "messages"}.issubset(tables)


def test_session_ids_are_validated_and_persisted(tmp_path: Path) -> None:
    database = tmp_path / "router.db"
    requested = str(uuid4())

    assert get_or_create_session(database, requested) == requested
    assert get_or_create_session(database, requested) == requested

    replacement = get_or_create_session(database, "not-a-uuid")
    assert replacement != "not-a-uuid"
    assert UUID(replacement).version == 4


def test_messages_round_trip_in_order_with_routing_metadata(tmp_path: Path) -> None:
    database = tmp_path / "router.db"
    session_id = get_or_create_session(database)

    save_message(database, session_id, "user", "Hello")
    save_message(
        database,
        session_id,
        "assistant",
        "Hi there",
        {
            "intent": "GENERAL",
            "classifier_source": "llm",
            "model": "economy-model",
            "latency_ms": 125.5,
            "input_tokens": 11,
            "output_tokens": 4,
            "total_tokens": 15,
        },
    )

    assert load_messages(database, session_id) == [
        {"role": "user", "content": "Hello"},
        {
            "role": "assistant",
            "content": "Hi there",
            "routing": {
                "intent": "GENERAL",
                "classifier_source": "llm",
                "model": "economy-model",
                "latency_ms": 125.5,
                "input_tokens": 11,
                "output_tokens": 4,
                "total_tokens": 15,
            },
        },
    ]


def test_sessions_are_isolated_and_clear_only_removes_target(tmp_path: Path) -> None:
    database = tmp_path / "router.db"
    first_session = get_or_create_session(database)
    second_session = get_or_create_session(database)
    save_message(database, first_session, "user", "First session")
    save_message(database, second_session, "user", "Second session")

    clear_messages(database, first_session)

    assert load_messages(database, first_session) == []
    assert load_messages(database, second_session) == [
        {"role": "user", "content": "Second session"}
    ]
    assert get_or_create_session(database, first_session) == first_session


@pytest.mark.parametrize(
    ("role", "content", "message"),
    [
        ("system", "Hello", "role must be"),
        ("user", "   ", "content cannot be empty"),
    ],
)
def test_invalid_messages_are_rejected(
    tmp_path: Path,
    role: str,
    content: str,
    message: str,
) -> None:
    database = tmp_path / "router.db"
    session_id = get_or_create_session(database)

    with pytest.raises(ValueError, match=message):
        save_message(database, session_id, role, content)  # type: ignore[arg-type]
