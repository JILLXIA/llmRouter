from __future__ import annotations

from typing import Any

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, SystemMessage

from llm_router.config import Settings
from llm_router.models import Intent, IntentResult
from llm_router.router import LLMRouter, RouterError, keyword_match


class StubRunnable:
    def __init__(self) -> None:
        self.result: object = IntentResult(intent=Intent.ANALYSIS, confidence=0.8)
        self.error: Exception | None = None
        self.calls: list[list[object]] = []

    def invoke(self, messages: list[object]) -> object:
        self.calls.append(messages)
        if self.error:
            raise self.error
        return self.result


class StubModel:
    def __init__(self, name: str) -> None:
        self.name = name
        self.chunks = [
            AIMessageChunk(content="A useful "),
            AIMessageChunk(
                content="answer",
                usage_metadata={
                    "input_tokens": 21,
                    "output_tokens": 9,
                    "total_tokens": 30,
                },
            ),
        ]
        self.error: Exception | None = None
        self.calls: list[list[object]] = []
        self.stream_kwargs: list[dict[str, object]] = []
        self.error_after_chunks: int | None = None
        self.structured = StubRunnable()
        self.structured_schema: object | None = None
        self.structured_method: str | None = None

    def with_structured_output(self, schema: object, *, method: str) -> StubRunnable:
        self.structured_schema = schema
        self.structured_method = method
        return self.structured

    def invoke(self, messages: list[object]) -> AIMessage:
        raise AssertionError("response generation must use stream(), not invoke()")

    def stream(
        self,
        messages: list[object],
        **kwargs: object,
    ) -> object:
        self.calls.append(messages)
        self.stream_kwargs.append(kwargs)
        if self.error and self.error_after_chunks is None:
            raise self.error
        for index, chunk in enumerate(self.chunks):
            if self.error and self.error_after_chunks == index:
                raise self.error
            yield chunk
        if self.error and self.error_after_chunks == len(self.chunks):
            raise self.error


class StubModelFactory:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.models: list[StubModel] = []

    def __call__(self, **kwargs: Any) -> StubModel:
        self.calls.append(kwargs)
        model = StubModel(kwargs["model"])
        self.models.append(model)
        return model


def make_router(**settings_overrides: Any) -> tuple[LLMRouter, StubModelFactory]:
    factory = StubModelFactory()
    settings = Settings(
        openai_api_key="test-key",
        intent_model="intent-model",
        high_quality_model="quality-model",
        balanced_model="balanced-model",
        economy_model="economy-model",
        **settings_overrides,
    )
    return LLMRouter(settings, model_factory=factory), factory


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("Implement a Python function", Intent.CODE_GENERATION),
        ("Debug this function traceback", Intent.CODE_ANALYSIS),
        ("Analyze the trade-offs and evidence", Intent.ANALYSIS),
        ("Summarize this report into key points", Intent.SUMMARIZATION),
        ("Write a creative detective story", Intent.CREATIVE_WRITING),
    ],
)
def test_clear_keywords_skip_the_intent_model(query: str, expected: Intent) -> None:
    router, factory = make_router()

    assert router.classify(query) == (expected, "keyword")
    assert factory.models[0].structured.calls == []


def test_weak_keyword_match_uses_the_intent_model() -> None:
    router, factory = make_router()

    assert router.classify("Compare Kafka and RabbitMQ") == (Intent.ANALYSIS, "llm")
    assert len(factory.models[0].structured.calls) == 1


def test_intent_failure_uses_keyword_candidate_or_general() -> None:
    router, factory = make_router()
    factory.models[0].structured.error = RuntimeError("temporary provider error")

    assert router.classify("Compare Kafka and RabbitMQ") == (
        Intent.ANALYSIS,
        "fallback",
    )
    assert router.classify("Hello there") == (Intent.GENERAL, "fallback")


def test_keyword_matching_is_case_insensitive() -> None:
    assert keyword_match("IMPLEMENT A PYTHON FUNCTION") == (
        Intent.CODE_GENERATION,
        True,
    )


@pytest.mark.parametrize(
    ("intent", "expected_model"),
    [
        (Intent.CODE_GENERATION, "quality-model"),
        (Intent.CODE_ANALYSIS, "quality-model"),
        (Intent.ANALYSIS, "balanced-model"),
        (Intent.CREATIVE_WRITING, "balanced-model"),
        (Intent.SUMMARIZATION, "economy-model"),
        (Intent.GENERAL, "economy-model"),
    ],
)
def test_model_routing(intent: Intent, expected_model: str) -> None:
    router, _ = make_router()

    assert router.model_for(intent) == expected_model


def test_chat_selects_model_and_builds_langchain_messages() -> None:
    router, factory = make_router(chat_history_messages=3)
    history = [
        {"role": "user", "content": "Old question"},
        {
            "role": "assistant",
            "content": "Old answer",
            "routing": {"internal": "not sent"},
        },
        {"role": "user", "content": "Recent question"},
    ]

    emitted: list[str] = []
    result = router.chat("Implement a Python endpoint", history, on_chunk=emitted.append)

    assert result.response == "A useful answer"
    assert result.intent == Intent.CODE_GENERATION
    assert result.classifier_source == "keyword"
    assert result.model == "quality-model"
    assert result.input_tokens == 21
    assert result.output_tokens == 9
    assert result.total_tokens == 30
    assert result.routing_metadata()["total_tokens"] == 30
    assert emitted == ["A useful ", "answer"]
    assert factory.models[1].stream_kwargs == [{"stream_usage": True}]

    sent = factory.models[1].calls[0]
    assert isinstance(sent[0], SystemMessage)
    assert isinstance(sent[1], AIMessage)
    assert sent[1].content == "Old answer"
    assert isinstance(sent[2], HumanMessage)
    assert sent[2].content == "Recent question"
    assert isinstance(sent[3], HumanMessage)
    assert sent[3].content == "Implement a Python endpoint"


def test_langchain_configuration_and_structured_schema() -> None:
    router, factory = make_router(
        response_max_output_tokens=321,
        openai_timeout_seconds=12,
    )

    router.chat("Implement a Python endpoint", [])

    assert factory.calls[0] == {
        "model": "intent-model",
        "model_provider": "openai",
        "api_key": "test-key",
        "timeout": 12,
        "max_tokens": 100,
        "reasoning_effort": "none",
        "use_responses_api": True,
    }
    assert factory.models[0].structured_schema is IntentResult
    assert factory.models[0].structured_method == "json_schema"
    assert factory.calls[1]["max_tokens"] == 321
    assert factory.calls[1]["reasoning_effort"] == "low"


def test_response_models_are_cached_by_name() -> None:
    router, factory = make_router()

    router.chat("Implement a Python function", [])
    router.chat("Build a Python class", [])

    assert [call["model"] for call in factory.calls] == [
        "intent-model",
        "quality-model",
    ]
    assert len(factory.models[1].calls) == 2


def test_empty_input_and_model_failures_have_safe_errors() -> None:
    router, factory = make_router()

    with pytest.raises(RouterError, match="Please enter a message"):
        router.chat("   ", [])

    router.chat("Implement a Python function", [])
    factory.models[1].error = RuntimeError("private provider detail")

    with pytest.raises(RouterError) as raised:
        router.chat("Build a Python class", [])

    assert str(raised.value) == (
        "The model request could not be completed. Please try again."
    )
    assert "private provider detail" not in str(raised.value)


def test_empty_model_response_is_rejected() -> None:
    router, factory = make_router()
    router.chat("Implement a Python function", [])
    factory.models[1].chunks = [AIMessageChunk(content="   ")]

    with pytest.raises(RouterError, match="could not be completed"):
        router.chat("Build a Python class", [])


def test_missing_usage_metadata_defaults_to_zero() -> None:
    router, factory = make_router()
    router.chat("Implement a Python function", [])
    factory.models[1].chunks = [AIMessageChunk(content="Answer without usage")]

    result = router.chat("Build a Python class", [])

    assert (
        result.input_tokens,
        result.output_tokens,
        result.total_tokens,
    ) == (0, 0, 0)


def test_stream_ignores_empty_chunks_and_reports_partial_failure() -> None:
    router, factory = make_router()
    router.chat("Implement a Python function", [])
    factory.models[1].chunks = [
        AIMessageChunk(content="Partial"),
        AIMessageChunk(content=" answer"),
    ]
    factory.models[1].error = RuntimeError("private stream failure")
    factory.models[1].error_after_chunks = 1
    emitted: list[str] = []

    with pytest.raises(RouterError, match="could not be completed"):
        router.chat("Build a Python class", [], on_chunk=emitted.append)

    assert emitted == ["Partial"]


def test_empty_metadata_chunk_is_not_emitted() -> None:
    router, factory = make_router()
    router.chat("Implement a Python function", [])
    factory.models[1].chunks = [
        AIMessageChunk(content=""),
        AIMessageChunk(
            content="Done",
            usage_metadata={
                "input_tokens": 3,
                "output_tokens": 1,
                "total_tokens": 4,
            },
        ),
    ]
    emitted: list[str] = []

    result = router.chat("Build a Python class", [], on_chunk=emitted.append)

    assert emitted == ["Done"]
    assert result.total_tokens == 4
