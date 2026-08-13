# LLM Router

This repository implements the P0 vertical slice of `Slack.AI LLM Router Platform.md`: a Streamlit chat application that classifies each message, chooses an OpenAI model, and displays the answer with routing metadata.

## P0 behavior

1. Deterministic keyword rules score the six supported intents.
2. Ambiguous or unmatched messages use `gpt-5.4-nano` for typed intent classification.
3. The router selects a configured OpenAI response model.
4. The selected model receives up to the last 10 chat messages through the Responses API.
5. Streamlit displays the answer, routing decision, and response-model token usage.

The default routing table is:

| Intent | Default model |
|---|---|
| `CODE_GENERATION`, `CODE_ANALYSIS` | `gpt-5.6-sol` |
| `ANALYSIS`, `CREATIVE_WRITING` | `gpt-5.6-terra` |
| `SUMMARIZATION`, `GENERAL` | `gpt-5.6-luna` |

Model IDs are environment settings because OpenAI project access can differ.

## Run locally

Python 3.10 or newer is required.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Ensure the existing `.env` contains `OPENAI_API_KEY` and the model settings documented in the P0 requirements, then start the application:

```bash
streamlit run app.py
```

The `.env` file is ignored by Git. Never commit the key.

## Run tests

```bash
python -m pytest
python -m pytest --cov=llm_router --cov=app --cov-report=term-missing
```

The automated suite injects fake LangChain models and does not consume API credits. The simplified implementation passes 27 tests with 97% branch coverage. A real-model smoke test requires a valid `OPENAI_API_KEY` and access to the configured model IDs.

## Project structure

```text
app.py                         Streamlit UI and session state
src/llm_router/config.py       Environment-backed settings
src/llm_router/models.py       Intent schema and chat result
src/llm_router/router.py       Classification, routing, and LangChain calls
tests/test_router.py           Complete routing-flow tests
tests/test_app.py              Streamlit smoke tests
tests/test_config.py           Settings tests
```

The P0 deliberately has one main backend class: `LLMRouter`. Its `chat()` method classifies the prompt, looks up the configured model, converts recent history to LangChain messages, invokes the model, and returns the answer with routing metadata. Small helper methods keep those steps readable without introducing a layer for each one.

LangChain's `init_chat_model` enables the OpenAI Responses API and provider-native JSON Schema output for intent classification. Routed response models are cached by model ID.

## Scope and documentation

- `MVP P0 — implemented`: Streamlit chat, hybrid intent classification, OpenAI model routing, session history, friendly errors, and automated tests.
- `Validation pending`: manually approved live OpenAI smoke calls; no API key is stored in this repository.
- `Deferred`: FastAPI endpoints and the larger platform requirements in documents 00–04.

Documentation:

1. [Original requirement](Slack.AI%20LLM%20Router%20Platform.md)
2. [Bare-minimum P0 requirements — active](docs/05-bare-minimum-mvp-requirements.md)
3. [Strict requirements analysis and priorities](docs/00-requirements-analysis.md)
4. [Source-aligned architecture](docs/01-architecture.md)
5. [P0 component development tutorial](docs/02-development-tutorial.md)
6. [P0-first development plan](docs/03-development-plan.md)
7. [Deferred five-endpoint API specification](docs/04-api-specification.md)

The deferred API endpoints are `POST /query`, `GET /models`, `GET /stats`, `GET /health`, and `GET /metrics`. They are not part of the active Streamlit MVP.
