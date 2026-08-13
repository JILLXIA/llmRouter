from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from llm_router.config import load_settings
from llm_router.models import Intent
from llm_router.router import LLMRouter, keyword_match

'''
# Free keyword-only evaluation
python -m llm_router.evals

# Complete hybrid evaluation using OpenAI
python -m llm_router.evals --live
'''
PROJECT_ROOT = Path(__file__).parents[2]
DEFAULT_DATASET = PROJECT_ROOT / "evals" / "routing-v1.jsonl"
DEFAULT_JSON_REPORT = PROJECT_ROOT / "reports" / "eval-results.json"
DEFAULT_MARKDOWN_REPORT = PROJECT_ROOT / "reports" / "eval-summary.md"

MODEL_ALIAS_BY_INTENT = {
    Intent.CODE_GENERATION: "high_quality",
    Intent.CODE_ANALYSIS: "high_quality",
    Intent.ANALYSIS: "balanced",
    Intent.CREATIVE_WRITING: "balanced",
    Intent.SUMMARIZATION: "economy",
    Intent.GENERAL: "economy",
}

# A classifier returns its prediction and the stage that made the decision.
Classifier = Callable[[str], tuple[Intent | None, str]]


class EvalCase(BaseModel):
    """One reviewed input and its expected intent."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9_]+$")
    query: str = Field(min_length=1)
    expected_intent: Intent


def load_cases(path: str | Path = DEFAULT_DATASET) -> list[EvalCase]:
    """Read the JSONL dataset and reject invalid or duplicate cases."""

    cases: list[EvalCase] = []
    seen_ids: set[str] = set()

    for line_number, line in enumerate(Path(path).read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            case = EvalCase.model_validate_json(line)
        except Exception as error:
            raise ValueError(f"invalid case on line {line_number}: {error}") from error
        if case.id in seen_ids:
            raise ValueError(f"duplicate case id: {case.id}")
        seen_ids.add(case.id)
        cases.append(case)

    if not cases:
        raise ValueError("evaluation dataset is empty")
    return cases


def validate_dataset(cases: Sequence[EvalCase]) -> None:
    """Check the promised v1 shape: 120 cases, 20 for each intent."""

    if len(cases) != 120:
        raise ValueError(f"routing-v1 must contain 120 cases, found {len(cases)}")

    counts = Counter(case.expected_intent for case in cases)
    '''
    counts = {
        Intent.SEARCH: 2,
        Intent.CREATE: 1,
    }
    '''
    for intent in Intent:
        if counts[intent] != 20:
            raise ValueError(
                f"routing-v1 must contain 20 {intent.value} cases, "
                f"found {counts[intent]}"
            )


def keyword_classifier(query: str) -> tuple[Intent | None, str]:
    """Evaluate only the free, deterministic keyword stage."""

    intent, confident = keyword_match(query)
    if confident and intent:
        return intent, "keyword"
    return None, "unresolved"


def evaluate(cases: Sequence[EvalCase], classify: Classifier) -> list[dict[str, Any]]:
    """Run every case, recording a failure instead of stopping the suite."""

    results: list[dict[str, Any]] = []
    for case in cases:
        started = perf_counter()
        try:
            predicted, source = classify(case.query)
            results.append(
                {
                    "case_id": case.id,
                    "expected_intent": case.expected_intent.value,
                    "predicted_intent": predicted.value if predicted else None,
                    "predicted_model_alias": (
                        MODEL_ALIAS_BY_INTENT[predicted] if predicted else None
                    ),
                    "source": source,
                    "correct": predicted == case.expected_intent,
                    "latency_ms": round((perf_counter() - started) * 1_000, 3),
                    "error": None,
                }
            )
        except Exception as error:
            results.append(
                {
                    "case_id": case.id,
                    "expected_intent": case.expected_intent.value,
                    "predicted_intent": None,
                    "predicted_model_alias": None,
                    "source": "error",
                    "correct": False,
                    "latency_ms": round((perf_counter() - started) * 1_000, 3),
                    "error": f"{type(error).__name__}: {error}",
                }
            )
    return results


def summarize(
    results: Sequence[dict[str, Any]],
    *,
    dataset_name: str,
    live: bool,
) -> dict[str, Any]:
    """Calculate the small set of metrics needed to judge the router."""

    total = len(results)
    classified = [result for result in results if result["predicted_intent"]]
    correct = sum(result["correct"] for result in results)

    per_intent: dict[str, dict[str, Any]] = {}
    for intent in Intent:
        group = [
            result
            for result in results
            if result["expected_intent"] == intent.value
        ]
        group_classified = [result for result in group if result["predicted_intent"]]
        group_correct = sum(result["correct"] for result in group)
        per_intent[intent.value] = {
            "total": len(group),
            "classified": len(group_classified),
            "accuracy": round(group_correct / len(group_classified), 4)
            if group_classified
            else None,
        }

    columns = [intent.value for intent in Intent] + ["UNRESOLVED"]
    confusion_matrix = {
        intent.value: {column: 0 for column in columns} for intent in Intent
    }
    for result in results:
        predicted = result["predicted_intent"] or "UNRESOLVED"
        confusion_matrix[result["expected_intent"]][predicted] += 1

    accuracy = round(correct / len(classified), 4) if classified else None
    threshold_failures: list[str] = []
    if live:
        if len(classified) != total:
            threshold_failures.append("live coverage is below 100%")
        if accuracy is None or accuracy < 0.90:
            threshold_failures.append("overall accuracy is below 90%")
        for intent, metrics in per_intent.items():
            intent_accuracy = metrics["accuracy"]
            if intent_accuracy is None or intent_accuracy < 0.80:
                threshold_failures.append(f"{intent} accuracy is below 80%")

    return {
        "dataset": dataset_name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "live_hybrid" if live else "offline_keyword_only",
        "total_cases": total,
        "classified_cases": len(classified),
        "unresolved_cases": total - len(classified),
        "failed_cases": sum(bool(result["error"]) for result in results),
        "coverage": round(len(classified) / total, 4),
        "accuracy_on_classified_cases": accuracy,
        "source_counts": dict(Counter(result["source"] for result in results)),
        "average_latency_ms": round(
            sum(result["latency_ms"] for result in results) / total, 3
        ),
        "per_intent": per_intent,
        "confusion_matrix": confusion_matrix,
        "routing_gate": {
            "applied": live,
            "passed": not threshold_failures if live else None,
            "failures": threshold_failures,
        },
        "results": list(results),
    }


def render_markdown(summary: dict[str, Any], command: str) -> str:
    """Create a short human-readable report from the JSON summary."""

    accuracy = summary["accuracy_on_classified_cases"]
    accuracy_text = f"{accuracy:.1%}" if accuracy is not None else "N/A"
    lines = [
        "# LLM Router Evaluation",
        "",
        f"- Dataset: `{summary['dataset']}`",
        f"- Mode: `{summary['mode']}`",
        f"- Cases: {summary['total_cases']}",
        f"- Coverage: {summary['coverage']:.1%}",
        f"- Accuracy on classified cases: {accuracy_text}",
        f"- Failed cases: {summary['failed_cases']}",
        "",
    ]

    if summary["mode"] == "offline_keyword_only":
        lines.extend(
            [
                "> Offline mode evaluates only keyword matching. Unresolved prompts "
                "need the LLM classifier, so this is not full-router accuracy.",
                "",
            ]
        )

    lines.extend(
        [
            "## Per-intent results",
            "",
            "| Intent | Classified / Total | Accuracy |",
            "|---|---:|---:|",
        ]
    )
    for intent, metrics in summary["per_intent"].items():
        value = metrics["accuracy"]
        value_text = f"{value:.1%}" if value is not None else "N/A"
        lines.append(
            f"| {intent} | {metrics['classified']} / {metrics['total']} | "
            f"{value_text} |"
        )

    gate = summary["routing_gate"]
    if gate["applied"]:
        lines.extend(
            [
                "",
                "## Routing gate",
                "",
                f"Status: `{'PASS' if gate['passed'] else 'FAIL'}`",
            ]
        )
        lines.extend(f"- {failure}" for failure in gate["failures"])

    failures = [result for result in summary["results"] if result["error"]]
    if failures:
        lines.extend(["", "## Failed cases", ""])
        lines.extend(
            f"- `{result['case_id']}`: {result['error']}" for result in failures
        )

    lines.extend(["", "## Reproduce", "", f"```bash\n{command}\n```", ""])
    return "\n".join(lines)


def write_reports(
    summary: dict[str, Any],
    json_path: str | Path,
    markdown_path: str | Path,
    command: str,
) -> None:
    json_target = Path(json_path)
    markdown_target = Path(markdown_path)
    json_target.parent.mkdir(parents=True, exist_ok=True)
    markdown_target.parent.mkdir(parents=True, exist_ok=True)
    json_target.write_text(json.dumps(summary, indent=2) + "\n")
    markdown_target.write_text(render_markdown(summary, command))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use the complete hybrid classifier and allow paid API calls",
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--json-report", type=Path, default=DEFAULT_JSON_REPORT)
    parser.add_argument(
        "--markdown-report", type=Path, default=DEFAULT_MARKDOWN_REPORT
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cases = load_cases(args.dataset)
        validate_dataset(cases)
    except (OSError, ValueError) as error:
        print(f"Dataset error: {error}")
        return 2

    if args.live:
        try:
            router = LLMRouter(load_settings())
        except Exception as error:
            print(f"Live evaluation setup failed: {type(error).__name__}: {error}")
            return 2
        classify: Classifier = router.classify
    else:
        classify = keyword_classifier

    results = evaluate(cases, classify)
    summary = summarize(results, dataset_name=args.dataset.stem, live=args.live)
    command = "python -m llm_router.evals" + (" --live" if args.live else "")
    write_reports(summary, args.json_report, args.markdown_report, command)

    print(
        f"{summary['mode']}: {summary['coverage']:.1%} coverage, "
        f"reports written to {args.markdown_report} and {args.json_report}"
    )
    gate = summary["routing_gate"]
    return 1 if gate["applied"] and not gate["passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
