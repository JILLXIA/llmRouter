from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Literal
from uuid import UUID, uuid4

from llm_router.models import ConversationSummary

Role = Literal["user", "assistant"]
DatabasePath = str | Path


@contextmanager
def _connect(database_path: DatabasePath) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(database_path, timeout=5)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA journal_mode = WAL")
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database(database_path: DatabasePath) -> None:
    """Create the database directory and schema if they do not exist."""

    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with _connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                intent TEXT,
                classifier_source TEXT,
                model TEXT,
                latency_ms REAL,
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                total_tokens INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_messages_session_id
            ON messages(session_id, id);

            CREATE TABLE IF NOT EXISTS conversation_summaries (
                session_id TEXT PRIMARY KEY,
                summary TEXT NOT NULL,
                summarized_through_message_id INTEGER NOT NULL,
                model TEXT NOT NULL,
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );
            """
        )


def _valid_session_id(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError):
        return None
    return str(parsed) if parsed.version == 4 else None


def get_or_create_session(
    database_path: DatabasePath,
    requested_id: str | None = None,
) -> str:
    """Return a valid UUID session, creating its database row when needed."""

    initialize_database(database_path)
    session_id = _valid_session_id(requested_id) or str(uuid4())

    with _connect(database_path) as connection:
        connection.execute(
            "INSERT OR IGNORE INTO sessions (id) VALUES (?)",
            (session_id,),
        )
    return session_id


def load_messages(database_path: DatabasePath, session_id: str) -> list[dict[str, Any]]:
    """Load a session's messages in conversation order."""

    with _connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT id, role, content, intent, classifier_source, model, latency_ms,
                   input_tokens, output_tokens, total_tokens
            FROM messages
            WHERE session_id = ?
            ORDER BY id
            """,
            (session_id,),
        ).fetchall()

    messages: list[dict[str, Any]] = []
    for row in rows:
        message: dict[str, Any] = {
            "id": row["id"],
            "role": row["role"],
            "content": row["content"],
        }
        if row["intent"] and row["classifier_source"] and row["model"]:
            message["routing"] = {
                "intent": row["intent"],
                "classifier_source": row["classifier_source"],
                "model": row["model"],
                "latency_ms": row["latency_ms"] or 0.0,
                "input_tokens": row["input_tokens"],
                "output_tokens": row["output_tokens"],
                "total_tokens": row["total_tokens"],
            }
        messages.append(message)
    return messages


def load_summary(
    database_path: DatabasePath,
    session_id: str,
) -> ConversationSummary | None:
    """Load the current rolling summary for a session."""

    with _connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT summary, summarized_through_message_id, model,
                   input_tokens, output_tokens
            FROM conversation_summaries
            WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()
    if not row:
        return None
    return ConversationSummary(
        text=row["summary"],
        summarized_through_message_id=row["summarized_through_message_id"],
        model=row["model"],
        input_tokens=row["input_tokens"],
        output_tokens=row["output_tokens"],
    )


def save_summary(
    database_path: DatabasePath,
    session_id: str,
    summary: ConversationSummary,
) -> None:
    """Atomically insert or replace a session's rolling summary."""

    if not summary.text.strip():
        raise ValueError("summary cannot be empty")
    if summary.summarized_through_message_id < 1:
        raise ValueError("summary boundary must be a positive message id")

    with _connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO conversation_summaries (
                session_id, summary, summarized_through_message_id, model,
                input_tokens, output_tokens
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                summary = excluded.summary,
                summarized_through_message_id =
                    excluded.summarized_through_message_id,
                model = excluded.model,
                input_tokens = excluded.input_tokens,
                output_tokens = excluded.output_tokens,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                session_id,
                summary.text,
                summary.summarized_through_message_id,
                summary.model,
                summary.input_tokens,
                summary.output_tokens,
            ),
        )


def save_message(
    database_path: DatabasePath,
    session_id: str,
    role: Role,
    content: str,
    routing: Mapping[str, str | int | float] | None = None,
) -> None:
    """Append one user or assistant message and update session activity."""

    if role not in {"user", "assistant"}:
        raise ValueError("role must be 'user' or 'assistant'")
    if not content.strip():
        raise ValueError("message content cannot be empty")

    metadata = routing or {}
    with _connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO messages (
                session_id, role, content, intent, classifier_source, model,
                latency_ms, input_tokens, output_tokens, total_tokens
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                role,
                content,
                metadata.get("intent"),
                metadata.get("classifier_source"),
                metadata.get("model"),
                metadata.get("latency_ms"),
                int(metadata.get("input_tokens", 0)),
                int(metadata.get("output_tokens", 0)),
                int(metadata.get("total_tokens", 0)),
            ),
        )
        connection.execute(
            "UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (session_id,),
        )


def clear_messages(database_path: DatabasePath, session_id: str) -> None:
    """Delete a session's messages while keeping the session itself."""

    with _connect(database_path) as connection:
        connection.execute(
            "DELETE FROM conversation_summaries WHERE session_id = ?",
            (session_id,),
        )
        connection.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        connection.execute(
            "UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (session_id,),
        )
