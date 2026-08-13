"""The complete keyword -> intent -> model -> response flow."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Mapping, Sequence
from time import perf_counter
from typing import Any, Literal

from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from llm_router.config import Settings
from llm_router.models import ChatResult, Intent, IntentResult

logger = logging.getLogger(__name__)

INTENT_PROMPT = """Classify the user's message into exactly one intent:
CODE_GENERATION, CODE_ANALYSIS, ANALYSIS, SUMMARIZATION, CREATIVE_WRITING, or GENERAL.
Return only the requested structured result. Do not answer the message.
"""

CHAT_PROMPT = """You are a helpful assistant. Answer the user's request directly.
Use conversation history when relevant. Never mention internal model routing.
"""

# Each matching pattern adds one point to an intent. Keeping the rules together makes
# them easy to review and tune without reading the Streamlit or LangChain code.
KEYWORD_PATTERNS: dict[Intent, tuple[str, ...]] = {
    Intent.CODE_GENERATION: (
        r"\b(implement|create|generate|build|refactor|code)\b",
        r"\b(function|class|script|api|endpoint|component)\b",
        r"\b(python|javascript|typescript|java|golang|go|rust|c\+\+|sql)\b",
    ),
    Intent.CODE_ANALYSIS: (
        r"\b(debug|review|explain|optimi[sz]e|diagnose)\b",
        r"\b(code|function|class|method|query)\b",
        r"\b(error|exception|traceback|bug|deadlock|failure)\b",
    ),
    Intent.ANALYSIS: (
        r"\b(analy[sz]e|compare|evaluate|research|investigate)\b",
        r"\b(trade[- ]?offs?|pros and cons|advantages|disadvantages)\b",
        r"\b(root cause|why did|impact|evidence)\b",
    ),
    Intent.SUMMARIZATION: (
        r"\b(summari[sz]e|condense|paraphrase|translate)\b",
        r"\b(summary|key points|tl;?dr|bullet points?)\b",
        r"\b(text|article|report|document|transcript)\b",
    ),
    Intent.CREATIVE_WRITING: (
        r"\b(write|create|brainstorm|draft)\b",
        r"\b(story|poem|novel|screenplay|blog post|article|marketing copy)\b",
        r"\b(creative|fiction|character|plot|slogan)\b",
    ),
}

ClassifierSource = Literal["keyword", "llm", "fallback"]
ModelFactory = Callable[..., Any]


class RouterError(Exception):
    """Safe error that can be shown in the Streamlit UI."""


# use keyword_match to check the user intent
def keyword_match(
    query: str,
    *,
    min_matches: int = 2,
    min_margin: int = 1,
) -> tuple[Intent | None, bool]:
    scores = {
        intent: sum(
            bool(re.search(pattern, query, re.IGNORECASE)) for pattern in patterns
        )
        for intent, patterns in KEYWORD_PATTERNS.items()
    }
    ranked = sorted(scores, key=lambda intent: scores[intent], reverse=True)
    candidate = ranked[0]
    top_score = scores[candidate]
    second_score = scores[ranked[1]]

    if top_score == 0:
        return None, False

    confident = (
        top_score >= min_matches and top_score - second_score >= min_margin
    )
    return candidate, confident


class LLMRouter:
    """Classify a message, choose an OpenAI model, and generate its response."""

    def __init__(
        self,
        settings: Settings,
        *,
        model_factory: ModelFactory = init_chat_model,
    ) -> None:
        self.settings = settings
        self._model_factory = model_factory
        self._models: dict[str, Any] = {}
        self._routes = {
            Intent.CODE_GENERATION: settings.high_quality_model,
            Intent.CODE_ANALYSIS: settings.high_quality_model,
            Intent.ANALYSIS: settings.balanced_model,
            Intent.CREATIVE_WRITING: settings.balanced_model,
            Intent.SUMMARIZATION: settings.economy_model,
            Intent.GENERAL: settings.economy_model,
        }

        intent_model = self._new_model(
            settings.intent_model,
            max_tokens=100,
            reasoning_effort="none",
        )
        self._intent_model = intent_model.with_structured_output(
            IntentResult,
            method="json_schema",
        )

    def classify(self, query: str) -> tuple[Intent, ClassifierSource]:
        """Use keywords when clear; otherwise ask the lightweight model."""
        candidate, confident = keyword_match(
            query,
            min_matches=self.settings.keyword_min_matches,
            min_margin=self.settings.keyword_min_margin,
        )
        if confident and candidate:
            return candidate, "keyword"

        try:
            result = self._intent_model.invoke(
                [SystemMessage(content=INTENT_PROMPT), HumanMessage(content=query)]
            )
            parsed = (
                result
                if isinstance(result, IntentResult)
                else IntentResult.model_validate(result)
            )
            return parsed.intent, "llm"
        except Exception as error:
            logger.warning(
                "intent_classification_failed error_type=%s", type(error).__name__
            )
            return candidate or Intent.GENERAL, "fallback"

    def model_for(self, intent: Intent) -> str:
        return self._routes[intent]

    def chat(
        self,
        user_message: str,
        history: Sequence[Mapping[str, Any]],
    ) -> ChatResult:
        query = user_message.strip()
        if not query:
            raise RouterError("Please enter a message before sending.")

        started = perf_counter()
        intent, source = self.classify(query)
        model_name = self.model_for(intent)
        messages = self._chat_messages(history, query)

        try:
            response = self._response_model(model_name).invoke(messages)
            answer = response.text.strip()
            if not answer:
                raise ValueError("empty model response")
        except Exception as error:
            logger.error(
                "response_generation_failed model=%s error_type=%s",
                model_name,
                type(error).__name__,
            )
            raise RouterError(
                "The model request could not be completed. Please try again."
            ) from error

        latency_ms = (perf_counter() - started) * 1_000
        logger.info(
            "chat_completed intent=%s source=%s model=%s latency_ms=%.2f",
            intent.value,
            source,
            model_name,
            latency_ms,
        )
        return ChatResult(answer, intent, source, model_name, latency_ms)

    def _chat_messages(
        self,
        history: Sequence[Mapping[str, Any]],
        query: str,
    ) -> list[SystemMessage | HumanMessage | AIMessage]:
        history_slots = max(self.settings.chat_history_messages - 1, 0)
        recent = list(history[-history_slots:]) if history_slots else []
        messages: list[SystemMessage | HumanMessage | AIMessage] = [
            SystemMessage(content=CHAT_PROMPT)
        ]

        for item in recent:
            content = str(item.get("content", ""))
            if item.get("role") == "user":
                messages.append(HumanMessage(content=content))
            elif item.get("role") == "assistant":
                messages.append(AIMessage(content=content))

        messages.append(HumanMessage(content=query))
        return messages

    def _new_model(
        self,
        model: str,
        *,
        max_tokens: int,
        reasoning_effort: str,
    ) -> Any:
        return self._model_factory(
            model=model,
            model_provider="openai",
            api_key=self.settings.openai_api_key,
            timeout=self.settings.openai_timeout_seconds,
            max_tokens=max_tokens,
            reasoning_effort=reasoning_effort,
            use_responses_api=True,
        )

    def _response_model(self, model: str) -> Any:
        if model not in self._models:
            self._models[model] = self._new_model(
                model,
                max_tokens=self.settings.response_max_output_tokens,
                reasoning_effort="low",
            )
        return self._models[model]
