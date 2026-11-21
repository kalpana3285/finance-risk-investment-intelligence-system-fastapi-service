"""Run the FRIIS golden dataset against the API and report documented SLOs."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import os
import re
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

import httpx
from dotenv import load_dotenv
from fastapi import HTTPException
from openai import AsyncAzureOpenAI
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, create_engine, insert, select
from sqlalchemy.pool import StaticPool

from agents.control_plane import (
    PortfolioMarketAnalystAgent,
    QueryContext,
    QueryPlanner,
)
from prompts.catalog import get_prompt
from schemas import QueryRequest
from security.auth import Principal, Role
from services.database import (
    asset_risk_logs,
    investment_decisions,
    market_indicators,
    metadata,
    portfolio_holdings,
    portfolios,
    query_requests,
)
from services.database_api_service import DatabaseAPIService
from services.guardrails import GuardrailsValidator

DEFAULT_DATASET_PATH = Path(__file__).with_name("golden_dataset_v1.json")
DEFAULT_GUARDRAIL_DATASET_PATH = Path(__file__).with_name(
    "guardrail_attack_dataset_v1.json"
)
TERMINAL_STATUSES = {
    "completed",
    "needs_clarification",
    "escalated",
    "failed",
}
POLL_INTERVAL_SECONDS = 1.0
QUERY_TIMEOUT_SECONDS = 180.0

RiskClass = Literal[
    "not_applicable",
    "low",
    "moderate",
    "medium",
    "high",
    "critical",
    "requires_human_review",
]


def _positive_timeout_seconds(value: str) -> float:
    try:
        seconds = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number of seconds") from exc
    if not math.isfinite(seconds) or seconds <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return seconds

_EVALUATOR_PROMPT = get_prompt("finance-rag-evaluator")


class JudgeScores(BaseModel):
    model_config = ConfigDict(extra="forbid")

    faithfulness: float = Field(ge=0, le=1)
    answer_relevance: float = Field(ge=0, le=1)
    context_precision: float = Field(ge=0, le=1)
    context_recall: float = Field(ge=0, le=1)
    correctness: float = Field(ge=0, le=1)
    usefulness: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    task_success: bool
    risk_classification: RiskClass


def load_golden_cases(dataset_path: Path = DEFAULT_DATASET_PATH) -> dict[str, Any]:
    """Load and minimally validate the project's versioned evaluation dataset."""
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    cases = dataset.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError(f"{dataset_path} must contain a non-empty cases list")
    if dataset.get("case_count") != len(cases):
        raise ValueError(
            f"{dataset_path} declares {dataset.get('case_count')} cases, "
            f"but contains {len(cases)}"
        )
    required_fields = {
        "id",
        "category",
        "question",
        "expected_route",
        "expected_risk_class",
        "answer_rubric",
        "required_evidence",
        "expected_escalation",
    }
    for index, case in enumerate(cases, start=1):
        if not isinstance(case, dict) or not required_fields.issubset(case):
            raise ValueError(f"Case {index} is missing required evaluation fields")
    return dataset


def load_guardrail_attack_cases(
    dataset_path: Path = DEFAULT_GUARDRAIL_DATASET_PATH,
) -> dict[str, Any]:
    """Load the versioned deterministic and end-to-end guardrail attack cases."""
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    cases = dataset.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError(f"{dataset_path} must contain a non-empty cases list")
    if dataset.get("case_count") != len(cases):
        raise ValueError(
            f"{dataset_path} declares {dataset.get('case_count')} cases, "
            f"but contains {len(cases)}"
        )
    required_fields = {"id", "attack_type", "surface"}
    for case in cases:
        if not isinstance(case, dict) or not required_fields.issubset(case):
            raise ValueError(
                f"{dataset_path} cases must contain {sorted(required_fields)}"
            )
    return dataset


def planned_route(case: Mapping[str, Any], planner: QueryPlanner | None = None) -> str:
    """Map the production deterministic planner's decision to the golden labels."""
    active_planner = planner or QueryPlanner()
    plan = active_planner.create_plan(
        QueryContext(
            query_id=str(case["id"]),
            question=str(case["question"]),
            portfolio_id=case.get("portfolio_id"),
        )
    )
    if plan.mandatory_escalation_reason:
        return "human_escalation"
    if plan.clarification_question:
        return "clarification_required"
    specialist_set = set(plan.specialists)
    has_document = "Document Retrieval agent" in specialist_set
    has_structured = "Portfolio / Market Analyst agent" in specialist_set
    if has_document and has_structured:
        return "hybrid_risk"
    if has_document:
        return "document_retrieval"
    if has_structured:
        return "structured_data"
    return "no_route"


def _citation_context(citations: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            key: citation.get(key)
            for key in (
                "source_id",
                "source_title",
                "source_version",
                "evidence_type",
                "excerpt",
                "page_number",
                "section",
                "record_reference",
            )
            if citation.get(key) is not None
        }
        for citation in citations
    ]


_EVIDENCE_TABLES = (
    "portfolio_holdings",
    "asset_risk_logs",
    "investment_decisions",
    "market_indicators",
    "portfolios",
)
_EVIDENCE_PRIMARY_KEYS = {
    "portfolio_holdings": "holding_id",
    "asset_risk_logs": "risk_id",
    "investment_decisions": "decision_id",
    "market_indicators": "indicator_id",
    "portfolios": "portfolio_id",
}
_SECTION_STOP_WORDS = frozenset({"and", "by", "for", "in", "of", "the", "to"})


def _normalized_reference(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _required_evidence_targets(
    requirements: Sequence[str], fixtures: Mapping[str, Any]
) -> list[tuple[str, ...]]:
    targets: list[tuple[str, ...]] = []
    for requirement in requirements:
        document = re.match(
            r"^\s*(project-pdf-\d+|project[\s-]+blueprint)\s*§\s*(.+)$",
            requirement,
            flags=re.IGNORECASE,
        )
        if document:
            section = [
                word
                for word in _normalized_reference(document.group(2)).split()
                if word not in _SECTION_STOP_WORDS
            ]
            if section and section[0].isdigit():
                section = section[1:]
            targets.append(
                ("document", _normalized_reference(document.group(1)), " ".join(section))
            )
            continue

        normalized = _normalized_reference(requirement)
        if normalized == "fixture friis sql golden fixture v1":
            continue
        table = next(
            (
                name
                for name in _EVIDENCE_TABLES
                if re.search(rf"\b{re.escape(name)}\b", requirement, re.IGNORECASE)
            ),
            None,
        )
        if table is None:
            raise ValueError(
                f"Unsupported required-evidence reference: {requirement!r}"
            )

        row_ids_match = re.search(
            r"\brows?\s+(\d+(?:\s+and\s+\d+)*)", normalized
        )
        if row_ids_match:
            targets.extend(
                ("record", f"{table}:{row_id}")
                for row_id in re.findall(r"\d+", row_ids_match.group(1))
            )
            continue

        portfolio_match = re.search(
            r"\bportfolio(?:\s+id)?\s+(\d+)\b", normalized
        )
        if portfolio_match:
            portfolio_id = int(portfolio_match.group(1))
            rows = [
                row
                for row in fixtures.get(table, [])
                if row.get("portfolio_id") == portfolio_id
            ]
            if rows:
                targets.extend(
                    (
                        "record",
                        f"{table}:{row[_EVIDENCE_PRIMARY_KEYS[table]]}",
                    )
                    for row in rows
                )
            continue

        targets.append(("table", table))
    return targets


def _required_evidence_counts(
    case: Mapping[str, Any],
    citations: Sequence[Mapping[str, Any]],
    fixtures: Mapping[str, Any],
) -> tuple[int, int]:
    targets = _required_evidence_targets(case["required_evidence"], fixtures)
    retrieved = 0
    for target in targets:
        kind = target[0]
        matched = False
        for citation in citations:
            reference = str(citation.get("record_reference") or "").casefold()
            if kind == "record":
                matched = reference == target[1]
            elif kind == "table":
                matched = reference.startswith(f"{target[1]}:")
            else:
                source_matches = target[1] in (
                    _normalized_reference(str(citation.get("source_id") or "")),
                    _normalized_reference(str(citation.get("source_title") or "")),
                )
                section = target[2].split()
                section_value = citation.get("section") or citation.get("excerpt")
                section_matches = not section or all(
                    word in _normalized_reference(str(section_value or "")).split()
                    for word in section
                )
                matched = source_matches and section_matches
            if matched:
                break
        retrieved += matched
    return retrieved, len(targets)


def _has_source_attribution(citations: Sequence[Mapping[str, Any]]) -> bool:
    return bool(citations) and all(
        bool(citation.get("source_id"))
        and any(
            citation.get(field) not in (None, "")
            for field in ("excerpt", "page_number", "section", "record_reference")
        )
        for citation in citations
    )


async def submit_and_wait(
    client: httpx.AsyncClient,
    *,
    api_url: str,
    token: str,
    case: Mapping[str, Any],
    timeout_seconds: float = QUERY_TIMEOUT_SECONDS,
    poll_interval_seconds: float = POLL_INTERVAL_SECONDS,
) -> tuple[dict[str, Any], float]:
    """Submit one golden case and wait until the API returns a terminal result."""
    headers = {"Authorization": f"Bearer {token}"}
    request_body = {
        "question": case["question"],
        "portfolio_id": case.get("portfolio_id"),
    }
    started = time.perf_counter()
    submitted = await client.post(
        f"{api_url.rstrip('/')}/api/v1/queries",
        headers=headers,
        json=request_body,
    )
    submitted.raise_for_status()
    query_id = submitted.json()["query_id"]

    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while True:
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            raise TimeoutError(
                f"Query {query_id} did not finish within {timeout_seconds:g} seconds"
            )
        try:
            response = await client.get(
                f"{api_url.rstrip('/')}/api/v1/queries/{query_id}",
                headers=headers,
                timeout=min(30.0, remaining),
            )
        except httpx.TimeoutException as exc:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise TimeoutError(
                    f"Timed out polling query {query_id} after "
                    f"{timeout_seconds:g} seconds"
                ) from exc
            await asyncio.sleep(min(poll_interval_seconds, remaining))
            continue
        response.raise_for_status()
        result = response.json()
        status = result.get("status")
        if status in TERMINAL_STATUSES:
            result["query_id"] = query_id
            return result, time.perf_counter() - started
        if status not in {"queued", "processing"}:
            raise ValueError(
                f"Query {query_id} returned an unrecognized status: {status!r}"
            )
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            raise TimeoutError(
                f"Query {query_id} did not finish within {timeout_seconds:g} seconds"
            )
        await asyncio.sleep(min(poll_interval_seconds, remaining))


async def judge_case(
    client: AsyncAzureOpenAI,
    *,
    deployment: str,
    case: Mapping[str, Any],
    result: Mapping[str, Any],
) -> JudgeScores:
    """Score one API result with a bounded JSON LLM-as-a-judge response."""
    answer = result.get("answer") or result.get("clarification_question") or ""
    payload = {
        "question": case["question"],
        "answer": answer,
        "query_status": result.get("status"),
        "answer_rubric": case["answer_rubric"],
        "required_evidence": case["required_evidence"],
        "expected_result": case.get("expected_result"),
        "expected_risk_class": case["expected_risk_class"],
        "citations": _citation_context(result.get("citations") or []),
    }
    request_options: dict[str, Any] = {
        "model": deployment,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": _EVALUATOR_PROMPT["messages"][0]["role"],
                "content": _EVALUATOR_PROMPT["messages"][0]["content"],
            },
            {
                "role": _EVALUATOR_PROMPT["messages"][1]["role"],
                "content": json.dumps(payload, ensure_ascii=True),
            },
        ],
    }
    deployment_name = deployment.casefold()
    if not deployment_name.startswith("gpt-5") or deployment_name.startswith(
        "gpt-5-chat"
    ):
        request_options["temperature"] = 0
    response = await client.chat.completions.create(
        **request_options,
    )
    content = response.choices[0].message.content
    if not content:
        raise ValueError(f"Judge returned an empty result for case {case['id']}")
    return JudgeScores.model_validate_json(content)


async def evaluate_dataset(
    *,
    dataset: Mapping[str, Any],
    api_url: str,
    api_token: str,
    judge_client: AsyncAzureOpenAI,
    judge_deployment: str,
    query_timeout_seconds: float = QUERY_TIMEOUT_SECONDS,
    langfuse_client: Any | None = None,
    sql_case_results: Mapping[str, bool] | None = None,
) -> dict[str, Any]:
    """Run golden cases serially through the API and calculate SLO measurements."""
    outcomes: list[dict[str, Any]] = []
    total_cases = len(dataset["cases"])
    async with httpx.AsyncClient(timeout=30.0) as api_client:
        for case in dataset["cases"]:
            case_started = time.perf_counter()
            api_result: dict[str, Any] | None = None
            try:
                api_result, latency_seconds = await submit_and_wait(
                    api_client,
                    api_url=api_url,
                    token=api_token,
                    case=case,
                    timeout_seconds=query_timeout_seconds,
                )
                scores = await judge_case(
                    judge_client,
                    deployment=judge_deployment,
                    case=case,
                    result=api_result,
                )
            except Exception as exc:
                observed_route = planned_route(case)
                if api_result is None:
                    latency_seconds = time.perf_counter() - case_started
                citations = (api_result or {}).get("citations") or []
                sql_correct = (sql_case_results or {}).get(case["id"])
                retrieved_evidence, required_evidence = _required_evidence_counts(
                    case,
                    citations,
                    dataset.get("fixtures", {}),
                )
                outcome = {
                    "case_id": case["id"],
                    "category": case["category"],
                    "latency_seconds": latency_seconds,
                    "status": (api_result or {}).get(
                        "status", "evaluation_error"
                    ),
                    "expected_route": case["expected_route"],
                    "planned_route": observed_route,
                    "route_correct": observed_route == case["expected_route"],
                    "expected_escalation": case["expected_escalation"],
                    "actual_escalation": (api_result or {}).get("status")
                    == "escalated",
                    "expected_risk_class": case["expected_risk_class"],
                    "predicted_risk_class": None,
                    "source_attributed": _has_source_attribution(citations),
                    "retrieved_relevant_documents": retrieved_evidence,
                    "total_relevant_documents": required_evidence,
                    "retrieval_recall": (
                        retrieved_evidence / required_evidence
                        if required_evidence
                        else None
                    ),
                    "sql_correct": sql_correct,
                    "scores": None,
                    "evaluation_error_type": type(exc).__name__,
                }
                outcome["task_success"] = _deterministic_task_success(outcome)
                outcomes.append(outcome)
                report = build_slo_report(dataset, outcomes)
                report["online_evaluation"] = {
                    "status": "partial",
                    "completed_cases": len(outcomes) - 1,
                    "total_cases": total_cases,
                    "failed_case_id": case["id"],
                    "error_type": type(exc).__name__,
                }
                report["judge"] = {
                    "model": judge_deployment,
                    "prompt": _EVALUATOR_PROMPT["name"],
                    "prompt_version": _EVALUATOR_PROMPT["version"],
                }
                return report
            actual_escalation = api_result.get("status") == "escalated"
            citations = api_result.get("citations") or []
            observed_route = planned_route(case)
            sql_correct = (sql_case_results or {}).get(case["id"])
            retrieved_evidence, required_evidence = _required_evidence_counts(
                case,
                citations,
                dataset.get("fixtures", {}),
            )
            outcome = {
                "case_id": case["id"],
                "category": case["category"],
                "latency_seconds": latency_seconds,
                "status": api_result.get("status"),
                "expected_route": case["expected_route"],
                "planned_route": observed_route,
                "route_correct": observed_route == case["expected_route"],
                "expected_escalation": case["expected_escalation"],
                "actual_escalation": actual_escalation,
                "expected_risk_class": case["expected_risk_class"],
                "predicted_risk_class": scores.risk_classification,
                "source_attributed": _has_source_attribution(citations),
                "retrieved_relevant_documents": retrieved_evidence,
                "total_relevant_documents": required_evidence,
                "retrieval_recall": (
                    retrieved_evidence / required_evidence
                    if required_evidence
                    else None
                ),
                "sql_correct": sql_correct,
                "scores": scores.model_dump(),
            }
            outcome["task_success"] = _deterministic_task_success(outcome)
            outcomes.append(outcome)
            if langfuse_client is not None:
                trace_id = _uuid_trace_id(api_result.get("query_id"))
                if trace_id is not None:
                    _publish_query_scores(
                        langfuse_client,
                        trace_id=trace_id,
                        case=case,
                        scores=scores,
                        judge_deployment=judge_deployment,
                        route_correct=observed_route == case["expected_route"],
                        latency_seconds=latency_seconds,
                        retrieval_recall=outcome["retrieval_recall"],
                        task_success=outcome["task_success"],
                        source_attributed=_has_source_attribution(citations),
                        sql_correct=(sql_case_results or {}).get(case["id"]),
                    )
    report = build_slo_report(dataset, outcomes)
    report["online_evaluation"] = {
        "status": "completed",
        "completed_cases": len(outcomes),
        "total_cases": total_cases,
    }
    report["judge"] = {
        "model": judge_deployment,
        "prompt": _EVALUATOR_PROMPT["name"],
        "prompt_version": _EVALUATOR_PROMPT["version"],
    }
    if langfuse_client is not None:
        langfuse_client.flush()
    return report


def _uuid_trace_id(query_id: Any) -> str | None:
    if not isinstance(query_id, str):
        return None
    try:
        from uuid import UUID

        return UUID(query_id).hex
    except (ValueError, TypeError, AttributeError):
        return None


def _publish_query_scores(
    langfuse_client: Any,
    *,
    trace_id: str,
    case: Mapping[str, Any],
    scores: JudgeScores,
    judge_deployment: str,
    route_correct: bool,
    latency_seconds: float,
    retrieval_recall: float | None,
    task_success: bool,
    source_attributed: bool,
    sql_correct: bool | None,
) -> None:
    metadata = {
        "dataset_id": "friis-golden-evaluation",
        "case_id": case["id"],
        "judge_model": judge_deployment,
        "judge_prompt": _EVALUATOR_PROMPT["name"],
        "judge_prompt_version": _EVALUATOR_PROMPT["version"],
    }
    numeric_scores = {
        "accuracy": (
            float(route_correct)
            + float(scores.risk_classification == case["expected_risk_class"])
            + (
                float(sql_correct is True)
                if case.get("category") == "portfolio_sql"
                else 0.0
            )
        )
        / (3 if case.get("category") == "portfolio_sql" else 2),
        "faithfulness": scores.faithfulness,
        "answer_relevance": scores.answer_relevance,
        "context_precision": scores.context_precision,
        "context_recall": scores.context_recall,
        "correctness": scores.correctness,
        "usefulness": scores.usefulness,
        "judge_confidence": scores.confidence,
        "risk_classification_accuracy": float(
            scores.risk_classification == case["expected_risk_class"]
        ),
        "query_routing_accuracy": float(route_correct),
        "source_attribution": float(source_attributed),
        "latency_seconds": latency_seconds,
    }
    if retrieval_recall is not None:
        numeric_scores["retrieval_recall"] = retrieval_recall
    for name, value in numeric_scores.items():
        langfuse_client.create_score(
            name=name,
            value=float(value),
            trace_id=trace_id,
            data_type="NUMERIC",
            metadata=metadata,
        )
    langfuse_client.create_score(
        name="task_success",
        value=float(task_success),
        trace_id=trace_id,
        data_type="BOOLEAN",
        metadata=metadata,
    )
    langfuse_client.create_score(
        name="judge_task_success",
        value=float(scores.task_success),
        trace_id=trace_id,
        data_type="BOOLEAN",
        metadata=metadata,
    )
    langfuse_client.create_score(
        name="risk_classification",
        value=scores.risk_classification,
        trace_id=trace_id,
        data_type="CATEGORICAL",
        metadata=metadata,
    )
    if sql_correct is not None:
        langfuse_client.create_score(
            name="sql_correctness",
            value=float(sql_correct),
            trace_id=trace_id,
            data_type="NUMERIC",
            metadata=metadata,
        )


def _rate(values: Sequence[bool]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _threshold_slo(
    observed: float | None,
    *,
    operator: str,
    target: float,
    sample_count: int,
    unit: str = "pass_rate",
) -> dict[str, Any]:
    if operator == ">=":
        met = observed >= target if observed is not None else None
    elif operator == "<=":
        met = observed <= target if observed is not None else None
    elif operator == "<":
        met = observed < target if observed is not None else None
    else:
        raise ValueError(f"Unsupported SLO operator: {operator}")
    target_display = (
        f"{operator}{target:g}" if unit == "seconds" else f"{operator}{target:.0%}"
    )
    return {
        "target": target_display,
        "observed": observed,
        "unit": unit,
        "sample_count": sample_count,
        "met": met,
    }


def _score_pass_rate(
    outcomes: Sequence[Mapping[str, Any]], score_name: str, threshold: float
) -> float | None:
    values = [
        float(outcome["scores"][score_name])
        for outcome in outcomes
        if outcome.get("scores", {}).get(score_name) is not None
    ]
    return _rate([value >= threshold for value in values])


def _prediction_results(outcomes: Sequence[Mapping[str, Any]]) -> list[bool]:
    predictions: list[bool] = []
    for outcome in outcomes:
        predictions.append(bool(outcome.get("route_correct")))
        predictions.append(
            outcome.get("predicted_risk_class") == outcome.get("expected_risk_class")
        )
        if outcome.get("category") == "portfolio_sql":
            predictions.append(outcome.get("sql_correct") is True)
    return predictions


def _deterministic_task_success(outcome: Mapping[str, Any]) -> bool:
    expected_status = (
        "escalated" if outcome["expected_escalation"] else "completed"
    )
    evidence_count = int(outcome.get("total_relevant_documents") or 0)
    evidence_complete = (
        int(outcome.get("retrieved_relevant_documents") or 0) == evidence_count
        and (
            evidence_count > 0
            or (
                outcome.get("category") == "portfolio_sql"
                and outcome.get("sql_correct") is True
            )
        )
    )
    sql_correct = (
        outcome.get("category") != "portfolio_sql"
        or outcome.get("sql_correct") is True
    )
    return (
        outcome.get("status") == expected_status
        and bool(outcome.get("route_correct"))
        and outcome.get("predicted_risk_class") == outcome.get("expected_risk_class")
        and evidence_complete
        and sql_correct
    )


def _percentile_95(values: Sequence[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[math.ceil(0.95 * len(ordered)) - 1]


def _evaluation_engine(dataset: Mapping[str, Any]):
    """Create an isolated in-memory database seeded only with golden fixtures."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata.create_all(engine)
    fixtures = dataset["fixtures"]
    fixture_tables = {
        "portfolios": portfolios,
        "portfolio_holdings": portfolio_holdings,
        "asset_risk_logs": asset_risk_logs,
        "market_indicators": market_indicators,
        "investment_decisions": investment_decisions,
    }
    date_fields = {
        "last_updated",
        "assessment_date",
        "measurement_date",
        "decision_date",
    }
    with engine.begin() as connection:
        for fixture_name, table in fixture_tables.items():
            rows = []
            for fixture_row in fixtures.get(fixture_name, []):
                row = dict(fixture_row)
                for field in date_fields & row.keys():
                    if isinstance(row[field], str):
                        row[field] = date.fromisoformat(row[field])
                rows.append(row)
            if rows:
                connection.execute(insert(table), rows)
    return engine


def _json_record(evidence: Any) -> dict[str, Any] | None:
    excerpt = evidence.citation.excerpt
    if not excerpt:
        return None
    try:
        record = json.loads(excerpt)
    except (TypeError, json.JSONDecodeError):
        return None
    return record if isinstance(record, dict) else None


def _matches_expected(actual: Mapping[str, Any], expected: Mapping[str, Any]) -> bool:
    for key, wanted in expected.items():
        value = actual.get(key)
        if isinstance(wanted, bool):
            if value is not wanted:
                return False
        elif isinstance(wanted, (int, float)):
            try:
                if Decimal(str(value)) != Decimal(str(wanted)):
                    return False
            except (InvalidOperation, TypeError, ValueError):
                return False
        elif value != wanted:
            return False
    return True


def _record_rows(
    records: Sequence[Mapping[str, Any]], source_prefix: str
) -> list[dict[str, Any]]:
    rows = []
    for item in records:
        reference = item["record_reference"]
        if not reference.startswith(f"{source_prefix}:"):
            continue
        record = dict(item["record"])
        if source_prefix == "portfolios":
            portfolio_id = reference.split(":", 1)[1]
            record["portfolio_id"] = (
                int(portfolio_id) if portfolio_id.isdigit() else portfolio_id
            )
        rows.append({"record_reference": reference, "record": record})
    return rows


def _expected_source_prefix(expected: Any) -> str:
    if expected is None or (
        isinstance(expected, Mapping) and "portfolio_name" in expected
    ):
        return "portfolios"
    if isinstance(expected, list):
        if expected and "decision_id" in expected[0]:
            return "investment_decisions"
        return "portfolio_holdings"
    if "holding_count" in expected or "combined_allocation_percentage" in expected:
        return "portfolio_holdings"
    if "risk_id" in expected:
        return "asset_risk_logs"
    if "indicator_id" in expected:
        return "market_indicators"
    raise ValueError("SQL evaluation case has an unsupported expected result shape.")


def _actual_sql_result(
    case: Mapping[str, Any], records: Sequence[Mapping[str, Any]]
) -> Any:
    expected = case.get("expected_result")
    candidates = _record_rows(records, _expected_source_prefix(expected))
    if isinstance(expected, Mapping) and "combined_allocation_percentage" in expected:
        total = sum(
            (
                Decimal(str(item["record"].get("allocation_percentage") or 0))
                for item in candidates
                if item["record"].get("sector") == expected["sector"]
            ),
            Decimal(0),
        )
        return {
            "sector": expected["sector"],
            "combined_allocation_percentage": float(total),
        }
    if isinstance(expected, Mapping) and "holding_count" in expected:
        portfolio_id = expected["portfolio_id"]
        portfolio = next(
            (
                item["record"]
                for item in _record_rows(records, "portfolios")
                if item["record"]["portfolio_id"] == portfolio_id
            ),
            None,
        )
        if portfolio is None:
            return []
        return {
            "portfolio_id": portfolio_id,
            "holding_count": len(candidates),
        }
    return candidates


def _sql_results_match(actual: Any, expected: Any) -> bool:
    if expected is None:
        return actual == []
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            return False
        unmatched = [item["record"] for item in actual]
        for expected_row in expected:
            match_index = next(
                (
                    index
                    for index, actual_row in enumerate(unmatched)
                    if _matches_expected(actual_row, expected_row)
                ),
                None,
            )
            if match_index is None:
                return False
            unmatched.pop(match_index)
        return not unmatched
    if isinstance(expected, Mapping):
        if isinstance(actual, list):
            return (
                len(actual) == 1
                and _matches_expected(actual[0]["record"], expected)
            )
        return (
            isinstance(actual, Mapping)
            and actual.keys() == expected.keys()
            and _matches_expected(actual, expected)
        )
    return False


async def evaluate_sql_correctness(
    dataset: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Compare normalized structured-agent results with fixture results."""
    engine = _evaluation_engine(dataset)
    analyst = PortfolioMarketAnalystAgent(engine)
    outcomes: list[dict[str, Any]] = []
    try:
        for case in dataset["cases"]:
            if case["category"] != "portfolio_sql":
                continue
            context = QueryContext(
                query_id=f"eval-{case['id']}",
                question=case["question"],
                portfolio_id=case.get("portfolio_id"),
                authorized_portfolio_ids=(case.get("portfolio_id"),)
                if case.get("portfolio_id") is not None
                else (),
                all_portfolios_access=True,
            )
            result = await analyst.run(context)
            records = [
                {
                    "record_reference": item.citation.record_reference,
                    "record": _json_record(item),
                }
                for item in result.evidence
                if item.citation.record_reference and _json_record(item) is not None
            ]
            expected = case.get("expected_result")
            actual = _actual_sql_result(case, records)
            outcomes.append(
                {
                    "case_id": case["id"],
                    "passed": _sql_results_match(actual, expected),
                    "record_count": len(records),
                    "actual_result": actual,
                    "expected_result": expected,
                }
            )
    finally:
        engine.dispose()
    return outcomes


async def evaluate_rbac(dataset: Mapping[str, Any]) -> dict[str, Any]:
    """Exercise tenant isolation and verify structured authorization audit logs."""
    engine = _evaluation_engine(dataset)
    service = DatabaseAPIService(
        engine, query_worker_ready=True, ingestion_worker_ready=True
    )
    owner = Principal(
        subject="eval-owner",
        roles=frozenset({Role.ANALYST}),
        portfolio_ids=frozenset({901}),
    )
    other_owner = Principal(
        subject="eval-other-owner",
        roles=frozenset({Role.ANALYST}),
        portfolio_ids=frozenset({902}),
    )
    checks: list[dict[str, Any]] = []
    audit_events: list[dict[str, Any]] = []
    service_logger = logging.getLogger("services.database_api_service")

    class AuditCapture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            if getattr(record, "event", None) == "authorization.denied":
                audit_events.append(
                    {
                        "principal_subject": getattr(
                            record, "principal_subject", None
                        ),
                        "action": getattr(record, "action", None),
                        "resource_type": getattr(record, "resource_type", None),
                        "resource_id": getattr(record, "resource_id", None),
                    }
                )

    audit_capture = AuditCapture(level=logging.WARNING)
    service_logger.addHandler(audit_capture)

    def add_check(name: str, passed: bool) -> None:
        checks.append({"case": name, "passed": passed})

    try:
        add_check(
            "owner_reads_authorized_portfolio",
            await service.get_portfolio(owner, 901) is not None,
        )
        try:
            await service.get_portfolio(owner, 902)
        except HTTPException as exc:
            add_check("cross_tenant_portfolio_read_denied", exc.status_code == 403)
        else:
            add_check("cross_tenant_portfolio_read_denied", False)
        try:
            await service.submit_query(
                owner,
                QueryRequest(question="Summarize this portfolio.", portfolio_id=902),
            )
        except HTTPException as exc:
            add_check("cross_tenant_query_submission_denied", exc.status_code == 403)
        else:
            add_check("cross_tenant_query_submission_denied", False)
        with engine.connect() as connection:
            denied_query_rows = connection.execute(
                select(query_requests.c.query_id).where(
                    and_(
                        query_requests.c.owner_subject == owner.subject,
                        query_requests.c.portfolio_id == 902,
                    )
                )
            ).all()
        add_check("denied_query_submission_not_persisted", not denied_query_rows)
        add_check(
            "other_owner_reads_authorized_portfolio",
            await service.get_portfolio(other_owner, 902) is not None,
        )
        submitted = await service.submit_query(
            owner,
            QueryRequest(question="Summarize my authorized portfolio.", portfolio_id=901),
        )
        add_check(
            "query_owner_isolation",
            await service.get_query(other_owner, submitted.query_id) is None,
        )
    finally:
        service_logger.removeHandler(audit_capture)
        engine.dispose()

    expected_audit_events = {
        ("eval-owner", "portfolio.read", "portfolio", 902),
        ("eval-owner", "query.submit", "portfolio", 902),
        ("eval-other-owner", "query.read", "query", submitted.query_id),
    }
    observed_audit_events = {
        (
            event["principal_subject"],
            event["action"],
            event["resource_type"],
            event["resource_id"],
        )
        for event in audit_events
    }
    for subject, action, resource_type, resource_id in expected_audit_events:
        add_check(
            f"audit_log_{action}_{resource_id}",
            (subject, action, resource_type, resource_id) in observed_audit_events,
        )

    violations = sum(not item["passed"] for item in checks)
    return {
        "sample_count": len(checks),
        "violation_count": violations,
        "passed_checks": len(checks) - violations,
        "passed": violations == 0 and bool(checks),
        "audit_log_count": len(audit_events),
        "audit_logs_verified": len(expected_audit_events & observed_audit_events),
        "checks": checks,
    }


def evaluate_guardrails() -> dict[str, Any]:
    """Run deterministic controls from the versioned adversarial test dataset."""
    dataset = load_guardrail_attack_cases()
    validator = GuardrailsValidator()
    import tldextract
    from tldextract import tldextract as tldextract_impl

    extractor = tldextract.TLDExtract(
        cache_dir=None,
        suffix_list_urls=(),
        fallback_to_snapshot=True,
    )
    tldextract.TLD_EXTRACTOR = extractor
    tldextract_impl.TLD_EXTRACTOR = extractor

    checks: list[dict[str, Any]] = []
    unverified_cases: list[dict[str, str]] = []
    for case in dataset["cases"]:
        if case["surface"] == "end_to_end":
            unverified_cases.append(
                {
                    "case_id": case["id"],
                    "attack_type": case["attack_type"],
                    "reason": "Requires an online model/API assertion.",
                }
            )
            continue
        if case["surface"] == "input":
            payload = case.get("payload")
            if "payload_length" in case:
                payload = "q" * int(case["payload_length"])
            decision = validator.validate_input(payload)
            passed = decision.allowed is case["expected_allowed"]
        elif case["surface"] == "output":
            decision = validator.validate_output(case["payload"])
            passed = all(
                forbidden.casefold() not in decision.sanitized_text.casefold()
                for forbidden in case["must_not_contain"]
            )
        else:
            raise ValueError(f"Unsupported guardrail test surface: {case['surface']}")
        checks.append(
            {
                "case_id": case["id"],
                "attack_type": case["attack_type"],
                "passed": passed,
            }
        )
    passed = sum(bool(check["passed"]) for check in checks)
    return {
        "dataset_id": dataset["dataset_id"],
        "dataset_version": dataset["version"],
        "sample_count": len(checks),
        "passed_count": passed,
        "checks": checks,
        "unverified_cases": unverified_cases,
        "unverified_count": len(unverified_cases),
        "pass_rate": passed / len(checks) if checks else None,
        "scope": (
            "Deterministic input-boundary and output-PII controls only; the "
            "prompt-injection case is recorded as unverified, not scored."
        ),
    }


async def evaluate_offline_metrics(
    dataset: Mapping[str, Any],
) -> dict[str, Any]:
    route_cases = [
        {
            "case_id": case["id"],
            "expected_route": case["expected_route"],
            "planned_route": planned_route(case),
            "passed": planned_route(case) == case["expected_route"],
        }
        for case in dataset["cases"]
    ]
    sql_cases = await evaluate_sql_correctness(dataset)
    rbac = await evaluate_rbac(dataset)
    guardrails = evaluate_guardrails()
    return {
        "routing_cases": route_cases,
        "sql_cases": sql_cases,
        "rbac": rbac,
        "guardrails": guardrails,
    }


def apply_offline_metrics(
    report: dict[str, Any], offline: Mapping[str, Any]
) -> dict[str, Any]:
    """Replace placeholder SLOs with deterministic isolated measurements."""
    routes = offline["routing_cases"]
    sql_cases = offline["sql_cases"]
    rbac = offline["rbac"]
    guardrails = offline["guardrails"]
    report["slos"]["Query Routing Accuracy"] = _threshold_slo(
        _rate([bool(item["passed"]) for item in routes]),
        operator=">=",
        target=0.95,
        sample_count=len(routes),
    )
    report["slos"]["SQL Correctness"] = _threshold_slo(
        _rate([bool(item["passed"]) for item in sql_cases]),
        operator=">=",
        target=0.95,
        sample_count=len(sql_cases),
        unit="exact_result_match_rate",
    )
    accuracy_predictions = [
        bool(item["passed"]) for item in routes
    ] + [bool(item["passed"]) for item in sql_cases]
    accuracy_predictions.extend(
        outcome.get("predicted_risk_class") == outcome.get("expected_risk_class")
        for outcome in report.get("cases", [])
    )
    report["slos"]["Accuracy"] = _threshold_slo(
        _rate(accuracy_predictions),
        operator=">=",
        target=0.85,
        sample_count=len(accuracy_predictions),
        unit="correct_predictions/total_predictions",
    )
    report["slos"]["Unauthorized Data Access (RBAC)"] = {
        "target": "0 violations",
        "observed": rbac["violation_count"],
        "unit": "violations",
        "sample_count": rbac["sample_count"],
        "met": rbac["violation_count"] == 0,
    }
    report["slos"]["Guardrail Effectiveness"] = _threshold_slo(
        guardrails["pass_rate"],
        operator=">=",
        target=1.0,
        sample_count=guardrails["sample_count"],
    ) | {"scope": guardrails["scope"]}
    report["offline_evaluation"] = {
        "routing_cases": routes,
        "sql_cases": sql_cases,
        "rbac": rbac,
        "guardrails": guardrails,
    }
    return report


def publish_offline_scores(
    langfuse_client: Any,
    dataset: Mapping[str, Any],
    report: Mapping[str, Any],
) -> str:
    """Publish a score-bearing Langfuse evaluation trace and return its ID."""
    trace_id = uuid4().hex
    score_to_slo = {
        "accuracy": "Accuracy",
        "latency_p95_seconds": "Latency",
        "retrieval_recall": "Recall",
        "task_success_rate": "Task Success Rate",
        "sql_correctness": "SQL Correctness",
        "source_attribution_rate": "Source Attribution Rate",
        "critical_misclassification_rate": "Critical Misclassification Rate",
        "escalation_recall": "Escalation Recall",
        "rbac_violations": "Unauthorized Data Access (RBAC)",
        "guardrail_effectiveness": "Guardrail Effectiveness",
        "query_routing_accuracy": "Query Routing Accuracy",
        "risk_classification_accuracy": "Risk Classification Accuracy",
    }
    scores: dict[str, float | int] = {}
    for score_name, slo_name in score_to_slo.items():
        value = report["slos"][slo_name]["observed"]
        if value is not None:
            scores[score_name] = value
    with langfuse_client.start_as_current_observation(
        name="friis-golden-set-offline-evaluation",
        as_type="span",
        trace_context={"trace_id": trace_id},
        input={"dataset_id": dataset["dataset_id"], "case_count": dataset["case_count"]},
        metadata={"dataset_version": dataset["version"], "content_captured": False},
    ) as trace:
        trace.update(
            output={
                "scores": scores,
                "slo_met": {
                    name: metric["met"] for name, metric in report["slos"].items()
                },
                "evaluation_context": {
                    "safety_dataset_coverage": report.get(
                        "safety_dataset_coverage"
                    ),
                    "guardrail_scope": report["slos"][
                        "Guardrail Effectiveness"
                    ].get("scope"),
                    "guardrail_unverified_cases": [
                        case["case_id"]
                        for case in report.get("offline_evaluation", {})
                        .get("guardrails", {})
                        .get("unverified_cases", [])
                    ],
                },
            }
        )
        for name, value in scores.items():
            score_dataset_id = dataset["dataset_id"]
            score_dataset_version = dataset["version"]
            if name == "guardrail_effectiveness":
                guardrail_dataset = report.get("offline_evaluation", {}).get(
                    "guardrails", {}
                )
                score_dataset_id = guardrail_dataset.get(
                    "dataset_id", score_dataset_id
                )
                score_dataset_version = guardrail_dataset.get(
                    "dataset_version", score_dataset_version
                )
            langfuse_client.create_score(
                name=name,
                value=float(value),
                trace_id=trace_id,
                data_type="NUMERIC",
                comment=(
                    f"Evaluation dataset {dataset['dataset_id']} "
                    f"v{dataset['version']}; aggregate metric."
                ),
                metadata={
                    "sample_count": report["slos"][score_to_slo[name]][
                        "sample_count"
                    ],
                    "target_met": report["slos"][score_to_slo[name]]["met"],
                    "dataset_id": score_dataset_id,
                    "dataset_version": score_dataset_version,
                },
            )
    langfuse_client.flush()
    expected_names = set(scores)
    verification_deadline = time.monotonic() + 35
    while time.monotonic() < verification_deadline:
        observation_page = langfuse_client.api.observations.get_many(
            trace_id=trace_id,
            fields="core,basic,io",
            limit=100,
        )
        score_page = langfuse_client.api.scores.get_many(
            trace_id=trace_id,
            limit=100,
        )
        observed_names = {item.name for item in score_page.data}
        if observation_page.data and expected_names.issubset(observed_names):
            return trace_id
        time.sleep(2)
    raise TimeoutError(
        "Langfuse accepted the evaluation trace flush, but the trace and all "
        "aggregate scores were not readable before the verification deadline."
    )


def build_slo_report(
    dataset: Mapping[str, Any], outcomes: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Aggregate evaluated cases using the targets in the project's SLO sheet."""
    scored = [
        outcome for outcome in outcomes if isinstance(outcome.get("scores"), Mapping)
    ]
    score_names = (
        "faithfulness",
        "answer_relevance",
        "context_precision",
        "context_recall",
        "correctness",
        "usefulness",
        "confidence",
    )
    score_averages = {
        name: (
            sum(float(outcome["scores"][name]) for outcome in scored) / len(scored)
            if scored
            else None
        )
        for name in score_names
    }

    cases_by_id = {case["id"]: case for case in dataset["cases"]}
    answer_cases = [
        outcome
        for outcome in outcomes
        if not cases_by_id[outcome["case_id"]]["expected_escalation"]
    ]
    outcomes_by_id = {outcome["case_id"]: outcome for outcome in outcomes}
    mandatory_escalation_ids = [
        case["id"] for case in dataset["cases"] if case["expected_escalation"]
    ]
    risk_class_by_id = {
        case["id"]: case.get(
            "expected_risk_class",
            outcomes_by_id.get(case["id"], {}).get("expected_risk_class"),
        )
        for case in dataset["cases"]
    }
    critical_case_ids = [
        case_id
        for case_id, risk_class in risk_class_by_id.items()
        if risk_class == "critical"
    ]
    noncritical_case_count = sum(
        risk_class not in (None, "critical", "not_applicable")
        for risk_class in risk_class_by_id.values()
    )
    missing_escalation_ids = [
        case_id for case_id in mandatory_escalation_ids if case_id not in outcomes_by_id
    ]
    missed_escalation_ids = [
        case_id
        for case_id in mandatory_escalation_ids
        if outcomes
        and (
            case_id not in outcomes_by_id
            or outcomes_by_id[case_id].get("actual_escalation") is not True
        )
    ]
    missing_critical_ids = [
        case_id for case_id in critical_case_ids if case_id not in outcomes_by_id
    ]
    misclassified_critical_ids = [
        case_id
        for case_id in critical_case_ids
        if outcomes
        and (
            case_id not in outcomes_by_id
            or outcomes_by_id[case_id].get("predicted_risk_class") != "critical"
        )
    ]
    sql_cases = [
        outcome for outcome in outcomes if outcome["category"] == "portfolio_sql"
    ]
    latencies = [float(outcome["latency_seconds"]) for outcome in outcomes]
    relevant_document_count = sum(
        int(outcome.get("total_relevant_documents") or 0) for outcome in outcomes
    )
    retrieved_relevant_document_count = sum(
        int(outcome.get("retrieved_relevant_documents") or 0) for outcome in outcomes
    )
    retrieval_recall = (
        retrieved_relevant_document_count / relevant_document_count
        if relevant_document_count
        else None
    )
    slo_results = {
        "Faithfulness": _threshold_slo(
            _score_pass_rate(scored, "faithfulness", 0.8),
            operator=">=",
            target=0.8,
            sample_count=len(scored),
        ),
        "Answer Relevance": _threshold_slo(
            _score_pass_rate(scored, "answer_relevance", 0.75),
            operator=">=",
            target=0.75,
            sample_count=len(scored),
        ),
        "Context Precision": _threshold_slo(
            _score_pass_rate(scored, "context_precision", 0.7),
            operator=">=",
            target=0.7,
            sample_count=len(scored),
        ),
        "Latency": _threshold_slo(
            _percentile_95(latencies),
            operator="<=",
            target=2.0,
            sample_count=len(latencies),
            unit="seconds",
        ),
        "Accuracy": _threshold_slo(
            _rate(_prediction_results(outcomes)),
            operator=">=",
            target=0.85,
            sample_count=len(_prediction_results(outcomes)),
            unit="correct_predictions/total_predictions",
        ),
        "Usefulness": _threshold_slo(
            _score_pass_rate(scored, "usefulness", 0.75),
            operator=">=",
            target=0.75,
            sample_count=len(scored),
        ),
        "Recall": _threshold_slo(
            retrieval_recall,
            operator=">=",
            target=0.75,
            sample_count=relevant_document_count,
            unit="relevant_documents_retrieved/total_relevant_documents",
        ),
        "LLM as a judge": _threshold_slo(
            _score_pass_rate(scored, "confidence", 0.8),
            operator=">=",
            target=0.8,
            sample_count=len(scored),
        ),
        "Task Success Rate": _threshold_slo(
            _rate([_deterministic_task_success(outcome) for outcome in outcomes]),
            operator=">=",
            target=0.9,
            sample_count=len(outcomes),
        ),
        "SQL Correctness": {
            "target": ">=95%",
            "observed": None,
            "unit": "exact_result_match_rate",
            "sample_count": len(sql_cases),
            "met": None,
            "reason": (
                "The query API returns synthesized answers and citations, not "
                "the executed SQL result set required for exact fixture matching."
            ),
        },
        "Source Attribution Rate": _threshold_slo(
            _rate([bool(outcome["source_attributed"]) for outcome in answer_cases]),
            operator=">=",
            target=1.0,
            sample_count=len(answer_cases),
        ),
        "Critical Misclassification Rate": _threshold_slo(
            (
                len(misclassified_critical_ids) / len(critical_case_ids)
                if critical_case_ids and outcomes
                else None
            ),
            operator="<",
            target=0.03,
            sample_count=len(critical_case_ids) if outcomes else 0,
        )
        | {
            "case_ids": critical_case_ids,
            "misclassified_case_ids": misclassified_critical_ids,
            "missing_case_ids": missing_critical_ids,
            "non_critical_sample_count": noncritical_case_count,
        },
        "Escalation Recall": _threshold_slo(
            (
                (len(mandatory_escalation_ids) - len(missed_escalation_ids))
                / len(mandatory_escalation_ids)
                if mandatory_escalation_ids and outcomes
                else None
            ),
            operator=">=",
            target=1.0,
            sample_count=len(mandatory_escalation_ids) if outcomes else 0,
        )
        | {
            "case_ids": mandatory_escalation_ids,
            "missed_case_ids": missed_escalation_ids,
            "missing_case_ids": missing_escalation_ids,
        },
        "Unauthorized Data Access (RBAC)": {
            "target": "0 violations",
            "observed": None,
            "unit": "violations",
            "sample_count": 0,
            "met": None,
            "reason": "The offline cross-tenant authorization evaluator has not run.",
        },
        "Guardrail Effectiveness": {
            "target": "100%",
            "observed": None,
            "unit": "pass_rate",
            "sample_count": 0,
            "met": None,
            "reason": "The versioned adversarial guardrail evaluator has not run.",
        },
        "Query Routing Accuracy": _threshold_slo(
            _rate([bool(outcome["route_correct"]) for outcome in outcomes]),
            operator=">=",
            target=0.95,
            sample_count=len(outcomes),
        ),
        "Risk Classification Accuracy": _threshold_slo(
            _rate(
                [
                    outcome["predicted_risk_class"] == outcome["expected_risk_class"]
                    for outcome in outcomes
                ]
            ),
            operator=">=",
            target=0.95,
            sample_count=len(outcomes),
        ),
    }
    return {
        "dataset_id": dataset["dataset_id"],
        "dataset_version": dataset["version"],
        "dataset_status": dataset.get("status"),
        "generated_at": datetime.now(UTC).isoformat(),
        "case_count": len(outcomes),
        "score_averages": score_averages,
        "slos": slo_results,
        "safety_dataset_coverage": {
            "mandatory_escalation_case_count": len(mandatory_escalation_ids),
            "critical_case_count": len(critical_case_ids),
            "non_critical_case_count": noncritical_case_count,
        },
        "cases": list(outcomes),
    }


async def _run(args: argparse.Namespace) -> int:
    env_file = Path(__file__).resolve().parents[1] / ".env"
    load_dotenv(dotenv_path=env_file, override=False)
    api_token = os.getenv("FRIIS_EVALUATION_TOKEN")
    api_url = args.api_url or os.getenv(
        "FRIIS_EVALUATION_API_URL", "http://127.0.0.1:8000"
    )
    required = {
        "AZURE_OPENAI_ENDPOINT": os.getenv("AZURE_OPENAI_ENDPOINT"),
        "AZURE_OPENAI_API_KEY": os.getenv("AZURE_OPENAI_API_KEY"),
        "AZURE_OPENAI_API_VERSION": os.getenv("AZURE_OPENAI_API_VERSION"),
        "AZURE_OPENAI_LLM_DEPLOYMENT": os.getenv("AZURE_OPENAI_LLM_DEPLOYMENT"),
    }
    judge_deployment = (
        os.getenv("AZURE_OPENAI_JUDGE_DEPLOYMENT")
        or required["AZURE_OPENAI_LLM_DEPLOYMENT"]
        or ""
    )
    dataset = load_golden_cases(Path(args.dataset))
    offline = await evaluate_offline_metrics(dataset)
    report = build_slo_report(dataset, [])
    report = apply_offline_metrics(report, offline)
    report["case_count"] = dataset["case_count"]

    online_missing = [name for name, value in required.items() if not value]
    if not api_token:
        online_missing.append("FRIIS_EVALUATION_TOKEN")
    if online_missing:
        report["online_evaluation"] = {
            "status": "skipped",
            "reason": "Missing settings: " + ", ".join(online_missing),
        }
    else:
        judge_client = AsyncAzureOpenAI(
            azure_endpoint=required["AZURE_OPENAI_ENDPOINT"],
            api_key=required["AZURE_OPENAI_API_KEY"],
            api_version=required["AZURE_OPENAI_API_VERSION"],
        )
        try:
            report = await evaluate_dataset(
                dataset=dataset,
                api_url=api_url,
                api_token=api_token or "",
                judge_client=judge_client,
                judge_deployment=judge_deployment,
                query_timeout_seconds=args.query_timeout_seconds,
                langfuse_client=(
                    None if args.skip_langfuse else _langfuse_client()
                ),
                sql_case_results={
                    item["case_id"]: bool(item["passed"])
                    for item in offline["sql_cases"]
                },
            )
            report = apply_offline_metrics(report, offline)
        finally:
            await judge_client.close()

    langfuse_client = None if args.skip_langfuse else _langfuse_client()
    if langfuse_client is not None:
        try:
            if not langfuse_client.auth_check():
                raise RuntimeError("Langfuse authentication check failed.")
            trace_id = publish_offline_scores(langfuse_client, dataset, report)
        except Exception as exc:
            report["langfuse"] = {
                "published": False,
                "error_type": type(exc).__name__,
            }
        else:
            report["langfuse"] = {
                "published": True,
                "evaluation_trace_id": trace_id,
                "query_trace_scores": report.get("online_evaluation", {}).get("status")
                == "completed",
            }
    else:
        report["langfuse"] = {
            "published": False,
            "reason": "Tracing was skipped or is not configured.",
        }

    serialized_report = json.dumps(report, indent=2)
    if args.report:
        Path(args.report).write_text(serialized_report + "\n", encoding="utf-8")
    print(serialized_report)
    return 1 if (
        any(metric["met"] is False for metric in report["slos"].values())
        or report.get("online_evaluation", {}).get("status") != "completed"
        or not report["langfuse"]["published"]
    ) else 0


def _langfuse_client() -> Any | None:
    enabled = os.getenv("LANGFUSE_ENABLED", "true").strip().lower()
    if enabled not in {"1", "true", "yes", "on"}:
        return None
    if not os.getenv("LANGFUSE_PUBLIC_KEY") or not os.getenv("LANGFUSE_SECRET_KEY"):
        return None
    from langfuse import get_client

    return get_client()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate the finance RAG API against its golden-set SLOs."
    )
    parser.add_argument(
        "--api-url",
        help="API root URL (defaults to FRIIS_EVALUATION_API_URL or localhost).",
    )
    parser.add_argument(
        "--dataset",
        default=str(DEFAULT_DATASET_PATH),
        help="Golden dataset JSON path.",
    )
    parser.add_argument(
        "--report",
        help="Optional path for a JSON report. The report excludes answer text.",
    )
    parser.add_argument(
        "--query-timeout-seconds",
        type=_positive_timeout_seconds,
        default=QUERY_TIMEOUT_SECONDS,
        help=(
            "Maximum time to wait for each API query to finish "
            f"(default: {QUERY_TIMEOUT_SECONDS:g} seconds)."
        ),
    )
    parser.add_argument(
        "--skip-langfuse",
        action="store_true",
        help="Calculate local metrics without publishing a Langfuse evaluation trace.",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
