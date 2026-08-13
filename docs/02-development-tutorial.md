# Development Tutorial: Source-Required LLM Router

This tutorial implements only `Slack.AI LLM Router Platform.md`.

Priority rule:

- `P0 — Required`: complete before considering extensions.
- `P1 — Source extension`: explicitly mentioned in the source overview but not required by the detailed grading checklist.

The tutorial follows the nine P0 task parts. P1 is isolated at the end.

## 1. P0 Part 1 — Project initialization and configuration

### 1.1 Create the project

```bash
python -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Initial dependencies:

```text
fastapi
uvicorn[standard]
pydantic>=2
pydantic-settings
pyyaml
httpx
openai
anthropic
structlog
prometheus-client
python-dotenv
tiktoken
pytest
pytest-asyncio
pytest-cov
```

Pin tested versions before the final submission so installation is reproducible.

### 1.2 Build the source-aligned structure

```text
src/llm_router/
├── __init__.py
├── api.py
├── config.py
├── models.py
├── classifier.py
├── selector.py
├── router.py
├── inference.py
├── context.py
├── cache.py
├── providers/
├── logging_config.py
├── metrics.py
├── monitor.py
└── pipeline.py
```

Add `.gitignore` entries for:

```text
venv/
.env
__pycache__/
.pytest_cache/
.coverage
htmlcov/
logs/*.log
data/*
```

Document required environment-variable names in the setup guide without exposing their values.

### 1.3 Define configuration models

```python
from enum import Enum
from pydantic import BaseModel, Field


class RoutingStrategy(str, Enum):
    INTELLIGENT = "intelligent"
    ROUND_ROBIN = "round_robin"
    WEIGHTED = "weighted"
    COST_OPTIMIZED = "cost_optimized"
    LATENCY_OPTIMIZED = "latency_optimized"


class ModelConfig(BaseModel):
    name: str
    provider: str
    model_name: str
    enabled: bool = True
    query_types: list[str]
    priority: int = 0
    weight: float = Field(default=1.0, gt=0)
    cost_per_1k_tokens: float = Field(ge=0)
    avg_latency_ms: float = Field(gt=0)
    context_limit: int = Field(gt=0)


class RouterConfig(BaseModel):
    strategy: RoutingStrategy = RoutingStrategy.INTELLIGENT
    fallback_enabled: bool = True
    models: list[ModelConfig]


class InferenceConfig(BaseModel):
    timeout_seconds: float = Field(default=30, gt=0)
    max_retries: int = Field(default=2, ge=0)
    retry_base_seconds: float = Field(default=0.5, ge=0)


class CacheConfig(BaseModel):
    enabled: bool = True
    ttl_seconds: int = Field(default=300, gt=0)
    max_entries: int = Field(default=1000, gt=0)


class AppConfig(BaseModel):
    api_host: str = "0.0.0.0"
    api_port: int = Field(default=8000, ge=1, le=65535)
    log_level: str = "INFO"
    log_file: str = "logs/llm-router.log"
    router: RouterConfig
    inference: InferenceConfig
    cache: CacheConfig
```

### 1.4 Load YAML and environment keys

```python
import os
from pathlib import Path
import yaml


def load_config(path: Path) -> AppConfig:
    with path.open("r", encoding="utf-8") as file:
        raw = yaml.safe_load(file)
    return AppConfig.model_validate(raw)


def load_provider_keys() -> dict[str, str | None]:
    return {
        "openai": os.getenv("OPENAI_API_KEY"),
        "anthropic": os.getenv("ANTHROPIC_API_KEY"),
    }
```

Do not put secret values in `config.yaml` or return them from configuration logging.

### 1.5 Tests

- Valid YAML loads.
- Missing required model fields fail.
- Invalid strategy, negative cost, invalid port, and zero context limit fail.
- Missing provider keys do not break unit tests that use fake providers.
- Configuration serialization/logging does not reveal keys.

### P0 done when

The package imports, YAML validates, environment keys load separately, and configuration tests pass.

## 2. P0 Part 2 — Query classification

### 2.1 Define query/result models

```python
from enum import Enum
from pydantic import BaseModel, Field


class QueryType(str, Enum):
    CODE_GENERATION = "CODE_GENERATION"
    CODE_ANALYSIS = "CODE_ANALYSIS"
    ANALYSIS = "ANALYSIS"
    SUMMARIZATION = "SUMMARIZATION"
    CREATIVE_WRITING = "CREATIVE_WRITING"
    GENERAL = "GENERAL"


class ClassificationResult(BaseModel):
    query_type: QueryType
    confidence: float = Field(ge=0.0, le=1.0)
    keywords: list[str]
```

### 2.2 Create patterns

Use rule IDs/keywords rather than returning regex strings as keywords:

```python
RULES = {
    QueryType.CODE_GENERATION: [
        ("implement", r"\b(implement|create|generate|write)\b"),
        ("code-object", r"\b(code|function|class|script|api)\b"),
        ("language", r"\b(python|javascript|java|go|rust)\b"),
    ],
    QueryType.CODE_ANALYSIS: [
        ("analyze-code", r"\b(review|debug|explain|optimi[sz]e)\b"),
        ("code-object", r"\b(code|function|class|stack trace)\b"),
    ],
    QueryType.ANALYSIS: [
        ("analysis", r"\b(analy[sz]e|compare|evaluate|research|study)\b"),
    ],
    QueryType.SUMMARIZATION: [
        ("summary", r"\b(summari[sz]e|summary|condense|paraphrase|translate)\b"),
    ],
    QueryType.CREATIVE_WRITING: [
        ("creative", r"\b(story|poem|brainstorm|creative|blog|article)\b"),
    ],
}
```

### 2.3 Score every type

```python
class QueryClassifier:
    def classify(self, query: str) -> ClassificationResult:
        text = " ".join(query.lower().split())
        scored: dict[QueryType, tuple[float, list[str]]] = {}

        for query_type, rules in RULES.items():
            matched = [keyword for keyword, pattern in rules if re.search(pattern, text)]
            if matched:
                scored[query_type] = (len(matched) / len(rules), matched)

        if not scored:
            return ClassificationResult(
                query_type=QueryType.GENERAL,
                confidence=0.5,
                keywords=[],
            )

        best_type = max(
            scored,
            key=lambda item: (scored[item][0], -list(QueryType).index(item)),
        )
        score, keywords = scored[best_type]
        return ClassificationResult(
            query_type=best_type,
            confidence=min(max(score, 0.0), 1.0),
            keywords=keywords,
        )
```

This is a deterministic requirement implementation, not a trained probability model.

### 2.4 Mixed-query policy

For P0:

1. Score all query types.
2. Select the highest score.
3. Break ties with a documented fixed priority.
4. Return `GENERAL` when no type matches.

### 2.5 Tests

Create tests for:

- at least five examples for every type;
- uppercase/mixed punctuation;
- unmatched general conversation;
- a mixed code-analysis/code-generation query;
- very short input;
- confidence always between 0 and 1;
- returned keywords are actual matched features.

### P0 done when

All six types, edge cases, and mixed-query behavior are deterministic and tested.

## 3. P0 Part 3 — Model selection and routing

### 3.1 Candidate filtering

```python
def candidates_for(
    models: list[ModelConfig],
    query_type: QueryType,
    available_models: set[str] | None,
) -> list[ModelConfig]:
    candidates = [model for model in models if model.enabled]

    if available_models is not None:
        candidates = [model for model in candidates if model.name in available_models]

    return [
        model
        for model in candidates
        if query_type.value in model.query_types or "GENERAL" in model.query_types
    ]
```

Checking `is not None` is important: an explicitly empty availability set means no model is available.

### 3.2 Implement the five strategies

```python
class ModelSelector:
    def __init__(self, config: RouterConfig):
        self.config = config
        self._round_robin_index = 0

    def select(
        self,
        query_type: QueryType,
        available_models: set[str] | None = None,
    ) -> list[ModelConfig]:
        candidates = candidates_for(
            self.config.models,
            query_type,
            available_models,
        )
        if not candidates:
            raise NoAvailableModelError("No suitable model is available")

        ordered = self._order(candidates)
        return ordered if self.config.fallback_enabled else ordered[:1]
```

Ordering logic:

- Intelligent: descending `priority`.
- Round robin: rotate primary, preserve remaining candidates as fallback order.
- Weighted: select primary with `random.choices`, then append remaining candidates.
- Cost optimized: ascending `cost_per_1k_tokens`.
- Latency optimized: ascending `avg_latency_ms`.

Inject/seed the random generator in tests.

### 3.3 Fallback

The selector returns an ordered list. The router attempts the primary, then alternatives only after retry rules permit it.

```python
for model in route_plan:
    try:
        return await inference.generate(query, model)
    except RetryableProviderError:
        logger.warning("model_failed", model=model.name)
        continue
raise AllModelsFailedError("All configured models failed")
```

The inference engine handles same-model retry; the router handles model fallback.

### 3.4 Tests

- Every strategy chooses the correct primary.
- Disabled and unavailable models are excluded.
- Unsupported query types are excluded unless the model supports `GENERAL`.
- Empty availability raises a controlled error.
- Fallback is ordered and can be disabled.
- Weighted selection distribution is tested with a fixed seed/tolerance.
- Round robin wraps correctly.

### P0 done when

All strategies and complete-failure behavior pass tests.

## 4. P0 Part 4 — Inference engine, context, and cache

### 4.1 Canonical inference contracts

```python
class InferenceRequest(BaseModel):
    query: str
    model_name: str
    max_output_tokens: int = 1000
    stream: bool = False


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class InferenceResult(BaseModel):
    response: str
    model: str
    usage: Usage
    latency_ms: float
    timestamp: datetime
```

### 4.2 Provider interface and factory

```python
class LLMProvider(Protocol):
    async def generate(self, request: InferenceRequest) -> InferenceResult: ...

    def stream(
        self, request: InferenceRequest
    ) -> AsyncIterator[str]: ...

    async def health_check(self) -> bool: ...


class ProviderFactory:
    def __init__(self, providers: dict[str, LLMProvider]):
        self.providers = providers

    def get(self, provider: str) -> LLMProvider:
        try:
            return self.providers[provider]
        except KeyError as error:
            raise ProviderConfigurationError(provider) from error
```

Build one provider client during application startup, not on every query.

### 4.3 OpenAI adapter

Responsibilities:

1. Translate `InferenceRequest` to the current official SDK request.
2. Use the configured provider model ID.
3. Set the configured timeout.
4. Support async non-streaming and streaming.
5. Extract response text and token usage.
6. Normalize provider errors.

Do not copy a provider model ID from the requirement examples without verifying it is available to your account. Put it in `config.yaml`.

### 4.4 Anthropic adapter

Implement the same contract, while translating Anthropic-specific message/usage/stop behavior internally. The router must never depend on Anthropic SDK response classes.

### 4.5 Error taxonomy and retry

```python
class ProviderError(Exception):
    retryable = False


class ProviderTimeoutError(ProviderError):
    retryable = True


class ProviderRateLimitError(ProviderError):
    retryable = True


class ProviderServerError(ProviderError):
    retryable = True


class ProviderAuthenticationError(ProviderError):
    retryable = False
```

Retry with exponential backoff up to `max_retries`. Retry only normalized retryable errors. Measure total attempt latency.

### 4.6 Provider streaming

P0 streaming is an inference capability. Test that adapters:

- yield text chunks in order;
- handle normal completion;
- close resources;
- surface a mid-stream error;
- aggregate chunks when the `/query` endpoint needs a normal JSON response.

The source does not require a public SSE endpoint.

### 4.7 Token counting and context compression

```python
class ContextManager:
    def count_tokens(self, text: str, model: ModelConfig) -> int:
        ...

    async def fit(self, text: str, model: ModelConfig) -> str:
        token_count = self.count_tokens(text, model)
        if token_count <= model.context_limit:
            return text
        return await self.compress(text, model)
```

P0 compression options:

- Deterministic truncation that preserves the beginning/end according to configuration.
- LLM summarization if you choose, with explicit timeout/error handling.

Test the exact boundary, over-limit input, Unicode, and compression failure.

### 4.8 Response cache

```python
class CacheEntry(BaseModel):
    result: InferenceResult
    expires_at: float


class ResponseCache:
    def get(self, key: str) -> InferenceResult | None: ...
    def set(self, key: str, value: InferenceResult) -> None: ...
```

Build a stable key from query, model, and relevant generation settings. P0 uses an in-memory bounded TTL cache.

Tests:

- hit returns the same result without calling provider;
- miss calls provider;
- expired entry is ignored;
- different query/model/settings produce different keys;
- failed responses are not cached.

### 4.9 Shared provider tests

Create a fake provider and a contract test suite. Run translation/error/stream tests for OpenAI and Anthropic with mocked SDK/network responses. Live tests are optional and should use very small output limits.

### P0 done when

Both provider adapters, retry, usage, streaming, token limits, compression, and cache pass tests.

## 5. P0 Part 5 — FastAPI service

### 5.1 Pydantic API models

```python
class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=10_000)
    user_id: str | None = Field(default=None, max_length=100)
    session_id: str | None = Field(default=None, max_length=100)


class QueryResponse(BaseModel):
    response: str
    model_used: str
    query_type: QueryType
    tokens_used: int
    latency_ms: float
    timestamp: datetime
```

### 5.2 Application lifespan

Create the configuration, provider clients, router, queue consumer, and health monitor at startup. Close them at shutdown.

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    services = await build_services()
    app.state.services = services
    await services.start()
    try:
        yield
    finally:
        await services.stop()
```

### 5.3 Implement the five endpoints

```python
@app.post("/query", response_model=QueryResponse)
async def query(body: QueryRequest, request: Request) -> QueryResponse:
    return await request.app.state.services.router.route(body)


@app.get("/models")
async def models(request: Request) -> ModelsResponse:
    return request.app.state.services.model_service.list_models()


@app.get("/stats")
async def stats(request: Request) -> StatsResponse:
    return request.app.state.services.pipeline.get_stats()


@app.get("/health")
async def health(request: Request) -> HealthResponse:
    return await request.app.state.services.monitor.status()
```

Mount the Prometheus ASGI/response handler at `/metrics`.

### 5.4 Unified errors

```python
class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorBody
```

Map validation, no model, provider timeout, provider failure, and internal error to appropriate statuses. Do not return raw exception text for unknown errors.

### 5.5 Tests

- Valid query response.
- Empty/too-long query.
- Oversized user/session ID.
- Router/provider controlled errors.
- Models include availability.
- Stats calculations are returned.
- Health includes components and uptime.
- Metrics use Prometheus content type.

### P0 done when

All five endpoints match [the API specification](04-api-specification.md) and integration tests pass.

## 6. P0 Part 6 — Structured logging and Prometheus metrics

### 6.1 Logging context

Generate a request ID in middleware and bind:

- `request_id`;
- `user_id` when present;
- endpoint;
- selected model/provider;
- query type;
- tokens and latency at completion;
- normalized error type on failure.

Never log `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`.

### 6.2 Console and file handlers

Configure both because the source explicitly requires them. Ensure `logs/` exists or create it safely at startup.

Example JSON log:

```json
{
  "timestamp": "2026-08-10T18:42:17Z",
  "level": "INFO",
  "event": "query_completed",
  "request_id": "req-123",
  "user_id": "user-123",
  "model": "openai-primary",
  "query_type": "CODE_GENERATION",
  "tokens": 228,
  "latency_ms": 1363.2
}
```

### 6.3 Required metrics

```python
REQUESTS = Counter(
    "llm_router_requests_total",
    "Total API requests",
    ["method", "endpoint", "status"],
)
LATENCY = Histogram(
    "llm_router_request_latency_seconds",
    "Request latency",
    ["endpoint"],
)
TOKENS = Counter(
    "llm_router_tokens_used_total",
    "Tokens used",
    ["model", "token_type"],
)
SELECTIONS = Counter(
    "llm_router_model_selections_total",
    "Model selections",
    ["model", "query_type", "strategy"],
)
ERRORS = Counter(
    "llm_router_errors_total",
    "Errors",
    ["error_type", "model"],
)
```

Do not use raw query/user/session/request values as Prometheus labels.

### 6.4 Tests

- Each log level can be emitted.
- Request/user context appears where expected.
- API-key canary does not appear in logs.
- Each required metric changes after its scenario.
- `/metrics` contains the metric names.

### P0 done when

Logs work in console and file, and all five metric families are exposed.

## 7. P0 Part 7 — Health monitoring and alerting

### 7.1 Health model

```python
class ComponentState(str, Enum):
    UP = "up"
    DOWN = "down"
    UNKNOWN = "unknown"


class HealthResponse(BaseModel):
    status: str
    components: dict[str, ComponentState]
    models_available: int
    uptime_seconds: float
```

### 7.2 Provider checks

Run bounded health checks for OpenAI and Anthropic. Do not let one exception fail the whole endpoint; translate it to `down` and calculate overall status.

Suggested overall rules:

- `healthy`: API up and all configured providers up.
- `degraded`: API up and at least one usable provider up.
- `unhealthy`: no usable provider.

### 7.3 Alert rules

```python
class AlertRule(BaseModel):
    name: str
    metric: Literal["latency_ms", "error_rate"]
    threshold: float
    window_seconds: int


class Alert(BaseModel):
    id: str
    rule: str
    message: str
    created_at: datetime
    status: Literal["active", "resolved"]
```

Define a notifier protocol and at least one implementation such as log notifier:

```python
class AlertNotifier(Protocol):
    async def send(self, alert: Alert) -> None: ...
```

Store alert history in memory or a local JSON/data store for P0.

### 7.4 Tests

- All providers up.
- One provider down produces degraded status.
- All providers down produces unhealthy status.
- Latency threshold creates one alert.
- Error-rate threshold creates one alert.
- Notifier receives alert.
- Alert appears in history and can resolve.

### P0 done when

`/health`, threshold rules, notifier, and history meet Part 7.

## 8. P0 Part 8 — Async query logging and statistics

### 8.1 Event model

```python
class QueryLogRecord(BaseModel):
    request_id: str
    query: str
    response: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    estimated_cost: float
    timestamp: datetime
```

The source asks to log query/response details. Still exclude provider API keys and exception secrets.

### 8.2 Queue and consumer

```python
class QueryPipeline:
    def __init__(self, max_size: int = 1000):
        self.queue: asyncio.Queue[QueryLogRecord] = asyncio.Queue(maxsize=max_size)
        self.records: list[QueryLogRecord] = []
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._consume())

    async def publish(self, record: QueryLogRecord) -> None:
        await self.queue.put(record)

    async def _consume(self) -> None:
        while True:
            record = await self.queue.get()
            try:
                self.records.append(record)
            finally:
                self.queue.task_done()
```

Add a stop signal and flush behavior before production use. Keep the queue bounded.

### 8.3 Statistics

```python
class StatsResponse(BaseModel):
    total_requests: int
    model_usage: dict[str, int]
    total_tokens: int
    estimated_cost: float
    avg_latency_ms: float
```

Calculate from stored records or maintain running aggregates. Define the pricing basis in model configuration.

### 8.4 Tests

- Publish does not perform the storage operation directly.
- Consumer processes records in order.
- Buffer limit behavior is explicit.
- Shutdown flushes queued records.
- Per-model count, tokens, cost, and average latency are correct.
- No records returns zeros, not division-by-zero.

### P0 done when

The router enqueues every successful query and `/stats` matches known test records.

## 9. P0 Part 9 — Docker and Docker Compose

### 9.1 Dockerfile

Required behavior:

- Install Python dependencies.
- Copy application/config files.
- Create `logs/` and `data/` paths.
- Expose port 8000.
- Start Uvicorn.
- Read keys/settings from environment at runtime.

Example structure:

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY config ./config
RUN mkdir -p /app/logs /app/data

ENV PYTHONPATH=/app/src
EXPOSE 8000
CMD ["uvicorn", "llm_router.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

Do not copy `.env` into the image.

### 9.2 Docker Compose

```yaml
services:
  llm-router:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - ./logs:/app/logs
      - ./data:/app/data
      - ./config:/app/config:ro
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 30s
      timeout: 5s
      retries: 3
```

### 9.3 Deployment guide

Document:

```bash
# Ensure provider keys are configured in the existing ignored .env file
docker compose up --build -d
curl http://localhost:8000/health
curl http://localhost:8000/models
```

Troubleshooting topics:

- missing/invalid provider keys;
- configuration validation error;
- port 8000 conflict;
- provider timeout/rate limit;
- unwritable log/data volume;
- unhealthy Compose service.

### 9.4 Tests

- Image builds.
- Container starts.
- `/health` succeeds or clearly reports configured provider failure.
- Query using mocked/test provider in test profile succeeds.
- Logs/data volumes receive expected output.

### P0 done when

The Compose commands and troubleshooting guide work from a clean setup.

## 10. P0 test and submission requirements

Run:

```bash
pytest --cov=src/llm_router --cov-report=term-missing --cov-report=html
```

Required submission artifacts:

- Complete source and tests.
- README with project description, installation, configuration, run, API examples, and architecture.
- Test report with at least 70% coverage.
- API documentation for all five endpoints.
- Docker/Compose deployment and troubleshooting guide.

Do not use coverage alone as proof. Each required failure/fallback/API scenario needs an assertion.

## 11. P1 — Only after P0 is complete

### 11.1 vLLM adapter

Add a provider behind `LLMProvider`. It must pass the same provider contract tests and must not change routing/API contracts.

### 11.2 Kafka and ClickHouse

Replace/extend the P0 `asyncio.Queue` consumer:

```text
Router -> Kafka producer -> Kafka consumer -> ClickHouse
```

Keep `QueryLogRecord` versioned and preserve `/stats` output.

### 11.3 Kubernetes and CI/CD

Package the already passing Docker image for Kubernetes and automate existing tests/builds. These tasks must not delay the source-required Docker Compose release.

## 12. Final priority checklist

### P0

- [ ] Configuration and project structure
- [ ] Regex classifier and six query types
- [ ] Five routing strategies and fallback
- [ ] OpenAI and Anthropic adapters
- [ ] Provider streaming/retry/usage
- [ ] Token counting and context compression
- [ ] Response cache
- [ ] `/query`, `/models`, `/stats`, `/health`, `/metrics`
- [ ] Structured console/file logs
- [ ] Five Prometheus metric families
- [ ] Health checks and alert interface/history
- [ ] Async query log buffer and statistics
- [ ] Docker, Compose, deployment/troubleshooting docs
- [ ] Complete code, README, API docs, and at least 70% coverage

### P1

- [ ] vLLM
- [ ] Kafka
- [ ] ClickHouse
- [ ] Kubernetes
- [ ] CI/CD

Start no P1 checkbox until all P0 checkboxes are complete.
