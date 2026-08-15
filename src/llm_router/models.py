from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Intent(str, Enum):
    CODE_GENERATION = "CODE_GENERATION"
    CODE_ANALYSIS = "CODE_ANALYSIS"
    ANALYSIS = "ANALYSIS"
    SUMMARIZATION = "SUMMARIZATION"
    CREATIVE_WRITING = "CREATIVE_WRITING"
    GENERAL = "GENERAL"


class IntentResult(BaseModel):
    """Structured result returned by the lightweight intent model."""

    model_config = ConfigDict(extra="forbid")

    intent: Intent
    confidence: float = Field(ge=0.0, le=1.0)


@dataclass(frozen=True)
class ConversationSummary:
    text: str
    summarized_through_message_id: int
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True)
class ChatResult:
    response: str
    intent: Intent
    classifier_source: Literal["keyword", "llm", "fallback"]
    model: str
    latency_ms: float
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    summary_update: ConversationSummary | None = None

    def routing_metadata(self) -> dict[str, str | int | float]:
        """Return routing and usage data stored with the assistant message."""

        return {
            "intent": self.intent.value,
            "classifier_source": self.classifier_source,
            "model": self.model,
            "latency_ms": self.latency_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
        }
