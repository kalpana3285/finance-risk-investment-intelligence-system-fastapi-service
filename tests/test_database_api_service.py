from datetime import UTC, date, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, insert, update
from sqlalchemy.pool import StaticPool

from schemas import (
    Citation,
    EscalationListQuery,
    EscalationStatus,
    EscalationUpdateRequest,
    IngestionRequest,
    IngestionSourceType,
    IngestionStatus,
    PortfolioListQuery,
    QueryRequest,
    QueryStatus,
    ReviewOutcome,
)
from security.auth import Principal, Role
from services.api_service import (
    EscalationConflictError,
    InvalidIngestionRequest,
    InvalidQueryError,
)
from services.database import (
    asset_risk_logs,
    document_versions,
    escalations,
    ingestion_run_items,
    metadata,
    portfolio_holdings,
    portfolios,
    query_requests,
    source_documents,
)
from services.database_api_service import DatabaseAPIService

NOW = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)
ANALYST = Principal(
    subject="auth0|analyst",
    roles=frozenset({Role.ANALYST}),
    portfolio_ids=frozenset({1}),
)
REVIEWER = Principal(
    subject="auth0|reviewer",
    roles=frozenset({Role.COMPLIANCE_REVIEWER}),
    portfolio_ids=frozenset({1}),
)
OPERATOR = Principal(
    subject="auth0|operator",
    roles=frozenset({Role.OPERATOR}),
)


@pytest.fixture
def service() -> DatabaseAPIService:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            insert(portfolios),
            [
                {
                    "portfolio_id": 1,
                    "portfolio_name": "Allowed Portfolio",
                    "risk_category": "High",
                },
                {
                    "portfolio_id": 2,
                    "portfolio_name": "Restricted Portfolio",
                    "risk_category": "Low",
                },
            ],
        )
        connection.execute(
            insert(portfolio_holdings).values(
                holding_id=1,
                portfolio_id=1,
                asset_name="Example Asset",
                allocation_percentage=8.5,
                market_value=1000,
                last_updated=date(2025, 2, 1),
            )
        )
        connection.execute(
            insert(asset_risk_logs).values(
                risk_id=1,
                asset_name="Example Asset",
                risk_type="Market Risk",
                risk_score=45,
                risk_level="Moderate",
                assessment_date=date(2025, 1, 10),
                escalation_flag=False,
            )
        )
        connection.execute(
            insert(source_documents).values(
                document_id="doc-1",
                source_key="risk-policy",
                title="Approved Risk Policy",
                source_type="policy",
                source_uri="file:///approved/risk-policy.pdf",
                approved=True,
                enabled=True,
                created_at=NOW,
                updated_at=NOW,
            )
        )
    return DatabaseAPIService(
        engine,
        query_worker_ready=False,
        ingestion_worker_ready=False,
    )


@pytest.mark.asyncio
async def test_database_service_persists_queries_and_enforces_owner_scope(service) -> None:
    submitted = await service.submit_query(
        ANALYST,
        QueryRequest(question="Summarize risk", portfolio_id=1),
    )
    assert submitted.status == QueryStatus.QUEUED

    retrieved = await service.get_query(ANALYST, submitted.query_id)
    assert retrieved is not None
    assert retrieved.status == QueryStatus.QUEUED
    assert retrieved.answer is None

    other_user = Principal(
        subject="auth0|other",
        roles=frozenset({Role.ANALYST}),
        portfolio_ids=frozenset({1}),
    )
    assert await service.get_query(other_user, submitted.query_id) is None
    revoked_scope = Principal(
        subject=ANALYST.subject,
        roles=ANALYST.roles,
    )
    assert await service.get_query(revoked_scope, submitted.query_id) is None


@pytest.mark.asyncio
async def test_database_service_rejects_queries_that_fail_input_guardrails(service) -> None:
    request = QueryRequest.model_construct(question=" \t ", portfolio_id=None)

    with pytest.raises(InvalidQueryError, match="cannot be empty"):
        await service.submit_query(ANALYST, request)


@pytest.mark.asyncio
async def test_portfolio_queries_enforce_token_scope_and_return_joined_records(service) -> None:
    listing = await service.list_portfolios(ANALYST, PortfolioListQuery())
    assert [item.portfolio_id for item in listing.items] == [1]

    detail = await service.get_portfolio(ANALYST, 1)
    assert detail is not None
    assert detail.holdings[0].asset_name == "Example Asset"
    assert detail.risk_assessments[0].risk_score == 45

    with pytest.raises(HTTPException, match="not authorized") as error:
        await service.get_portfolio(ANALYST, 2)
    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_escalation_workflow_applies_scope_and_transition_rules(service) -> None:
    query = await service.submit_query(
        ANALYST,
        QueryRequest(question="Assess exposure", portfolio_id=1),
    )
    with service.engine.begin() as connection:
        connection.execute(
            insert(escalations).values(
                escalation_id="esc-1",
                query_id=query.query_id,
                portfolio_id=1,
                status=EscalationStatus.OPEN.value,
                reason="Insufficient evidence",
                question="Assess exposure?",
                evidence=[],
                attempted_steps=["retrieved policy"],
                data_gaps=["missing benchmark history"],
                requested_review="Review risk evidence",
                created_at=NOW,
                updated_at=NOW,
            )
        )

    listing = await service.list_escalations(REVIEWER, EscalationListQuery())
    assert [item.escalation_id for item in listing.items] == ["esc-1"]
    updated = await service.update_escalation(
        REVIEWER,
        "esc-1",
        EscalationUpdateRequest(
            status=EscalationStatus.RESOLVED,
            outcome=ReviewOutcome.GUIDANCE_PROVIDED,
            reviewer_notes="Reviewed.",
        ),
    )
    assert updated is not None
    assert updated.status == EscalationStatus.RESOLVED
    assert updated.answer is None
    assert updated.citations == []

    with pytest.raises(EscalationConflictError):
        await service.update_escalation(
            REVIEWER,
            "esc-1",
            EscalationUpdateRequest(status=EscalationStatus.CLOSED),
        )


@pytest.mark.asyncio
async def test_escalation_detail_transfers_query_context_to_reviewers(service) -> None:
    query = await service.submit_query(
        ANALYST,
        QueryRequest(question="Assess exposure", portfolio_id=1, session_id="session-1"),
    )
    citation = Citation(
        source_id="policy-1",
        source_title="Approved risk policy",
        evidence_type="policy_document",
        excerpt="Exposure limits are reviewed quarterly.",
        page_number=3,
    )
    with service.engine.begin() as connection:
        connection.execute(
            update(query_requests)
            .where(query_requests.c.query_id == query.query_id)
            .values(
                status=QueryStatus.ESCALATED.value,
                answer="The available evidence is incomplete.",
                citations=[citation.model_dump(mode="json")],
                limitations=["Historical market data is unavailable."],
            )
        )
        connection.execute(
            insert(escalations).values(
                escalation_id="esc-context",
                query_id=query.query_id,
                portfolio_id=1,
                status=EscalationStatus.OPEN.value,
                reason="Insufficient evidence",
                question="Assess exposure",
                evidence=[],
                attempted_steps=["Retrieved approved risk policy."],
                data_gaps=["Historical market data is unavailable."],
                requested_review="Review the available evidence.",
                created_at=NOW,
                updated_at=NOW,
            )
        )

    detail = await service.get_escalation(REVIEWER, "esc-context")

    assert detail is not None
    assert detail.session_id == "session-1"
    assert detail.answer == "The available evidence is incomplete."
    assert detail.citations == [citation]
    assert detail.limitations == ["Historical market data is unavailable."]


@pytest.mark.asyncio
async def test_unscoped_escalations_are_visible_to_their_query_owner(service) -> None:
    reviewer_without_portfolio_scope = Principal(
        subject="auth0|reviewer",
        roles=frozenset({Role.COMPLIANCE_REVIEWER}),
    )
    query = await service.submit_query(
        reviewer_without_portfolio_scope,
        QueryRequest(question="What does the policy say?"),
    )
    with service.engine.begin() as connection:
        connection.execute(
            insert(escalations).values(
                escalation_id="esc-unscoped",
                query_id=query.query_id,
                portfolio_id=None,
                status=EscalationStatus.OPEN.value,
                reason="Ambiguous policy",
                question="What does the policy say?",
                evidence=[],
                attempted_steps=[],
                data_gaps=[],
                requested_review="Review policy interpretation",
                created_at=NOW,
                updated_at=NOW,
            )
        )
    result = await service.list_escalations(
        reviewer_without_portfolio_scope,
        EscalationListQuery(),
    )
    assert [item.escalation_id for item in result.items] == ["esc-unscoped"]


@pytest.mark.asyncio
async def test_ingestion_queue_requires_approved_source_and_is_owner_scoped(service) -> None:
    run = await service.start_ingestion(
        OPERATOR,
        IngestionRequest(
            source_type=IngestionSourceType.DOCUMENTS,
            source_ids=["risk-policy"],
        ),
    )
    assert run.status == IngestionStatus.QUEUED
    detail = await service.get_ingestion(OPERATOR, run.ingestion_id)
    assert detail is not None
    assert detail.processed_sources[0].source_id == "risk-policy"
    with service.engine.begin() as connection:
        connection.execute(
            insert(document_versions).values(
                document_version_id="version-1",
                document_id="doc-1",
                version_label="v1",
                content_sha256="a" * 64,
                content_type="application/pdf",
                storage_uri="Documents/risk-policy.pdf",
                validation_status="valid",
                created_at=NOW,
            )
        )
        connection.execute(
            insert(ingestion_run_items).values(
                ingestion_id=run.ingestion_id,
                document_version_id="version-1",
                status="succeeded",
                records_processed=1,
                chunks_created=3,
                chunks_indexed=3,
                started_at=NOW,
                completed_at=NOW,
            )
        )
    completed = await service.get_ingestion(OPERATOR, run.ingestion_id)
    assert completed is not None
    assert completed.processed_sources[0].source_id == "risk-policy"
    assert completed.processed_sources[0].status == IngestionStatus.SUCCEEDED
    assert await service.get_ingestion(ANALYST, run.ingestion_id) is None

    with pytest.raises(InvalidIngestionRequest):
        await service.start_ingestion(
            OPERATOR,
            IngestionRequest(
                source_type=IngestionSourceType.DOCUMENTS,
                source_ids=["unapproved"],
            ),
        )
    with pytest.raises(InvalidIngestionRequest):
        await service.start_ingestion(
            OPERATOR,
            IngestionRequest(
                source_type=IngestionSourceType.STRUCTURED_DATA,
                source_ids=["arbitrary_table"],
            ),
        )
    with pytest.raises(InvalidIngestionRequest, match="not available"):
        await service.start_ingestion(
            OPERATOR,
            IngestionRequest(
                source_type=IngestionSourceType.STRUCTURED_DATA,
                source_ids=["portfolio_holdings"],
            ),
        )


@pytest.mark.asyncio
async def test_health_marks_database_up_but_workers_degraded_until_configured(service) -> None:
    health = await service.health()
    assert health["database"].value == "ok"
    assert health["query_worker"].value == "degraded"
    assert health["ingestion_worker"].value == "degraded"
