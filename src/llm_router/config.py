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
    response_max_output_tokens: int = 1200
    openai_timeout_seconds: float = 60.0
    keyword_min_matches: int = 2
    keyword_min_margin: int = 1
    context_token_budget: int = 8000
    summary_trigger_tokens: int = 6000
    recent_context_tokens: int = 3000
    summary_max_output_tokens: int = 600

    def __post_init__(self) -> None:
        positive = {
            "context_token_budget": self.context_token_budget,
            "summary_trigger_tokens": self.summary_trigger_tokens,
            "recent_context_tokens": self.recent_context_tokens,
            "summary_max_output_tokens": self.summary_max_output_tokens,
        }
        if any(value <= 0 for value in positive.values()):
            raise ValueError("Context and summary token settings must be positive.")
        if self.summary_trigger_tokens > self.context_token_budget:
            raise ValueError(
                "SUMMARY_TRIGGER_TOKENS cannot exceed CONTEXT_TOKEN_BUDGET."
            )
        if self.recent_context_tokens > self.context_token_budget:
            raise ValueError(
                "RECENT_CONTEXT_TOKENS cannot exceed CONTEXT_TOKEN_BUDGET."
            )


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
        response_max_output_tokens=int(
            os.getenv("RESPONSE_MAX_OUTPUT_TOKENS", "1200")
        ),
        openai_timeout_seconds=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "60")),
        keyword_min_matches=int(os.getenv("KEYWORD_MIN_MATCHES", "2")),
        keyword_min_margin=int(os.getenv("KEYWORD_MIN_MARGIN", "1")),
        context_token_budget=int(os.getenv("CONTEXT_TOKEN_BUDGET", "8000")),
        summary_trigger_tokens=int(os.getenv("SUMMARY_TRIGGER_TOKENS", "6000")),
        recent_context_tokens=int(os.getenv("RECENT_CONTEXT_TOKENS", "3000")),
        summary_max_output_tokens=int(
            os.getenv("SUMMARY_MAX_OUTPUT_TOKENS", "600")
        ),
    )
