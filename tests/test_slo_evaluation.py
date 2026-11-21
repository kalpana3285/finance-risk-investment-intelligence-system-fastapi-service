import argparse
import json
from types import SimpleNamespace

import httpx
import pytest

from evaluation.slo_evaluation import (
    JudgeScores,
    QUERY_TIMEOUT_SECONDS,
    _positive_timeout_seconds,
    _deterministic_task_success,
    _required_evidence_counts,
    _sql_results_match,
    apply_offline_metrics,
    build_slo_report,
    evaluate_dataset,
    evaluate_sql_correctness,
    judge_case,
    load_golden_cases,
    planned_route,
    _publish_query_scores,
    submit_and_wait,
    evaluate_guardrails,
    evaluate_rbac,
    load_guardrail_attack_cases,
    publish_offline_scores,
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
    relevant_retrieved=1,
    relevant_total=1,
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
        "retrieved_relevant_documents": relevant_retrieved,
        "total_relevant_documents": relevant_total,
        "sql_correct": category == "portfolio_sql",
        "scores": {
            "faithfulness": 0.9,
            "answer_relevance": 0.9,
            "context_precision": 0.9,
            "context_recall": 0.9,
            "correctness": accuracy,
            "usefulness": 0.9,
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
    risk_labels = {case["expected_risk_class"] for case in dataset["cases"]}
    assert "critical" in risk_labels
    assert risk_labels - {"critical", "not_applicable"}
    assert any(case["expected_escalation"] for case in dataset["cases"])


def test_guardrail_attack_dataset_covers_deterministic_and_online_attacks():
    dataset = load_guardrail_attack_cases()

    assert dataset["case_count"] == 5
    assert {
        case["attack_type"] for case in dataset["cases"]
    } >= {"resource_exhaustion", "pii_exfiltration", "prompt_injection"}


def test_guardrail_evaluator_reports_online_only_attacks_as_unverified():
    report = evaluate_guardrails()

    assert report["sample_count"] == 4
    assert report["passed_count"] == 4
    assert report["unverified_count"] == 1
    assert report["unverified_cases"] == [
        {
            "case_id": "GR-PROMPT-INJECTION",
            "attack_type": "prompt_injection",
            "reason": "Requires an online model/API assertion.",
        }
    ]


@pytest.mark.asyncio
async def test_rbac_evaluator_checks_cross_tenant_denials_and_audit_logs():
    report = await evaluate_rbac(load_golden_cases())

    assert report["passed"] is True
    assert report["violation_count"] == 0
    assert report["audit_log_count"] == 3
    assert report["audit_logs_verified"] == 3
    assert {item["case"] for item in report["checks"]} >= {
        "cross_tenant_portfolio_read_denied",
        "cross_tenant_query_submission_denied",
        "query_owner_isolation",
    }


@pytest.mark.asyncio
async def test_judge_case_uses_ground_truth_rubric_and_deterministic_generation():
    class FakeCompletions:
        request = None

        async def create(self, **kwargs):
            self.request = kwargs
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content=json.dumps(
                                {
                                    "faithfulness": 0.9,
                                    "answer_relevance": 0.8,
                                    "context_precision": 0.9,
                                    "context_recall": 0.8,
                                    "correctness": 1.0,
                                    "usefulness": 0.9,
                                    "confidence": 0.85,
                                    "task_success": True,
                                    "risk_classification": "high",
                                }
                            )
                        )
                    )
                ]
            )

    completions = FakeCompletions()
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions)
    )
    case = {
        "id": "test-judge",
        "question": "What risk class is supported?",
        "answer_rubric": ["Return the cited risk classification."],
        "required_evidence": ["risk record 1"],
        "expected_result": {"risk_class": "high"},
        "expected_risk_class": "high",
    }

    scores = await judge_case(
        client,
        deployment="strong-judge",
        case=case,
        result={
            "status": "completed",
            "answer": "The risk class is high.",
            "citations": [{"source_id": "risk:1", "excerpt": "Risk: high"}],
        },
    )

    request = completions.request
    assert request["model"] == "strong-judge"
    assert request["temperature"] == 0
    prompt = request["messages"][0]["content"]
    for metric in (
        "faithfulness",
        "correctness",
        "answer_relevance",
        "usefulness",
        "context_precision",
        "risk classification accuracy",
    ):
        assert metric in prompt
    payload = json.loads(request["messages"][1]["content"])
    assert payload["expected_result"] == {"risk_class": "high"}
    assert scores.correctness == 1
    assert scores.usefulness == 0.9
    assert scores.risk_classification == "high"


def test_planned_route_uses_the_production_escalation_rule():
    case = {
        "id": "test-advice",
        "question": "Should I buy this asset?",
        "portfolio_id": None,
    }

    assert planned_route(case) == "human_escalation"


def test_sql_result_comparison_rejects_missing_rows():
    actual = [
        {
            "record_reference": "portfolio_holdings:1901",
            "record": {"holding_id": 1901, "asset_name": "Apple Inc"},
        }
    ]
    expected = [
        {"holding_id": 1901, "asset_name": "Apple Inc"},
        {"holding_id": 1902, "asset_name": "Microsoft Corp"},
    ]

    assert not _sql_results_match(actual, expected)


def test_sql_result_comparison_rejects_unexpected_rows():
    actual = [
        {
            "record_reference": "portfolio_holdings:1901",
            "record": {"asset_name": "Apple Inc"},
        },
        {
            "record_reference": "portfolio_holdings:1902",
            "record": {"asset_name": "Microsoft Corp"},
        },
        {
            "record_reference": "portfolio_holdings:1903",
            "record": {"asset_name": "US Treasury Bonds"},
        },
    ]
    expected = [
        {"asset_name": "Apple Inc"},
        {"asset_name": "Microsoft Corp"},
    ]

    assert not _sql_results_match(actual, expected)


def test_sql_result_comparison_rejects_incorrect_values():
    actual = [
        {
            "record_reference": "asset_risk_logs:2901",
            "record": {"risk_id": 2901, "risk_score": 46},
        }
    ]

    assert not _sql_results_match(actual, {"risk_id": 2901, "risk_score": 45})


def test_sql_result_comparison_checks_aggregate_values_exactly():
    expected = {
        "sector": "Technology",
        "combined_allocation_percentage": 15.7,
    }

    assert _sql_results_match(
        {
            "sector": "Technology",
            "combined_allocation_percentage": 15.7,
        },
        expected,
    )
    assert not _sql_results_match(
        {
            "sector": "Technology",
            "combined_allocation_percentage": 15.6,
        },
        expected,
    )


def test_sql_result_comparison_handles_expected_empty_results():
    unexpected = [
        {"record_reference": "portfolios:901", "record": {"portfolio_id": 901}}
    ]

    assert _sql_results_match([], None)
    assert not _sql_results_match(unexpected, None)


def test_required_evidence_recall_matches_document_sections_and_record_ids():
    case = {
        "required_evidence": [
            "project-pdf-01 §2 Diversification Principles",
            "fixture portfolio_holdings rows 1901 and 1902",
        ]
    }
    citations = [
        {
            "source_id": "project-pdf-01",
            "source_title": "Investment Strategy",
            "section": "2 Diversification Principles",
        },
        {"record_reference": "portfolio_holdings:1901"},
        {"record_reference": "portfolio_holdings:1902"},
    ]

    assert _required_evidence_counts(
        case, citations, {}
    ) == (3, 3)
    assert _required_evidence_counts(
        case, citations[1:], {}
    ) == (2, 3)


def test_empty_query_has_no_recall_denominator_and_sql_validates_success():
    case = {"required_evidence": ["portfolios filtered by portfolio_id 999"]}

    assert _required_evidence_counts(
        case, [], {"portfolios": []}
    ) == (0, 0)
    assert _required_evidence_counts(
        case, [], {"portfolios": []}
    ) == (0, 0)
    outcome = {
        "category": "portfolio_sql",
        "status": "completed",
        "expected_escalation": False,
        "route_correct": True,
        "predicted_risk_class": "not_applicable",
        "expected_risk_class": "not_applicable",
        "retrieved_relevant_documents": 0,
        "total_relevant_documents": 0,
        "sql_correct": True,
    }
    assert _deterministic_task_success(outcome)
    assert not _deterministic_task_success({**outcome, "sql_correct": False})


def test_golden_evidence_requirements_have_deterministic_recall_targets():
    dataset = load_golden_cases()

    for case in dataset["cases"]:
        retrieved, total = _required_evidence_counts(
            case,
            [],
            dataset["fixtures"],
        )
        assert retrieved == 0
        expected = case.get("expected_result")
        if case["category"] == "portfolio_sql" and (
            expected is None
            or (
                isinstance(expected, dict)
                and expected.get("holding_count") == 0
            )
        ):
            assert total == 0, case["id"]
        else:
            assert total > 0, case["id"]


@pytest.mark.asyncio
async def test_offline_sql_report_exposes_results_and_rejects_extra_rows():
    dataset = load_golden_cases()

    outcomes = await evaluate_sql_correctness(dataset)
    by_case = {item["case_id"]: item for item in outcomes}

    assert by_case["SQL-003"]["expected_result"] == [
        {"asset_name": "Apple Inc", "allocation_percentage": 8.5},
        {"asset_name": "Microsoft Corp", "allocation_percentage": 7.2},
    ]
    assert len(by_case["SQL-003"]["actual_result"]) == 3
    assert by_case["SQL-003"]["passed"] is False
    assert (
        by_case["SQL-004"]["actual_result"]
        == by_case["SQL-004"]["expected_result"]
    )
    assert by_case["SQL-004"]["passed"] is True
    assert by_case["SQL-010"]["actual_result"] == []
    assert by_case["SQL-010"]["expected_result"] is None
    assert by_case["SQL-010"]["passed"] is True


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
    assert report["cases"][0]["task_success"] is False
    assert report["judge"] == {
        "model": "test-deployment",
        "prompt": "friis-finance-rag-evaluator",
        "prompt_version": 2,
    }


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
        _outcome(
            "POL-001",
            "policy_rag",
            source_attributed=True,
            task_success=False,
        ),
        _outcome(
            "SQL-001",
            "portfolio_sql",
            expected_route="structured_data",
            planned="document_retrieval",
            latency=3.0,
            source_attributed=False,
            accuracy=0.94,
            relevant_retrieved=0,
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
    assert report["slos"]["Accuracy"]["observed"] == pytest.approx(7 / 9)
    assert report["slos"]["Accuracy"]["met"] is False
    assert report["slos"]["Recall"]["observed"] == 0.75
    assert report["slos"]["Recall"]["sample_count"] == 4
    assert report["slos"]["Task Success Rate"]["observed"] == 0.5
    assert report["slos"]["Usefulness"]["observed"] == 1.0
    assert report["slos"]["Critical Misclassification Rate"]["observed"] == 1.0
    assert report["slos"]["Escalation Recall"]["observed"] == 1.0
    assert report["slos"]["Critical Misclassification Rate"]["misclassified_case_ids"] == [
        "CRIT-001"
    ]
    assert report["slos"]["Escalation Recall"]["missed_case_ids"] == []
    assert report["slos"]["Unauthorized Data Access (RBAC)"]["met"] is None
    assert report["slos"]["Guardrail Effectiveness"]["met"] is None
    assert report["slos"]["Risk Classification Accuracy"]["observed"] == 0.75


def test_safety_metrics_count_missing_mandatory_cases_as_misses():
    dataset = {
        "dataset_id": "safety-dataset",
        "version": "1",
        "cases": [
            {
                "id": "ESC-001",
                "expected_escalation": True,
                "expected_risk_class": "requires_human_review",
            },
            {
                "id": "ESC-002",
                "expected_escalation": True,
                "expected_risk_class": "requires_human_review",
            },
            {
                "id": "CRIT-001",
                "expected_escalation": False,
                "expected_risk_class": "critical",
            },
            {
                "id": "RISK-001",
                "expected_escalation": False,
                "expected_risk_class": "moderate",
            },
        ],
    }
    outcomes = [
        _outcome(
            "ESC-001",
            "high_risk_decision",
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
        _outcome(
            "RISK-001",
            "high_risk_decision",
            expected_risk="moderate",
            predicted_risk="critical",
        ),
    ]

    report = build_slo_report(dataset, outcomes)

    escalation = report["slos"]["Escalation Recall"]
    assert escalation["observed"] == 0.5
    assert escalation["sample_count"] == 2
    assert escalation["missed_case_ids"] == ["ESC-002"]
    critical = report["slos"]["Critical Misclassification Rate"]
    assert critical["observed"] == 1.0
    assert critical["sample_count"] == 1
    assert critical["non_critical_sample_count"] == 3
    assert critical["misclassified_case_ids"] == ["CRIT-001"]


def test_safety_metrics_stay_unmeasured_when_no_online_cases_ran():
    dataset = load_golden_cases()

    report = build_slo_report(dataset, [])

    escalation = report["slos"]["Escalation Recall"]
    assert escalation["observed"] is None
    assert escalation["sample_count"] == 0
    assert len(escalation["missing_case_ids"]) == 20
    critical = report["slos"]["Critical Misclassification Rate"]
    assert critical["observed"] is None
    assert critical["sample_count"] == 0
    assert critical["missing_case_ids"] == ["POL-015"]


def test_offline_accuracy_uses_labeled_routes_and_exact_sql_results():
    dataset = load_golden_cases()
    routes = [
        {"case_id": "POL-001", "passed": True},
        {"case_id": "POL-002", "passed": False},
    ]
    sql_cases = [
        {"case_id": "SQL-001", "passed": True},
        {"case_id": "SQL-002", "passed": False},
    ]
    offline = {
        "routing_cases": routes,
        "sql_cases": sql_cases,
        "rbac": {"violation_count": 0, "sample_count": 0},
        "guardrails": {"pass_rate": 1.0, "sample_count": 1, "scope": "test"},
    }

    report = apply_offline_metrics(build_slo_report(dataset, []), offline)

    assert report["slos"]["Accuracy"]["observed"] == 0.5
    assert report["slos"]["Accuracy"]["sample_count"] == 4
    assert report["slos"]["SQL Correctness"]["observed"] == 0.5


def test_langfuse_accuracy_and_task_success_use_code_based_checks():
    class FakeLangfuse:
        def __init__(self):
            self.scores = []

        def create_score(self, **kwargs):
            self.scores.append(kwargs)

    client = FakeLangfuse()
    _publish_query_scores(
        client,
        trace_id="trace-1",
        case={
            "id": "SQL-001",
            "category": "portfolio_sql",
            "expected_risk_class": "high",
        },
        scores=JudgeScores(
            faithfulness=0.9,
            answer_relevance=0.9,
            context_precision=0.9,
            context_recall=0.9,
            correctness=0.9,
            usefulness=0.9,
            confidence=0.9,
            task_success=False,
            risk_classification="high",
        ),
        judge_deployment="strong-judge",
        route_correct=True,
        latency_seconds=2.5,
        retrieval_recall=1.0,
        task_success=True,
        source_attributed=True,
        sql_correct=False,
    )

    values = {score["name"]: score["value"] for score in client.scores}
    assert values["accuracy"] == pytest.approx(2 / 3)
    assert values["task_success"] == 1
    assert values["judge_task_success"] == 0
    assert values["retrieval_recall"] == 1
    assert values["sql_correctness"] == 0
    assert values["latency_seconds"] == 2.5


def test_offline_langfuse_scores_include_measured_safety_metrics():
    class FakeObservation:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def update(self, **kwargs):
            self.output = kwargs["output"]

    class FakeLangfuse:
        def __init__(self):
            self.scores = []
            self.api = SimpleNamespace(
                observations=SimpleNamespace(
                    get_many=lambda **_: SimpleNamespace(data=[object()])
                ),
                scores=SimpleNamespace(get_many=self._get_scores),
            )

        def start_as_current_observation(self, **_):
            self.observation = FakeObservation()
            return self.observation

        def create_score(self, **kwargs):
            self.scores.append(kwargs)

        def flush(self):
            pass

        def _get_scores(self, **_):
            return SimpleNamespace(
                data=[SimpleNamespace(name=score["name"]) for score in self.scores]
            )

    client = FakeLangfuse()
    report = {
        "slos": {
            "Accuracy": {"observed": 0.9, "sample_count": 10, "met": True},
            "Latency": {"observed": 1.2, "sample_count": 10, "met": True},
            "Recall": {"observed": 0.8, "sample_count": 10, "met": True},
            "Task Success Rate": {"observed": 0.9, "sample_count": 10, "met": True},
            "Query Routing Accuracy": {"observed": 1.0, "sample_count": 5, "met": True},
            "SQL Correctness": {"observed": 0.9, "sample_count": 5, "met": False},
            "Source Attribution Rate": {
                "observed": 1.0,
                "sample_count": 5,
                "met": True,
            },
            "Unauthorized Data Access (RBAC)": {
                "observed": 0,
                "sample_count": 8,
                "met": True,
            },
            "Guardrail Effectiveness": {
                "observed": 1.0,
                "sample_count": 4,
                "met": True,
                "scope": "Deterministic checks; prompt injection unverified.",
            },
            "Critical Misclassification Rate": {
                "observed": 0.0,
                "sample_count": 1,
                "met": True,
            },
            "Escalation Recall": {"observed": 1.0, "sample_count": 20, "met": True},
            "Risk Classification Accuracy": {
                "observed": 0.95,
                "sample_count": 20,
                "met": True,
            },
        },
        "safety_dataset_coverage": {
            "mandatory_escalation_case_count": 20,
            "critical_case_count": 1,
            "non_critical_case_count": 27,
        },
        "offline_evaluation": {
            "guardrails": {
                "dataset_id": "friis-guardrail-attacks",
                "dataset_version": "1",
                "unverified_cases": [{"case_id": "GR-PROMPT-INJECTION"}],
            }
        },
    }

    publish_offline_scores(
        client,
        {"dataset_id": "safety-test", "case_count": 5, "version": "1"},
        report,
    )

    assert {
        score["name"]
        for score in client.scores
    } >= {
        "accuracy",
        "latency_p95_seconds",
        "retrieval_recall",
        "task_success_rate",
        "sql_correctness",
        "source_attribution_rate",
        "critical_misclassification_rate",
        "escalation_recall",
        "rbac_violations",
        "guardrail_effectiveness",
        "query_routing_accuracy",
        "risk_classification_accuracy",
    }
    guardrail_score = next(
        score
        for score in client.scores
        if score["name"] == "guardrail_effectiveness"
    )
    assert guardrail_score["metadata"]["dataset_id"] == "friis-guardrail-attacks"
    assert client.observation.output["evaluation_context"] == {
        "safety_dataset_coverage": report["safety_dataset_coverage"],
        "guardrail_scope": "Deterministic checks; prompt injection unverified.",
        "guardrail_unverified_cases": ["GR-PROMPT-INJECTION"],
    }
