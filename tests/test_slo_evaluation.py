import argparse
import json

import httpx
import pytest

from evaluation.slo_evaluation import (
    QUERY_TIMEOUT_SECONDS,
    _positive_timeout_seconds,
    build_slo_report,
    evaluate_dataset,
    load_golden_cases,
    planned_route,
    submit_and_wait,
)


def test_query_timeout_defaults_above_observed_runtime():
    assert QUERY_TIMEOUT_SECONDS == 180.0


def test_query_timeout_argument_requires_positive_finite_seconds():
    assert _positive_timeout_seconds("120") == 120.0
    with pytest.raises(argparse.ArgumentTypeError):
        _positive_timeout_seconds("0")
    with pytest.raises(argparse.ArgumentTypeError):
        _positive_timeout_seconds("inf")


def _outcome(
    case_id,
    category,
    *,
    expected_route="document_retrieval",
    planned="document_retrieval",
    expected_escalation=False,
    actual_escalation=False,
    expected_risk="not_applicable",
    predicted_risk="not_applicable",
    latency=1.0,
    source_attributed=True,
    task_success=True,
    accuracy=0.99,
):
    return {
        "case_id": case_id,
        "category": category,
        "latency_seconds": latency,
        "status": "escalated" if actual_escalation else "completed",
        "expected_route": expected_route,
        "planned_route": planned,
        "route_correct": expected_route == planned,
        "expected_escalation": expected_escalation,
        "actual_escalation": actual_escalation,
        "expected_risk_class": expected_risk,
        "predicted_risk_class": predicted_risk,
        "source_attributed": source_attributed,
        "scores": {
            "faithfulness": 0.9,
            "answer_relevance": 0.9,
            "context_precision": 0.9,
            "context_recall": 0.9,
            "accuracy": accuracy,
            "confidence": 0.9,
            "task_success": task_success,
            "risk_classification": predicted_risk,
        },
    }


def test_load_golden_cases_reads_the_project_dataset():
    dataset = load_golden_cases()

    assert dataset["case_count"] == 50
    assert len(dataset["cases"]) == 50
    assert dataset["dataset_id"] == "friis-golden-evaluation"


def test_planned_route_uses_the_production_escalation_rule():
    case = {
        "id": "test-advice",
        "question": "Should I buy this asset?",
        "portfolio_id": None,
    }

    assert planned_route(case) == "human_escalation"


@pytest.mark.asyncio
async def test_submit_and_wait_polls_the_authenticated_query_api():
    statuses = iter(("queued", "completed"))

    def handle_request(request):
        assert request.headers["Authorization"] == "Bearer evaluation-token"
        if request.method == "POST":
            assert request.url.path == "/api/v1/queries"
            assert json.loads(request.read()) == {
                "question": "Summarize portfolio risk.",
                "portfolio_id": 901,
            }
            return httpx.Response(202, json={"query_id": "query-1"})
        assert request.url.path == "/api/v1/queries/query-1"
        return httpx.Response(200, json={"status": next(statuses)})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handle_request)
    ) as client:
        result, latency = await submit_and_wait(
            client,
            api_url="https://friis.example/",
            token="evaluation-token",
            case={
                "question": "Summarize portfolio risk.",
                "portfolio_id": 901,
            },
            timeout_seconds=1,
            poll_interval_seconds=0.001,
        )

    assert result["status"] == "completed"
    assert latency >= 0


@pytest.mark.asyncio
async def test_evaluate_dataset_returns_partial_report_when_a_case_errors(monkeypatch):
    async def fail_query(*args, **kwargs):
        raise TimeoutError("query timed out")

    monkeypatch.setattr("evaluation.slo_evaluation.submit_and_wait", fail_query)
    dataset = load_golden_cases()
    dataset["cases"] = dataset["cases"][:1]

    report = await evaluate_dataset(
        dataset=dataset,
        api_url="https://friis.example",
        api_token="evaluation-token",
        judge_client=None,
        judge_deployment="test-deployment",
    )

    assert report["online_evaluation"] == {
        "status": "partial",
        "completed_cases": 0,
        "total_cases": 1,
        "failed_case_id": dataset["cases"][0]["id"],
        "error_type": "TimeoutError",
    }
    assert report["case_count"] == 1
    assert report["cases"][0]["scores"] is None
    assert report["cases"][0]["evaluation_error_type"] == "TimeoutError"


def test_build_slo_report_measures_slos_and_marks_unobservable_ones():
    dataset = {
        "dataset_id": "test-dataset",
        "version": "1",
        "status": "test",
        "cases": [
            {
                "id": "POL-001",
                "expected_escalation": False,
            },
            {
                "id": "SQL-001",
                "expected_escalation": False,
            },
            {
                "id": "DEC-001",
                "expected_escalation": True,
            },
            {
                "id": "CRIT-001",
                "expected_escalation": False,
            },
        ],
    }
    outcomes = [
        _outcome("POL-001", "policy_rag", source_attributed=True),
        _outcome(
            "SQL-001",
            "portfolio_sql",
            expected_route="structured_data",
            planned="document_retrieval",
            latency=3.0,
            source_attributed=False,
            accuracy=0.94,
        ),
        _outcome(
            "DEC-001",
            "high_risk_decision",
            expected_route="human_escalation",
            planned="human_escalation",
            expected_escalation=True,
            actual_escalation=True,
            expected_risk="requires_human_review",
            predicted_risk="requires_human_review",
        ),
        _outcome(
            "CRIT-001",
            "high_risk_decision",
            expected_risk="critical",
            predicted_risk="high",
        ),
    ]

    report = build_slo_report(dataset, outcomes)

    assert report["case_count"] == 4
    assert report["slos"]["Latency"]["observed"] == 3.0
    assert report["slos"]["Latency"]["met"] is False
    assert report["slos"]["SQL Correctness"]["observed"] is None
    assert report["slos"]["SQL Correctness"]["met"] is None
    assert report["slos"]["Escalation Recall"]["observed"] == 1.0
    assert report["slos"]["Critical Misclassification Rate"]["observed"] == 1.0
    assert report["slos"]["Critical Misclassification Rate"]["met"] is False
    assert report["slos"]["Unauthorized Data Access (RBAC)"]["met"] is None
    assert report["slos"]["Guardrail Effectiveness"]["met"] is None
