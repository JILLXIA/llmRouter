# LLM Router Evaluation

- Dataset: `routing-v1`
- Mode: `live_hybrid`
- Cases: 120
- Coverage: 100.0%
- Accuracy on classified cases: 93.3%
- Failed cases: 0

## Per-intent results

| Intent | Classified / Total | Accuracy |
|---|---:|---:|
| CODE_GENERATION | 20 / 20 | 100.0% |
| CODE_ANALYSIS | 20 / 20 | 75.0% |
| ANALYSIS | 20 / 20 | 100.0% |
| SUMMARIZATION | 20 / 20 | 100.0% |
| CREATIVE_WRITING | 20 / 20 | 100.0% |
| GENERAL | 20 / 20 | 85.0% |

## Routing gate

Status: `FAIL`
- CODE_ANALYSIS accuracy is below 80%

## Reproduce

```bash
python -m llm_router.evals --live
```
