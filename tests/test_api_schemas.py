from datetime import UTC, date, datetime
from decimal import Decimal
from inspect import isclass

import pytest
from pydantic import BaseModel, ValidationError

import schemas
from schemas import (
    AssetRiskAssessment,
    Citation,
    ErrorResponse,
    EscalationDetailResponse,
    EscalationListQuery,
    EscalationListResponse,
    EscalationStatus,
    EscalationUpdateRequest,
    HealthResponse,
    HealthStatus,
    IngestionDetailResponse,
    IngestionRequest,
    IngestionSourceType,
    IngestionStatus,
    IngestionSubmissionResponse,
    PortfolioDetailResponse,
    PortfolioHolding,
    PortfolioListQuery,
    PortfolioListResponse,
    PortfolioSummary,
    QueryFailure,
    QueryRequest,
    QueryResponse,
    QueryStatus,
    QuerySubmissionResponse,
    ReviewOutcome,
)

NOW = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)


def test_query_contracts_validate_submission_and_terminal_responses() -> None:
    request = QueryRequest.model_validate(
        {"question": "  What is the portfolio risk? ", "portfolio_id": 1}
    )
    assert request.question == "What is the portfolio risk?"

    submission = QuerySubmissionResponse(
        query_id="q-123", status=QueryStatus.QUEUED, submitted_at=NOW
    )
    assert submission.status == QueryStatus.QUEUED

    citation = Citation(
        source_id="policy-1",
        source_title="Risk policy",
        evidence_type="document",
        page_number=2,
    )
    result = QueryResponse(
        query_id="q-123",
        status=QueryStatus.COMPLETED,
        answer="The result is supported by the cited policy.",
        citations=[citation],
    )
    assert result.citations[0].page_number == 2
    assert QueryResponse(
        query_id="q-124",
        status=QueryStatus.ESCALATED,
        escalation_id="e-123",
    ).escalation_id == "e-123"

    with pytest.raises(ValidationError, match="completed queries must include an answer"):
        QueryResponse(query_id="q-123", status=QueryStatus.COMPLETED)
    with pytest.raises(ValidationError, match="must include failure details"):
        QueryResponse(query_id="q-123", status=QueryStatus.FAILED)
    with pytest.raises(ValidationError):
        QueryRequest(question="   ")


def test_portfolio_contracts_match_finance_dataset_fields() -> None:
    filters = PortfolioListQuery(limit=10, risk_category="High")
    assert filters.limit == 10
    assert PortfolioListQuery().limit == 50

    portfolio = PortfolioSummary(
        portfolio_id=1,
        portfolio_name="Global Growth Fund",
        portfolio_manager="Analyst",
        risk_category="High",
        total_value=Decimal(250000000),
        benchmark_index="MSCI World",
    )
    holding = PortfolioHolding(
        holding_id=1,
        asset_name="Example asset",
        allocation_percentage=Decimal("8.5"),
        market_value=Decimal(21250000),
        last_updated=date(2025, 2, 1),
    )
    risk = AssetRiskAssessment(
        risk_id=1,
        risk_score=45,
        risk_level="Moderate",
        assessment_date=date(2025, 1, 10),
        escalation_flag=False,
    )
    detail = PortfolioDetailResponse(
        **portfolio.model_dump(),
        holdings=[holding],
        risk_assessments=[risk],
    )
    assert detail.total_value == Decimal(250000000)
    assert detail.holdings[0].allocation_percentage == Decimal("8.5")
    assert PortfolioListResponse(items=[portfolio]).next_cursor is None

    with pytest.raises(ValidationError):
        PortfolioListQuery(limit=101)
    with pytest.raises(ValidationError):
        PortfolioHolding(holding_id=1, allocation_percentage=Decimal(101))
    with pytest.raises(ValidationError):
        AssetRiskAssessment(risk_id=1, risk_score=101)


def test_escalation_contracts_represent_handoff_and_reviewer_updates() -> None:
    list_query = EscalationListQuery(status="open", limit=20)
    assert list_query.status == EscalationStatus.OPEN

    update = EscalationUpdateRequest(
        status=EscalationStatus.RESOLVED,
        outcome=ReviewOutcome.GUIDANCE_PROVIDED,
        reviewer_notes="Shared policy guidance.",
    )
    assert update.outcome == ReviewOutcome.GUIDANCE_PROVIDED

    detail = EscalationDetailResponse(
        escalation_id="e-123",
        query_id="q-123",
        status=EscalationStatus.OPEN,
        reason="Insufficient evidence",
        question="Can the system assess this exposure?",
        requested_review="Review the available risk evidence.",
        created_at=NOW,
        updated_at=NOW,
    )
    assert detail.evidence == []
    assert EscalationListResponse(items=[detail]).items[0].escalation_id == "e-123"

    with pytest.raises(ValidationError):
        EscalationUpdateRequest()
    with pytest.raises(ValidationError):
        EscalationUpdateRequest.model_validate(
            {"status": "resolved", "approve_trade": True}
        )


def test_ingestion_contracts_accept_only_registered_source_identifiers() -> None:
    request = IngestionRequest(
        source_type=IngestionSourceType.DOCUMENTS,
        source_ids=["policy-risk-v1"],
    )
    assert request.source_ids == ["policy-risk-v1"]

    submission = IngestionSubmissionResponse(
        ingestion_id="ing-123", status=IngestionStatus.QUEUED, submitted_at=NOW
    )
    detail = IngestionDetailResponse(
        ingestion_id=submission.ingestion_id,
        source_type=request.source_type,
        status=IngestionStatus.SUCCEEDED,
        submitted_at=NOW,
        completed_at=NOW,
    )
    assert detail.validation_errors == []

    with pytest.raises(ValidationError):
        IngestionRequest(
            source_type=IngestionSourceType.DOCUMENTS,
            source_ids=[],
        )
    with pytest.raises(ValidationError):
        IngestionRequest(
            source_type=IngestionSourceType.DOCUMENTS,
            source_ids=["policy-1", "unexpected_field"],
            extra="not allowed",
        )


def test_health_and_error_responses_are_typed() -> None:
    health = HealthResponse(
        status=HealthStatus.DEGRADED,
        checked_at=NOW,
        checks={"database": HealthStatus.OK},
    )
    assert health.checks["database"] == HealthStatus.OK

    error = ErrorResponse(
        code="not_found",
        message="The requested query was not found.",
        request_id="request-1",
    )
    assert error.request_id == "request-1"
    assert QueryFailure(code="timeout", message="The request timed out.").retryable is False


def test_exported_pydantic_models_generate_json_schemas() -> None:
    exported_models = [
        value
        for value in vars(schemas).values()
        if isclass(value) and issubclass(value, BaseModel) and value is not BaseModel
    ]
    assert exported_models
    for model in exported_models:
        assert model.model_json_schema()["title"] == model.__name__
