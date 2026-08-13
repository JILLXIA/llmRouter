from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    openai_api_key: str = field(repr=False)
    database_path: str = "data/llm_router.db"
    intent_model: str = "gpt-5.4-nano"
    high_quality_model: str = "gpt-5.6-sol"
    balanced_model: str = "gpt-5.6-terra"
    economy_model: str = "gpt-5.6-luna"
    chat_history_messages: int = 10
    response_max_output_tokens: int = 1_200
    openai_timeout_seconds: float = 60.0
    keyword_min_matches: int = 2
    keyword_min_margin: int = 1


def load_settings() -> Settings:
    """Load `.env` and return the small set of values used by the app."""

    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is missing from .env")

    return Settings(
        openai_api_key=api_key,
        database_path=os.getenv("DATABASE_PATH", "data/llm_router.db"),
        intent_model=os.getenv("INTENT_MODEL", "gpt-5.4-nano"),
        high_quality_model=os.getenv("HIGH_QUALITY_MODEL", "gpt-5.6-sol"),
        balanced_model=os.getenv("BALANCED_MODEL", "gpt-5.6-terra"),
        economy_model=os.getenv("ECONOMY_MODEL", "gpt-5.6-luna"),
        chat_history_messages=int(os.getenv("CHAT_HISTORY_MESSAGES", "10")),
        response_max_output_tokens=int(
            os.getenv("RESPONSE_MAX_OUTPUT_TOKENS", "1200")
        ),
        openai_timeout_seconds=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "60")),
        keyword_min_matches=int(os.getenv("KEYWORD_MIN_MATCHES", "2")),
        keyword_min_margin=int(os.getenv("KEYWORD_MIN_MARGIN", "1")),
    )
