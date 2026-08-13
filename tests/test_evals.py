from __future__ import annotations

import json
from pathlib import Path

import pytest

from llm_router.evals import (
    DEFAULT_DATASET,
    EvalCase,
    evaluate,
    keyword_classifier,
    load_cases,
    main,
    render_markdown,
    summarize,
    validate_dataset,
)
from llm_router.models import Intent


def sample_case(**overrides: object) -> EvalCase:
    values: dict[str, object] = {
        "id": "case_001",
        "query": "Implement a Python function",
        "expected_intent": "CODE_GENERATION",
    }
    values.update(overrides)
    return EvalCase.model_validate(values)


def test_dataset_has_120_cases_and_20_per_intent() -> None:
    cases = load_cases()

    validate_dataset(cases)

    assert len(cases) == 120
    assert all(
        sum(case.expected_intent == intent for case in cases) == 20
        for intent in Intent
    )


def test_loader_rejects_duplicate_and_invalid_cases(tmp_path: Path) -> None:
    record = sample_case().model_dump(mode="json")
    duplicate = tmp_path / "duplicate.jsonl"
    duplicate.write_text("\n".join(json.dumps(record) for _ in range(2)))

    with pytest.raises(ValueError, match="duplicate case id"):
        load_cases(duplicate)

    invalid = tmp_path / "invalid.jsonl"
    invalid.write_text("{not-json}\n")
    with pytest.raises(ValueError, match="line 1"):
        load_cases(invalid)


def test_keyword_classifier_marks_ambiguous_queries_unresolved() -> None:
    predicted, source = keyword_classifier("Hello there")

    assert predicted is None
    assert source == "unresolved"


def test_evaluate_records_predictions_and_continues_after_errors() -> None:
    calls = 0

    def fake_classifier(query: str) -> tuple[Intent, str]:
        nonlocal calls
        calls += 1
        if "fail" in query:
            raise TimeoutError("provider unavailable")
        return Intent.CODE_GENERATION, "llm"

    cases = [
        sample_case(id="good_case"),
        sample_case(id="bad_case", query="please fail"),
        sample_case(id="later_case"),
    ]

    results = evaluate(cases, fake_classifier)

    assert calls == 3
    assert results[0]["correct"] is True
    assert results[0]["predicted_model_alias"] == "high_quality"
    assert results[1]["error"] == "TimeoutError: provider unavailable"
    assert results[2]["correct"] is True


def test_live_summary_calculates_metrics_and_gate() -> None:
    cases = [
        sample_case(id="case_001"),
        sample_case(id="case_002", expected_intent="GENERAL"),
    ]

    def always_code(_: str) -> tuple[Intent, str]:
        return Intent.CODE_GENERATION, "llm"

    summary = summarize(
        evaluate(cases, always_code),
        dataset_name="test",
        live=True,
    )

    assert summary["coverage"] == 1.0
    assert summary["accuracy_on_classified_cases"] == 0.5
    assert summary["routing_gate"]["passed"] is False
    assert summary["confusion_matrix"]["GENERAL"]["CODE_GENERATION"] == 1


def test_offline_markdown_explains_keyword_only_scope() -> None:
    summary = summarize(
        evaluate([sample_case()], keyword_classifier),
        dataset_name="test",
        live=False,
    )

    markdown = render_markdown(summary, "python -m llm_router.evals")

    assert "keyword matching" in markdown
    assert "not full-router accuracy" in markdown
    assert summary["routing_gate"]["applied"] is False


def test_cli_writes_offline_reports(tmp_path: Path) -> None:
    json_report = tmp_path / "results.json"
    markdown_report = tmp_path / "summary.md"

    exit_code = main(
        [
            "--dataset",
            str(DEFAULT_DATASET),
            "--json-report",
            str(json_report),
            "--markdown-report",
            str(markdown_report),
        ]
    )

    report = json.loads(json_report.read_text())
    assert exit_code == 0
    assert report["total_cases"] == 120
    assert report["mode"] == "offline_keyword_only"
    assert "LLM Router Evaluation" in markdown_report.read_text()
