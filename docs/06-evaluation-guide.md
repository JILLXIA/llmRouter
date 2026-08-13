# Simple Routing Evaluation Guide

## What it evaluates

This P1 evaluation answers one question: does the router predict the expected intent?

It deliberately does not generate chat responses, call a judge model, compare response quality, or calculate cost. Those are useful future additions, but they are not required to validate the current routing logic.

The implementation is in `src/llm_router/evals.py`. Its flow is:

```text
load JSONL cases -> classify each query -> compare intents -> summarize -> write reports
```

## Dataset

`evals/routing-v1.jsonl` has 120 cases, with 20 cases for each of the six intents. Every line has only three fields:

```json
{"id":"code_generation_001","query":"Implement a Python LRU cache.","expected_intent":"CODE_GENERATION"}
```

The loader rejects invalid JSON, unexpected fields, empty queries, invalid intents, and duplicate IDs. Treat the expected intents as reviewed project labels; read them before presenting a live result as portfolio evidence.

## Offline keyword evaluation

Run:

```bash
python -m llm_router.evals
```

This mode is free and requires no API key. It calls the real `keyword_match()` function. A prompt that cannot be confidently classified by keywords is marked `unresolved` instead of pretending that a fake LLM classified it correctly.

Use two metrics together:

- Coverage: the percentage of cases resolved by keywords.
- Accuracy: the percentage correct among the cases resolved by keywords.

This measures the keyword stage, not the complete router.

## Live hybrid evaluation

Run:

```bash
python -m llm_router.evals --live
```

This mode creates the normal `LLMRouter`. Confident prompts use keywords; ambiguous prompts use the configured lightweight OpenAI classifier. It requires `OPENAI_API_KEY` and can incur API charges.

The live routing gate passes when coverage is 100%, overall accuracy is at least 90%, and every intent is at least 80%. A failed case is recorded and evaluation continues with the next case.

## Reports

Both modes write:

```text
reports/eval-results.json
reports/eval-summary.md
```

The JSON report contains summary metrics and one compact result per case. The Markdown report is intended for quick human review. Neither report stores model-generated responses or conversation history.

Key fields are:

- `coverage`
- `accuracy_on_classified_cases`
- `per_intent`
- `source_counts`
- `confusion_matrix`
- `routing_gate`
- `results`

Rerun the evaluation whenever keyword rules, classifier prompts, routing policy, or model configuration changes.
