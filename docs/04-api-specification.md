# Source-Required API Specification

Status: review contract  
Scope: only HTTP APIs required by `Slack.AI LLM Router Platform.md`

## 1. API priority

All five endpoints are `P0 — Required`.

| Priority | Method | Path | Source purpose |
|---|---|---|---|
| `P0` | `POST` | `/query` | Route a query to an LLM and return the response |
| `P0` | `GET` | `/models` | List available models |
| `P0` | `GET` | `/stats` | Return query/model/token/cost/latency statistics |
| `P0` | `GET` | `/health` | Return detailed system/provider health |
| `P0` | `GET` | `/metrics` | Expose the five Prometheus metric families |

There are no other required public APIs. Do not implement versioned/admin/project/key/policy/catalog/route-preview/request-inspection/feedback APIs in the current phase.

Provider streaming is a P0 internal inference capability; the source does not require a public SSE endpoint.

## 2. Common conventions

### 2.1 Content types

- JSON request: `Content-Type: application/json`
- JSON response: `Content-Type: application/json`
- Metrics response: Prometheus text exposition content type
- UTF-8 text

### 2.2 Request IDs

Generate one request ID per API call for structured logging and error correlation. A client may send an optional bounded `X-Request-ID`; otherwise the server generates one.

Successful `/query` follows the exact source response fields and does not need to return the request ID. Error responses return it for debugging correlation.

### 2.3 Timestamp

Use RFC 3339 UTC:

```text
2026-08-10T18:42:17.486Z
```

### 2.4 Unified error envelope

```json
{
  "error": {
    "code": "no_available_model",
    "message": "No configured model is currently available.",
    "request_id": "req-123"
  }
}
```

Validation error:

```json
{
  "error": {
    "code": "validation_error",
    "message": "The request payload is invalid.",
    "request_id": "req-123",
    "details": [
      {
        "field": "query",
        "message": "String should have at least 1 character."
      }
    ]
  }
}
```

Do not expose provider API keys, stack traces, or raw unexpected exception text.

### 2.5 Status codes

| HTTP | Usage |
|---:|---|
| `200` | Successful endpoint response |
| `422` | Pydantic request validation failure |
| `429` | Provider rate limit after retry/fallback cannot complete |
| `500` | Unexpected internal failure |
| `502` | Provider returned an unusable response/failure |
| `503` | No configured model/provider is available |
| `504` | Provider timeout after retries/fallback |

## 3. Query API

### `POST /query` — P0

Routes one query through classification, model selection, inference, usage measurement, logging, metrics, and the async data pipeline.

### 3.1 Input payload

```json
{
  "query": "Help me write a Python function to calculate Fibonacci",
  "user_id": "user_123",
  "session_id": "sess_abc"
}
```

| Field | Type | Required | Validation |
|---|---|---:|---|
| `query` | string | Yes | 1–10,000 characters |
| `user_id` | string or null | No | Maximum 100 characters |
| `session_id` | string or null | No | Maximum 100 characters |

Minimal valid request:

```json
{
  "query": "Hello, how are you?"
}
```

Unknown fields should be rejected so spelling mistakes do not silently pass.

### 3.2 Successful output — `200`

```json
{
  "response": "Here's an iterative Python Fibonacci function:\n\ndef fibonacci(n: int) -> int:\n    if n < 0:\n        raise ValueError('n must be non-negative')\n    a, b = 0, 1\n    for _ in range(n):\n        a, b = b, a + b\n    return a",
  "model_used": "openai-primary",
  "query_type": "CODE_GENERATION",
  "tokens_used": 350,
  "latency_ms": 1200.5,
  "timestamp": "2026-08-10T18:42:17.486Z"
}
```

| Field | Type | Meaning |
|---|---|---|
| `response` | string | Final generated text |
| `model_used` | string | Configured model name selected by router |
| `query_type` | enum | One of the six source query types |
| `tokens_used` | integer | Total input plus output tokens |
| `latency_ms` | number | End-to-end route/inference latency in milliseconds |
| `timestamp` | string | Completion timestamp in UTC |

### 3.3 Validation failure — `422`

Request:

```json
{
  "query": "",
  "user_id": "user_123"
}
```

Response:

```json
{
  "error": {
    "code": "validation_error",
    "message": "The request payload is invalid.",
    "request_id": "req-124",
    "details": [
      {
        "field": "query",
        "message": "String should have at least 1 character."
      }
    ]
  }
}
```

### 3.4 Provider fallback behavior

If the primary model fails with a retryable error:

1. Apply the configured same-provider retry policy.
2. If retries fail and fallback is enabled, try the next selector model.
3. Return the successful fallback model in `model_used`.
4. If every model fails, return a controlled `502`, `503`, or `504` response.

Example complete failure — `503`:

```json
{
  "error": {
    "code": "no_available_model",
    "message": "No configured model is currently available.",
    "request_id": "req-125"
  }
}
```

### 3.5 Context and cache behavior

These do not add request fields:

- The context manager counts tokens and compresses an overlong query before inference.
- The response cache may return a previous unexpired result for the same effective query/model settings.
- The response shape remains identical.
- Logs/metrics/pipeline record the final model, usage, and latency.

## 4. Models API

### `GET /models` — P0

No request body.

Example request:

```http
GET /models
```

Successful output — `200`:

```json
{
  "models": [
    {
      "name": "openai-primary",
      "provider": "openai",
      "model_name": "provider-model-id",
      "enabled": true,
      "available": true,
      "query_types": [
        "CODE_GENERATION",
        "CODE_ANALYSIS",
        "GENERAL"
      ],
      "priority": 100,
      "cost_per_1k_tokens": 0.01,
      "avg_latency_ms": 900.0
    },
    {
      "name": "anthropic-primary",
      "provider": "anthropic",
      "model_name": "provider-model-id",
      "enabled": true,
      "available": false,
      "query_types": [
        "ANALYSIS",
        "SUMMARIZATION",
        "CREATIVE_WRITING",
        "GENERAL"
      ],
      "priority": 90,
      "cost_per_1k_tokens": 0.008,
      "avg_latency_ms": 850.0
    }
  ],
  "total": 2,
  "available": 1,
  "routing_strategy": "intelligent"
}
```

The model IDs, price values, and latency values above are structural examples. Load actual configured values from `config.yaml`.

Do not return provider API keys.

## 5. Statistics API

### `GET /stats` — P0

No request body. It returns statistics accumulated by the async query pipeline.

Example request:

```http
GET /stats
```

Successful output — `200`:

```json
{
  "total_requests": 10000,
  "model_usage": {
    "openai-primary": 5000,
    "anthropic-primary": 5000
  },
  "total_tokens": 2500000,
  "estimated_cost": 75.5,
  "avg_latency_ms": 850.3
}
```

| Field | Type | Calculation |
|---|---|---|
| `total_requests` | integer | Count of completed logged query records |
| `model_usage` | object | Completed request count per configured model |
| `total_tokens` | integer | Sum of total tokens |
| `estimated_cost` | number | Sum using model-configured token cost |
| `avg_latency_ms` | number | Arithmetic mean query latency |

Empty output before any queries:

```json
{
  "total_requests": 0,
  "model_usage": {},
  "total_tokens": 0,
  "estimated_cost": 0.0,
  "avg_latency_ms": 0.0
}
```

## 6. Health API

### `GET /health` — P0

No request body. Returns detailed API/provider status and uptime.

Healthy/degraded example — `200`:

```json
{
  "status": "degraded",
  "components": {
    "api": "up",
    "openai": "up",
    "anthropic": "down"
  },
  "models_available": 1,
  "uptime_seconds": 86400.5
}
```

Overall status rules:

| Status | Rule |
|---|---|
| `healthy` | API and all enabled providers are up |
| `degraded` | API is up and at least one usable provider is up |
| `unhealthy` | No usable provider is available |

Unhealthy example — `503`:

```json
{
  "status": "unhealthy",
  "components": {
    "api": "up",
    "openai": "down",
    "anthropic": "down"
  },
  "models_available": 0,
  "uptime_seconds": 86430.2
}
```

Provider checks must use a bounded timeout. The response must not contain provider exception bodies or keys.

## 7. Metrics API

### `GET /metrics` — P0

No request body. Response is Prometheus text, not JSON.

```text
# HELP llm_router_requests_total Total API requests.
# TYPE llm_router_requests_total counter
llm_router_requests_total{method="POST",endpoint="/query",status="200"} 1523

# HELP llm_router_request_latency_seconds Request latency.
# TYPE llm_router_request_latency_seconds histogram
llm_router_request_latency_seconds_bucket{endpoint="/query",le="0.1"} 1200

# HELP llm_router_tokens_used_total Tokens used by model and token type.
# TYPE llm_router_tokens_used_total counter
llm_router_tokens_used_total{model="openai-primary",token_type="total"} 452000

# HELP llm_router_model_selections_total Model selection count.
# TYPE llm_router_model_selections_total counter
llm_router_model_selections_total{model="openai-primary",query_type="CODE_GENERATION",strategy="intelligent"} 731

# HELP llm_router_errors_total Error count.
# TYPE llm_router_errors_total counter
llm_router_errors_total{error_type="provider_timeout",model="openai-primary"} 12
```

Required metric families:

1. Request counter.
2. Request latency histogram.
3. Token counter.
4. Model selection counter.
5. Error counter.

Do not use raw request ID, user ID, session ID, query, or response as labels.

## 8. Pydantic schema structure

```python
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field


class QueryType(str, Enum):
    CODE_GENERATION = "CODE_GENERATION"
    CODE_ANALYSIS = "CODE_ANALYSIS"
    ANALYSIS = "ANALYSIS"
    SUMMARIZATION = "SUMMARIZATION"
    CREATIVE_WRITING = "CREATIVE_WRITING"
    GENERAL = "GENERAL"


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=10_000)
    user_id: str | None = Field(default=None, max_length=100)
    session_id: str | None = Field(default=None, max_length=100)


class QueryResponse(BaseModel):
    response: str
    model_used: str
    query_type: QueryType
    tokens_used: int = Field(ge=0)
    latency_ms: float = Field(ge=0)
    timestamp: datetime


class ModelInfo(BaseModel):
    name: str
    provider: str
    model_name: str
    enabled: bool
    available: bool
    query_types: list[QueryType]
    priority: int
    cost_per_1k_tokens: float
    avg_latency_ms: float


class ModelsResponse(BaseModel):
    models: list[ModelInfo]
    total: int
    available: int
    routing_strategy: str


class StatsResponse(BaseModel):
    total_requests: int
    model_usage: dict[str, int]
    total_tokens: int
    estimated_cost: float
    avg_latency_ms: float


class HealthResponse(BaseModel):
    status: str
    components: dict[str, str]
    models_available: int
    uptime_seconds: float
```

## 9. FastAPI route structure

```text
src/llm_router/
├── api.py          # five route definitions and error handlers
├── models.py       # API/domain Pydantic models
├── router.py       # /query use case
├── monitor.py      # /health service
├── pipeline.py     # /stats service
└── metrics.py      # /metrics instruments/handler
```

Example `/query` handler:

```python
@app.post("/query", response_model=QueryResponse)
async def route_query(request: QueryRequest) -> QueryResponse:
    return await services.router.route(request)
```

Classification, model selection, provider retry/fallback, caching, and pipeline calculations belong in their services, not inside the route function.

## 10. API test checklist

### `POST /query`

- [ ] Minimal valid query.
- [ ] Query with user/session IDs.
- [ ] Each query type.
- [ ] Primary provider success.
- [ ] Retry then success.
- [ ] Primary failure then fallback success.
- [ ] All providers fail.
- [ ] Cache hit and miss.
- [ ] Context compression.
- [ ] Empty/too-long query.
- [ ] Too-long user/session ID.
- [ ] Unknown field rejection.

### `GET /models`

- [ ] Enabled/disabled models.
- [ ] Available/unavailable state.
- [ ] Active strategy.
- [ ] No API keys in response.

### `GET /stats`

- [ ] Empty statistics.
- [ ] Known per-model records.
- [ ] Token/cost/average math.
- [ ] Async consumer records visible after flush/wait.

### `GET /health`

- [ ] All providers up.
- [ ] One provider down/degraded.
- [ ] All providers down/unhealthy.
- [ ] Uptime increases.
- [ ] Provider exception details are hidden.

### `GET /metrics`

- [ ] Prometheus content type.
- [ ] All five metric families.
- [ ] Metrics change after query/error scenarios.
- [ ] No raw user/session/query/response labels.

## 11. Final API scope confirmation

### P0 — implement now

- [ ] `POST /query`
- [ ] `GET /models`
- [ ] `GET /stats`
- [ ] `GET /health`
- [ ] `GET /metrics`

### Do not implement now

- `/v1/generate`
- `/livez` or `/readyz`
- route preview
- request inspection
- feedback
- project/key/policy/catalog/audit APIs
- public SSE endpoint
- OpenAI-compatible public endpoints

This five-endpoint contract is the complete current public API scope.
