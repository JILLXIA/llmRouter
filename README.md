# LLM Router
// TODO, new feature, router to company level question or outside question
This repository implements the P0 vertical slice of `Slack.AI LLM Router Platform.md`: a Streamlit chat application that classifies each message, chooses an OpenAI model, and displays the answer with routing metadata.

## P0 behavior

1. Deterministic keyword rules score the six supported intents.
2. Ambiguous or unmatched messages use `gpt-5.4-nano` for typed intent classification.
3. The router selects a configured OpenAI response model.
4. Each anonymous conversation gets a UUID v4 in the page URL and is stored in SQLite.
5. The selected model receives a token-bounded context containing one rolling summary and recent messages.
6. Streamlit displays the answer as it streams, followed by the routing decision and response-model token usage.

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

Ensure the existing `.env` contains `OPENAI_API_KEY` and the model settings documented in the P0 requirements. `DATABASE_PATH` is optional and defaults to `data/llm_router.db`. Then start the application:

```bash
streamlit run app.py
```

The `.env` file is ignored by Git. Never commit the key.

Long-conversation defaults can also be overridden in `.env`:

```text
CONTEXT_TOKEN_BUDGET=8000
SUMMARY_TRIGGER_TOKENS=6000
RECENT_CONTEXT_TOKENS=3000
SUMMARY_MAX_OUTPUT_TOKENS=600
```

The app creates an anonymous session and adds `?session_id=<uuid>` to the URL. Opening that URL restores the conversation from SQLite. Treat the URL as private: this MVP has no login, so anyone with the session URL can read that conversation. `Clear chat` deletes its messages while keeping the same session ID.

## Run tests

```bash
python -m pytest
python -m pytest --cov=llm_router --cov=app --cov-report=term-missing
```

The automated suite injects fake LangChain models and does not consume API credits. The current implementation passes 55 tests with 91% branch coverage. A real-model smoke test requires a valid `OPENAI_API_KEY` and access to the configured model IDs.

## Run evaluations

The repository includes a curated 120-case routing dataset with 20 prompts for each supported intent. The evaluation is intentionally small: it loads the cases, calls a classifier, compares predicted and expected intents, and writes two reports.

```bash
python -m llm_router.evals
```

The default command makes no API calls. It measures only the deterministic keyword stage and reports both precision and coverage. Add `--live` to evaluate the complete keyword-plus-LLM classifier; this can make paid OpenAI calls:

```bash
python -m llm_router.evals --live
```

Reports are written to `reports/eval-results.json` and `reports/eval-summary.md`. Review every expected label before quoting a live result on a resume. See the [evaluation guide](docs/06-evaluation-guide.md) for details.

## Project structure

```text
app.py                         Streamlit UI and anonymous-session flow
src/llm_router/config.py       Environment-backed settings
src/llm_router/models.py       Intent schema and chat result
src/llm_router/router.py       Classification, routing, and streamed LangChain calls
src/llm_router/storage.py      SQLite sessions and message persistence
src/llm_router/evals.py        Simple keyword/live routing evaluation
evals/routing-v1.jsonl         Versioned 120-case routing dataset
tests/test_router.py           Complete routing-flow tests
tests/test_app.py              Streamlit session-flow smoke tests
tests/test_config.py           Settings tests
tests/test_storage.py          SQLite persistence and isolation tests
tests/test_evals.py            Dataset, metric, error, and CLI tests
```

The P0 deliberately has one main backend class: `LLMRouter`. Its `chat()` method classifies the prompt, selects the model, prepares token-aware context, and streams the answer. When context grows past the configured trigger, the economy model replaces the session's previous summary with a cumulative summary of older complete turns. SQLite retains every original message for the UI.

LangChain's `init_chat_model` enables the OpenAI Responses API and provider-native JSON Schema output for intent classification. Routed response models are cached by model ID.

## Scope and documentation

- `MVP P0 — implemented`: streamed Streamlit chat, hybrid intent classification, OpenAI model routing, anonymous SQLite session history, friendly errors, and automated tests.
- `Portfolio P1 — implemented`: curated routing dataset, offline keyword evaluation, opt-in live hybrid evaluation, and reproducible JSON/Markdown reports.
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
