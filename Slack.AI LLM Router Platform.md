# Slack.AI LLM Router Platform - Complete Project

## Project Background and Objectives

In modern AI applications, different large language models (LLMs) have their own strengths and weaknesses. Some models excel at code generation, while others perform better at analysis or creative tasks. Choosing the right model for different user queries can significantly improve response quality while optimizing costs and latency.

This project will guide you through building a complete production-grade multi-model LLM routing system, covering query classification, model selection, inference engine, API service, observability, monitoring, data pipeline, and containerized deployment. Through this project, you will master the complete skill stack for building enterprise-level AI routing platforms.

---

## 1. Project Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        API Gateway Layer                            │
│                    FastAPI REST Service                            │
│              (Health Check / Route Query / Model List / Stats)    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP/REST
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Router Layer                                │
│              (Query Classifier / Model Selector / Strategy)        │
│                    Query Type: CODE / ANALYSIS / GENERAL          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Inference Engine Layer                     │
│         (OpenAI Provider / Anthropic Provider / vLLM Provider)    │
│              (Context Compression / Response Caching)             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Observability Layer                         │
│           (Structured Logging / Prometheus Metrics / Alerts)       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Data Pipeline Layer                         │
│              (Kafka Message Queue / ClickHouse Storage)            │
│                  (Query Logs / Metrics / Errors)                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Module Overview

This project consists of 10 core modules working together to form a complete LLM routing system.

### 2.1 Core Modules

| Module | Description | Key Responsibilities |
|--------|-------------|---------------------|
| Query Classifier | Classify user query types | Regex-based classification, confidence scoring |
| Model Selector | Select optimal model | Strategy-based routing, fallback logic |
| Inference Engine | Unified model interface | Provider abstraction, streaming, retry |
| Context Manager | Context optimization | Compression, cache, token counting |
| API Service | REST API endpoints | Request validation, response formatting |
| Logging System | Structured logging | Request logs, context filters |
| Metrics Collector | Prometheus metrics | System, router, inference metrics |
| Health Monitor | Health & alerting | Health checks, alert rules |
| Data Pipeline | Query logging | Kafka producer/consumer, storage |
| Deployment | Container configs | Docker, Kubernetes, CI/CD |

### 2.2 Data Models

The system uses Pydantic models for request/response validation:

| Model | Purpose | Key Fields |
|-------|---------|------------|
| QueryRequest | User query input | query, user_id, session_id |
| QueryResponse | AI response output | response, model_used, tokens, latency_ms |
| RouterConfig | Router configuration | strategy, models, fallback_enabled |
| ModelConfig | Model parameters | provider, model_name, api_key, priority |
| HealthStatus | System health | status, models_available, uptime |

---

## 3. Task Requirements

### 3.1 Task Objectives

Build a complete multi-model LLM routing platform with the following capabilities:

1. Intelligent query classification and model routing
2. Support for multiple LLM providers (OpenAI, Anthropic)
3. Context compression and response caching
4. RESTful API service with FastAPI
5. Structured logging and Prometheus metrics
6. Health monitoring and alerting
7. Query logging and statistics
8. Containerized deployment

### 3.2 Detailed Task Description

---

#### Part 1: Project Initialization and Configuration (10 points)

**Objective**: Set up project structure and configuration management.

**Requirements**:

1. **Project Structure** (4 points)
   - Create standard Python project directory structure
   - Set up virtual environment and dependencies
   - Create version control ignore files
   - Implement configuration loading module

2. **Configuration Management** (6 points)
   - Create main configuration file (config.yaml)
   - Implement configuration data models using Pydantic
   - Support loading from YAML files
   - Include API settings, logging, router, inference configurations

**Expected Output**:
```
project/
├── src/                    # Source code
│   ├── __init__.py
│   ├── config.py          # Configuration loader
│   └── models.py          # Data models
├── config/
│   └── config.yaml        # Configuration file
├── tests/                  # Test code
├── logs/                   # Log files
└── requirements.txt
```

---

#### Part 2: Query Classification (10 points)

**Objective**: Implement query classifier to identify query types.

**Requirements**:

1. **Query Type Definition** (3 points)
   - CODE_GENERATION: Code generation, debugging, refactoring
   - CODE_ANALYSIS: Code review, explanation, optimization
   - ANALYSIS: Data analysis, research, comparison
   - SUMMARIZATION: Summary, paraphrase, translation
   - CREATIVE_WRITING: Content creation, brainstorming
   - GENERAL: General questions, chat

2. **Classification Implementation** (4 points)
   - Use regular expressions for pattern matching
   - Calculate confidence score (0.0 - 1.0)
   - Handle edge cases and mixed queries

3. **Integration** (3 points)
   - Integrate classifier into routing flow
   - Return classification result with confidence

**Expected Output**:
```python
{
    "query_type": "CODE_GENERATION",
    "confidence": 0.85,
    "keywords": ["function", "implement", "code"]
}
```

---

#### Part 3: Model Selection and Routing (10 points)

**Objective**: Implement intelligent model selection based on query type and configuration.

**Requirements**:

1. **Model Configuration** (3 points)
   - Define model list with provider, name, capabilities
   - Configure priority and cost for each model
   - Support multiple models per query type

2. **Routing Strategies** (4 points)
   - INTELLIGENT: Select based on query type and model capabilities
   - ROUND_ROBIN: Rotate through available models
   - WEIGHTED: Select based on configured weights
   - COST_OPTIMIZED: Select cheapest suitable model
   - LATENCY_OPTIMIZED: Select fastest model

3. **Fallback Mechanism** (3 points)
   - Detect model unavailability
   - Fallback to alternative models
   - Handle complete system failure gracefully

**Expected Output**:
```python
{
    "selected_model": "gpt-4",
    "provider": "openai",
    "strategy": "intelligent",
    "fallback_enabled": true
}
```

---

#### Part 4: Inference Engine (15 points)

**Objective**: Implement unified inference interface for multiple LLM providers.

**Requirements**:

1. **Provider Abstraction** (5 points)
   - Define unified inference interface
   - Implement factory pattern for providers
   - Support provider configuration

2. **OpenAI Integration** (4 points)
   - Implement OpenAI API client
   - Support streaming responses
   - Implement error handling and retry
   - Record token usage

3. **Anthropic Integration** (4 points)
   - Implement Claude API client
   - Support streaming responses
   - Error handling and retry logic

4. **Context Management** (2 points)
   - Calculate token count
   - Implement context compression for long inputs

**Expected Output**:
```python
{
    "response": "Generated response text...",
    "model": "gpt-4",
    "usage": {
        "prompt_tokens": 150,
        "completion_tokens": 200,
        "total_tokens": 350
    },
    "latency_ms": 1200.5
}
```

---

#### Part 5: API Service (15 points)

**Objective**: Develop RESTful API service using FastAPI.

**Requirements**:

1. **API Endpoints** (6 points)
   - `GET /health`: Health check, return system status
   - `POST /query`: Route query to LLM, return response
   - `GET /models`: List available models
   - `GET /stats`: Query statistics

2. **Request Validation** (5 points)
   - Define request/response models with Pydantic
   - Validate query text, user_id, session_id
   - Set reasonable default values
   - Handle validation errors gracefully

3. **Error Handling** (4 points)
   - Unified error response format
   - Appropriate HTTP status codes
   - Detailed error messages for debugging

**API Specification**:

```python
# Query Request
POST /query
{
    "query": "Help me write a Python function to calculate Fibonacci",
    "user_id": "user_123",
    "session_id": "sess_abc"
}

# Query Response
{
    "response": "Here's a Python function...",
    "model_used": "gpt-4",
    "query_type": "CODE_GENERATION",
    "tokens_used": 350,
    "latency_ms": 1200.5,
    "timestamp": "2024-01-15T10:30:00Z"
}
```

---

#### Part 6: Logging and Metrics (10 points)

**Objective**: Implement observability components.

**Requirements**:

1. **Structured Logging** (5 points)
   - Configure logging with custom formatters
   - Add context filters (request_id, user_id)
   - Log to file and console
   - Log levels: DEBUG, INFO, WARNING, ERROR

2. **Prometheus Metrics** (5 points)
   - Request counter (total_requests)
   - Latency histogram (request_latency_seconds)
   - Token counter (tokens_used_total)
   - Model selection counter (model_selections_total)
   - Error counter (errors_total)

**Expected Output**:
```
# Metrics Endpoint
GET /metrics

# Example metrics
llm_router_requests_total{method="POST", endpoint="/query"} 1523
llm_router_request_latency_seconds_bucket{le="0.1"} 1200
llm_router_tokens_used_total{model="gpt-4"} 452000
```

---

#### Part 7: Health Monitoring and Alerting (10 points)

**Objective**: Implement system health monitoring and alerting.

**Requirements**:

1. **Health Check** (5 points)
   - Check system component status
   - Verify model provider availability
   - Return detailed health information

2. **Alert Management** (5 points)
   - Define alert rules (latency threshold, error rate)
   - Implement alert notification interface
   - Record alert history

**Expected Output**:
```python
{
    "status": "healthy",
    "components": {
        "api": "up",
        "openai": "up",
        "anthropic": "down"
    },
    "uptime_seconds": 86400
}
```

---

#### Part 8: Data Pipeline (10 points)

**Objective**: Implement query logging and statistics pipeline.

**Requirements**:

1. **Query Logging** (5 points)
   - Log query details: query, response, model, tokens, latency
   - Support async logging for performance
   - Implement log buffering

2. **Statistics** (5 points)
   - Count requests per model
   - Calculate token consumption and cost
   - Track latency distribution

**Expected Output**:
```python
{
    "total_requests": 10000,
    "model_usage": {
        "gpt-4": 5000,
        "claude-3": 5000
    },
    "total_tokens": 2500000,
    "estimated_cost": 75.50,
    "avg_latency_ms": 850.3
}
```

---

#### Part 9: Deployment (10 points)

**Objective**: Implement containerized deployment.

**Requirements**:

1. **Docker Configuration** (4 points)
   - Write Dockerfile
   - Configure Python environment
   - Set environment variables

2. **Container Orchestration** (3 points)
   - Create docker-compose.yml
   - Configure services and volumes
   - Implement health checks

3. **Deployment Documentation** (3 points)
   - Write deployment instructions
   - Document environment variables
   - Provide troubleshooting guide

**Expected Output**:
```bash
# Build and run
docker build -t llm-router .
docker-compose up -d

# Verify deployment
curl http://localhost:8000/health
```

---

## 4. Project Structure

```
Slack.AI.Codebase/
├── src/                           # Source code directory
│   ├── __init__.py
│   ├── config.py                 # Configuration loader
│   ├── models.py                 # Data models (Pydantic)
│   ├── router.py                 # Query classification & routing
│   ├── inference.py              # Inference engine
│   ├── api.py                    # FastAPI application
│   ├── logging.py                # Logging system
│   ├── metrics.py                # Prometheus metrics
│   ├── monitor.py                # Health monitoring
│   └── pipeline.py               # Data pipeline
├── config/
│   └── config.yaml               # Configuration file
├── tests/                         # Test code directory
│   ├── test_router.py
│   ├── test_inference.py
│   └── test_api.py
├── logs/                          # Log files directory
├── data/                          # Data directory
├── models/                        # Model storage (if needed)
├── requirements.txt               # Python dependencies
├── Dockerfile                     # Docker configuration
├── docker-compose.yml             # Docker Compose
└── README.md                      # Project documentation
```

---

## 5. Grading Criteria

| Part | Points | Grading Standards |
|------|--------|-------------------|
| Project Initialization & Configuration | 10 pts | Structure (4), Config (6) |
| Query Classification | 10 pts | Types (3), Implementation (4), Integration (3) |
| Model Selection & Routing | 10 pts | Config (3), Strategies (4), Fallback (3) |
| Inference Engine | 15 pts | Abstraction (5), OpenAI (4), Anthropic (4), Context (2) |
| API Service | 15 pts | Endpoints (6), Validation (5), Errors (4) |
| Logging & Metrics | 10 pts | Logging (5), Metrics (5) |
| Health Monitoring & Alerting | 10 pts | Health (5), Alerts (5) |
| Data Pipeline | 10 pts | Logging (5), Stats (5) |
| Deployment | 10 pts | Docker (4), Compose (3), Docs (3) |

**Total Score**: 100 points

---

## 6. Environment Setup and Dependencies

### 6.1 Python Environment Requirements

```txt
# Web Framework
fastapi>=0.100.0
uvicorn[standard]>=0.23.0

# Data Validation
pydantic>=2.0.0
pydantic-settings>=2.0.0

# HTTP Client
httpx>=0.25.0
aiohttp>=3.9.0

# Configuration
pyyaml>=6.0

# Logging
structlog>=23.0.0

# Metrics
prometheus-client>=0.19.0

# Async Support
asyncio-throttle>=1.0.0

# Testing
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-cov>=4.1.0

# Utilities
python-dotenv>=1.0.0
tiktoken>=0.5.0
```

### 6.2 Environment Variables

```bash
# API Keys (required for inference)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Configuration (optional)
LOG_LEVEL=INFO
METRICS_ENABLED=true
```

### 6.3 Quick Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env .env
# Edit .env with your API keys
```

### 6.4 Service Startup

```bash
# 1. Start API service
uvicorn src.api:app --reload --port 8000

# 2. Access documentation
# Open http://localhost:8000/docs

# 3. Health check
curl http://localhost:8000/health

# 4. Test query
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Hello, how are you?"}'
```

---

## 7. Implementation References

### 7.1 Query Classifier Example

```python
import re
from enum import Enum
from dataclasses import dataclass
from typing import Optional

class QueryType(Enum):
    CODE_GENERATION = "CODE_GENERATION"
    CODE_ANALYSIS = "CODE_ANALYSIS"
    ANALYSIS = "ANALYSIS"
    SUMMARIZATION = "SUMMARIZATION"
    CREATIVE_WRITING = "CREATIVE_WRITING"
    GENERAL = "GENERAL"

@dataclass
class ClassificationResult:
    """Classification result data class"""
    query_type: QueryType                    # Query type
    confidence: float                        # Confidence score
    keywords: list[str]                      # Matched keywords

class QueryClassifier:
    """Query classifier using regex pattern matching"""
    
    # Predefined query patterns
    PATTERNS = {
        QueryType.CODE_GENERATION: [
            r'\b(write|create|implement|generate)\b.*\b(code|function|class|script)\b',
            r'\b(python|javascript|java|go|rust)\b',
        ],
        QueryType.CODE_ANALYSIS: [
            r'\b(explain|analyze|review|debug|optimize)\b.*\b(code|function)\b',
        ],
        QueryType.ANALYSIS: [
            r'\b(analyze|compare|evaluate|research|study)\b',
        ],
        QueryType.SUMMARIZATION: [
            r'\b(summary|summarize|paraphrase|translate|condense)\b',
        ],
        QueryType.CREATIVE_WRITING: [
            r'\b(write|create|story|article|blog)\b',
        ],
    }

    def classify(self, query: str) -> ClassificationResult:
        """Classify the query"""
        query_lower = query.lower()
        scores = {}

        # Iterate through all patterns, calculate match scores
        for qtype, patterns in self.PATTERNS.items():
            score = 0
            matches = []
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    score += 1
                    matches.append(pattern)
            if score > 0:
                scores[qtype] = (score, matches)

        # No match, return GENERAL type
        if not scores:
            return ClassificationResult(
                query_type=QueryType.GENERAL,
                confidence=0.5,
                keywords=[]
            )

        # Select the highest scoring type
        best_type = max(scores, key=lambda x: scores[x][0])
        confidence = min(scores[best_type][0] * 0.3, 1.0)

        return ClassificationResult(
            query_type=best_type,
            confidence=confidence,
            keywords=scores[best_type][1]
        )
```

### 7.2 Model Selector Example

```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional

class RoutingStrategy(Enum):
    """Routing strategy enumeration"""
    INTELLIGENT = "intelligent"           # Intelligent selection
    ROUND_ROBIN = "round_robin"           # Round robin
    WEIGHTED = "weighted"                 # Weighted
    COST_OPTIMIZED = "cost_optimized"     # Cost optimization
    LATENCY_OPTIMIZED = "latency_optimized"  # Latency optimization

@dataclass
class ModelInfo:
    """Model information data class"""
    name: str                             # Model name
    provider: str                         # Provider
    query_types: list[str]                # Supported query types
    priority: int                          # Priority
    cost_per_1k_tokens: float             # Cost per 1000 tokens
    avg_latency_ms: float                  # Average latency
    enabled: bool = True                  # Enabled flag

class ModelSelector:
    """Model selector: select the most suitable model based on strategy"""
    
    def __init__(self, models: list[ModelInfo], strategy: RoutingStrategy):
        self.models = models
        self.strategy = strategy
        self._round_robin_index = 0        # Round robin index

    def select(self, query_type: str, 
               available_models: Optional[list[str]] = None) -> ModelInfo:
        """Select model based on query type"""
        # Get candidate model list
        candidates = [m for m in self.models if m.enabled]

        # Filter available models
        if available_models:
            candidates = [m for m in candidates if m.name in available_models]

        # Filter models supporting this query type
        candidates = [m for m in candidates 
                      if query_type in m.query_types or "GENERAL" in m.query_types]

        # Fallback to GENERAL type if no match
        if not candidates:
            candidates = [m for m in self.models 
                          if m.enabled and "GENERAL" in m.query_types]

        # Select model based on strategy
        if self.strategy == RoutingStrategy.INTELLIGENT:
            return max(candidates, key=lambda m: m.priority)
        elif self.strategy == RoutingStrategy.ROUND_ROBIN:
            selected = candidates[self._round_robin_index % len(candidates)]
            self._round_robin_index += 1
            return selected
        elif self.strategy == RoutingStrategy.WEIGHTED:
            total_weight = sum(m.priority for m in candidates)
            import random
            r = random.uniform(0, total_weight)
            cumsum = 0
            for model in candidates:
                cumsum += model.priority
                if cumsum >= r:
                    return model
        elif self.strategy == RoutingStrategy.COST_OPTIMIZED:
            return min(candidates, key=lambda m: m.cost_per_1k_tokens)
        elif self.strategy == RoutingStrategy.LATENCY_OPTIMIZED:
            return min(candidates, key=lambda m: m.avg_latency_ms)

        return candidates[0]
```

### 7.3 FastAPI Endpoint Example

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

app = FastAPI(title="LLM Router API")

class QueryRequest(BaseModel):
    """Query request model"""
    query: str = Field(..., min_length=1, max_length=10000)  # Query content
    user_id: Optional[str] = Field(None, max_length=100)       # User ID
    session_id: Optional[str] = Field(None, max_length=100)   # Session ID

class QueryResponse(BaseModel):
    """Query response model"""
    response: str                         # Response content
    model_used: str                        # Model used
    query_type: str                       # Query type
    tokens_used: int                      # Tokens used
    latency_ms: float                     # Latency in milliseconds
    timestamp: str                        # Timestamp

@app.post("/query", response_model=QueryResponse)
async def route_query(request: QueryRequest):
    """Route query endpoint"""
    try:
        # Classify query
        classification = classifier.classify(request.query)

        # Select model
        model = selector.select(classification.query_type.value)

        # Generate response
        result = await inference.generate(
            query=request.query,
            model=model.name,
            provider=model.provider
        )

        return QueryResponse(
            response=result["response"],
            model_used=model.name,
            query_type=classification.query_type.value,
            tokens_used=result["tokens"],
            latency_ms=result["latency"],
            timestamp=result["timestamp"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "models_available": len(selector.models)}
```

---

## 8. Important Notes

### 8.1 API Key Security

Never commit API keys to version control. Use environment variables or `.env` files (added to `.gitignore`).

### 8.2 Error Handling

All API calls to external providers may fail. Implement proper error handling with:
- Retry logic with exponential backoff
- Timeout handling
- Graceful degradation

### 8.3 Cost Management

Monitor token usage carefully. Implement:
- Token counting before sending requests
- Cost estimation and limits
- Alert thresholds for unusual spending

### 8.4 Code Standards

- Keep code clean with appropriate comments
- Write docstrings for functions and classes
- Use meaningful variable names
- Add logging for easier debugging
- Write unit tests for core modules

---

## 9. Submission Requirements

1. **Complete Code**: All source code including configuration, tests
2. **README Documentation**: Project description, installation, usage
3. **Test Report**: Unit test coverage (minimum 70%)
4. **API Documentation**: Endpoint specifications
5. **Deployment Guide**: How to build and deploy

---

## 10. Reference Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [OpenAI API Documentation](https://platform.openai.com/docs/)
- [Anthropic Documentation](https://docs.anthropic.com/)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [Docker Documentation](https://docs.docker.com/)

---

*Project Version: v1.0*
*Last Updated: August 2026*
