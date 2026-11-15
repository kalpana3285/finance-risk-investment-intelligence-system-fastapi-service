"""Database-backed implementation of the FRIIS HTTP service boundary."""

import asyncio
import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import and_, insert, inspect, or_, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from schemas import (
    AssetRiskAssessment,
    Citation,
    EscalationDetailResponse,
    EscalationListQuery,
    EscalationListResponse,
    EscalationStatus,
    EscalationSummary,
    EscalationUpdateRequest,
    EscalationUpdateResponse,
    HandoffEvidence,
    HealthStatus,
    IngestionDetailResponse,
    IngestionRequest,
    IngestionSourceResult,
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
from security.auth import Principal
from services.api_service import (
    APIService,
    EscalationConflictError,
    InvalidCursorError,
    InvalidIngestionRequest,
    InvalidQueryError,
)
from services.database import (
    asset_risk_logs,
    document_chunks,
    document_versions,
    conversation_sessions,
    escalations,
    ingestion_run_items,
    ingestion_runs,
    investment_decisions,
    market_indicators,
    portfolio_holdings,
    portfolios,
    query_requests,
    query_workflow_events,
    source_documents,
)
from services.guardrails import GuardrailsValidator

logger = logging.getLogger(__name__)

STRUCTURED_INGESTION_SOURCES = frozenset(
    {
        "portfolios",
        "portfolio_holdings",
        "asset_risk_logs",
        "market_indicators",
        "investment_decisions",
    }
)


class DatabaseAPIService(APIService):
    """Persist API workflows and serve authorized read-only finance queries.

    Query and ingestion requests are durable queued records. A separate worker
    must consume those records and update their status/result fields.
    """

    def __init__(
        self,
        engine: Engine,
        *,
        query_worker_ready: bool = False,
        ingestion_worker_ready: bool = False,
    ) -> None:
        self.engine = engine
        self.query_worker_ready = query_worker_ready
        self.ingestion_worker_ready = ingestion_worker_ready
        self.query_log_guardrails = GuardrailsValidator()

    async def submit_query(
        self, principal: Principal, request: QueryRequest
    ) -> QuerySubmissionResponse:
        decision = GuardrailsValidator.validate_input(request.question)
        if not decision.allowed:
            raise InvalidQueryError(decision.reason or "Query input is invalid.")
        if request.portfolio_id is not None:
            _require_portfolio_scope(principal, request.portfolio_id)
        now = _utcnow()
        query_id = str(uuid4())

        def persist() -> None:
            with self.engine.begin() as connection:
                prior_questions: list[str] = []
                connection.execute(
                    conversation_sessions.delete().where(
                        conversation_sessions.c.updated_at < now - timedelta(minutes=30)
                    )
                )
                if request.session_id:
                    memory = connection.execute(
                        select(conversation_sessions).where(
                            conversation_sessions.c.owner_subject == principal.subject,
                            conversation_sessions.c.session_id == request.session_id,
                        )
                    ).mappings().first()
                    updated_at = memory["updated_at"] if memory is not None else None
                    if updated_at is not None and updated_at.tzinfo is None:
                        updated_at = updated_at.replace(tzinfo=UTC)
                    if updated_at is not None and (now - updated_at).total_seconds() <= 1800:
                        prior_questions = list(memory["user_questions"] or [])[-6:]
                connection.execute(
                    insert(query_requests).values(
                        query_id=query_id,
                        owner_subject=principal.subject,
                        question=request.question,
                        portfolio_id=request.portfolio_id,
                        session_id=request.session_id,
                        conversation_context=prior_questions,
                        authorized_portfolio_ids=sorted(principal.portfolio_ids),
                        all_portfolios_access=principal.all_portfolios_access,
                        principal_roles=sorted(role.value for role in principal.roles),
                        status=QueryStatus.QUEUED.value,
                        citations=[],
                        limitations=[],
                        created_at=now,
                        updated_at=now,
                    )
                )
                if request.session_id:
                    values = dict(
                            owner_subject=principal.subject,
                            session_id=request.session_id,
                            user_questions=(prior_questions + [request.question])[-6:],
                            updated_at=now,
                        )
                    if memory is None:
                        connection.execute(insert(conversation_sessions).values(**values))
                    else:
                        connection.execute(
                            update(conversation_sessions)
                            .where(
                                and_(
                                    conversation_sessions.c.owner_subject == principal.subject,
                                    conversation_sessions.c.session_id == request.session_id,
                                )
                            )
                            .values(**values)
                        )

        await asyncio.to_thread(persist)
        try:
            safe_question = self.query_log_guardrails.validate_output(
                request.question
            ).sanitized_text
            safe_question = re.sub(
                r"<[A-Z][A-Z0-9_]*>", "[REDACTED]", safe_question
            )
        except Exception:
            logger.exception(
                "Could not sanitize submitted query for application logging",
                extra={"query_id": query_id},
            )
            safe_question = "[omitted because query sanitization failed]"
        logger.info(
            "Research query submitted",
            extra={
                "event": "query.submitted",
                "query_id": query_id,
                "user_query": safe_question,
                "portfolio_id": request.portfolio_id,
            },
        )
        return QuerySubmissionResponse(
            query_id=query_id,
            status=QueryStatus.QUEUED,
            submitted_at=now,
        )

    async def reset_conversation_memory(self, principal: Principal, session_id: str) -> None:
        def clear() -> None:
            with self.engine.begin() as connection:
                connection.execute(
                    conversation_sessions.delete().where(
                        and_(
                            conversation_sessions.c.owner_subject == principal.subject,
                            conversation_sessions.c.session_id == session_id,
                        )
                    )
                )

        await asyncio.to_thread(clear)

    async def get_query(
        self, principal: Principal, query_id: str
    ) -> QueryResponse | None:
        def fetch() -> dict[str, Any] | None:
            with self.engine.connect() as connection:
                conditions = [
                    query_requests.c.query_id == query_id,
                    query_requests.c.owner_subject == principal.subject,
                ]
                if not principal.all_portfolios_access:
                    if principal.portfolio_ids:
                        conditions.append(
                            or_(
                                query_requests.c.portfolio_id.is_(None),
                                query_requests.c.portfolio_id.in_(
                                    principal.portfolio_ids
                                ),
                            )
                        )
                    else:
                        conditions.append(query_requests.c.portfolio_id.is_(None))
                row = connection.execute(
                    select(
                        query_requests,
                        escalations.c.reason.label("escalation_reason"),
                        escalations.c.data_gaps.label("escalation_data_gaps"),
                    )
                    .outerjoin(
                        escalations,
                        query_requests.c.escalation_id == escalations.c.escalation_id,
                    )
                    .where(and_(*conditions))
                ).mappings().first()
                return dict(row) if row is not None else None

        row = await asyncio.to_thread(fetch)
        if row is None:
            return None
        return QueryResponse(
            query_id=row["query_id"],
            status=QueryStatus(row["status"]),
            answer=row["answer"],
            citations=row["citations"] or [],
            limitations=row["limitations"] or [],
            clarification_question=row["clarification_question"],
            escalation_id=row["escalation_id"],
            escalation_reason=row.get("escalation_reason"),
            escalation_data_gaps=row.get("escalation_data_gaps") or [],
            failure=QueryFailure.model_validate(row["failure"])
            if row["failure"]
            else None,
        )

    async def list_portfolios(
        self, principal: Principal, query: PortfolioListQuery
    ) -> PortfolioListResponse:
        offset = _parse_offset(query.cursor)
        conditions = _portfolio_scope_filter(principal)
        if query.risk_category is not None:
            conditions.append(portfolios.c.risk_category == query.risk_category)
        statement = select(portfolios).order_by(portfolios.c.portfolio_id)
        if conditions:
            statement = statement.where(and_(*conditions))
        statement = statement.offset(offset).limit(query.limit + 1)

        def fetch() -> list[dict[str, Any]]:
            with self.engine.connect() as connection:
                return [dict(row) for row in connection.execute(statement).mappings()]

        rows = await asyncio.to_thread(fetch)
        has_more = len(rows) > query.limit
        items = [_portfolio_summary(row) for row in rows[: query.limit]]
        return PortfolioListResponse(
            items=items,
            next_cursor=str(offset + query.limit) if has_more else None,
        )

    async def get_portfolio(
        self, principal: Principal, portfolio_id: int
    ) -> PortfolioDetailResponse | None:
        _require_portfolio_scope(principal, portfolio_id)

        def fetch() -> tuple[dict[str, Any] | None, list[dict[str, Any]], list[dict[str, Any]]]:
            with self.engine.connect() as connection:
                portfolio_row = connection.execute(
                    select(portfolios).where(
                        portfolios.c.portfolio_id == portfolio_id
                    )
                ).mappings().first()
                if portfolio_row is None:
                    return None, [], []
                holding_rows = [
                    dict(row)
                    for row in connection.execute(
                        select(portfolio_holdings)
                        .where(portfolio_holdings.c.portfolio_id == portfolio_id)
                        .order_by(portfolio_holdings.c.holding_id)
                    ).mappings()
                ]
                asset_names = list(
                    {
                        row["asset_name"]
                        for row in holding_rows
                        if row["asset_name"] is not None
                    }
                )
                risk_rows: list[dict[str, Any]] = []
                if asset_names:
                    risk_rows = [
                        dict(row)
                        for row in connection.execute(
                            select(asset_risk_logs)
                            .where(asset_risk_logs.c.asset_name.in_(asset_names))
                            .order_by(
                                asset_risk_logs.c.assessment_date.desc(),
                                asset_risk_logs.c.risk_id.desc(),
                            )
                        ).mappings()
                    ]
                return dict(portfolio_row), holding_rows, risk_rows

        portfolio_row, holding_rows, risk_rows = await asyncio.to_thread(fetch)
        if portfolio_row is None:
            return None
        return PortfolioDetailResponse(
            **_portfolio_summary(portfolio_row).model_dump(),
            holdings=[
                PortfolioHolding.model_validate(
                    {
                        key: row.get(key)
                        for key in PortfolioHolding.model_fields
                    }
                )
                for row in holding_rows
            ],
            risk_assessments=[
                AssetRiskAssessment.model_validate(
                    {
                        key: row.get(key)
                        for key in AssetRiskAssessment.model_fields
                    }
                )
                for row in risk_rows
            ],
        )

    async def list_escalations(
        self, principal: Principal, query: EscalationListQuery
    ) -> EscalationListResponse:
        offset = _parse_offset(query.cursor)
        conditions = _escalation_scope_filter(principal)
        if query.status is not None:
            conditions.append(escalations.c.status == query.status.value)
        statement = (
            select(escalations)
            .where(and_(*conditions))
            .order_by(escalations.c.created_at, escalations.c.escalation_id)
            .offset(offset)
            .limit(query.limit + 1)
        )

        def fetch() -> list[dict[str, Any]]:
            with self.engine.connect() as connection:
                return [dict(row) for row in connection.execute(statement).mappings()]

        rows = await asyncio.to_thread(fetch)
        has_more = len(rows) > query.limit
        items = [_escalation_summary(row) for row in rows[: query.limit]]
        return EscalationListResponse(
            items=items,
            next_cursor=str(offset + query.limit) if has_more else None,
        )

    async def get_escalation(
        self, principal: Principal, escalation_id: str
    ) -> EscalationDetailResponse | None:
        conditions = [
            escalations.c.escalation_id == escalation_id,
            *_escalation_scope_filter(principal),
        ]

        def fetch() -> dict[str, Any] | None:
            with self.engine.connect() as connection:
                row = connection.execute(
                    select(
                        escalations,
                        query_requests.c.session_id,
                        query_requests.c.answer,
                        query_requests.c.citations,
                        query_requests.c.limitations,
                    )
                    .join(
                        query_requests,
                        query_requests.c.query_id == escalations.c.query_id,
                    )
                    .where(and_(*conditions))
                ).mappings().first()
                return dict(row) if row is not None else None

        row = await asyncio.to_thread(fetch)
        return _escalation_detail(row) if row is not None else None

    async def update_escalation(
        self,
        principal: Principal,
        escalation_id: str,
        update_request: EscalationUpdateRequest,
    ) -> EscalationUpdateResponse | None:
        now = _utcnow()
        conditions = [
            escalations.c.escalation_id == escalation_id,
            *_escalation_scope_filter(principal),
        ]

        def update_record() -> dict[str, Any] | None:
            with self.engine.begin() as connection:
                current = connection.execute(
                    select(escalations).where(and_(*conditions))
                ).mappings().first()
                if current is None:
                    return None
                current_status = EscalationStatus(current["status"])
                next_status = update_request.status or current_status
                if not _valid_escalation_transition(current_status, next_status):
                    raise EscalationConflictError(
                        f"Escalation cannot move from {current_status.value} "
                        f"to {next_status.value}."
                    )
                next_outcome = update_request.outcome or (
                    ReviewOutcome(current["outcome"])
                    if current["outcome"]
                    else None
                )
                if next_status == EscalationStatus.RESOLVED and next_outcome is None:
                    raise EscalationConflictError(
                        "A resolved escalation requires a review outcome."
                    )
                values: dict[str, Any] = {
                    "status": next_status.value,
                    "updated_at": now,
                }
                if update_request.outcome is not None:
                    values["outcome"] = update_request.outcome.value
                if update_request.reviewer_notes is not None:
                    values["reviewer_notes"] = update_request.reviewer_notes
                connection.execute(
                    update(escalations)
                    .where(and_(*conditions))
                    .values(**values)
                )
                updated = connection.execute(
                    select(
                        escalations,
                        query_requests.c.session_id,
                        query_requests.c.answer,
                        query_requests.c.citations,
                        query_requests.c.limitations,
                    )
                    .join(
                        query_requests,
                        query_requests.c.query_id == escalations.c.query_id,
                    )
                    .where(and_(*conditions))
                ).mappings().one()
                return dict(updated)

        row = await asyncio.to_thread(update_record)
        if row is None:
            logger.info(
                "Human-review case update did not match an accessible case",
                extra={
                    "event": "review.case_update_not_found",
                    "escalation_id": escalation_id,
                },
            )
            return None
        logger.info(
            "Human-review case updated",
            extra={
                "event": "review.case_updated",
                "escalation_id": escalation_id,
                "review_status": row["status"],
                "review_outcome": row["outcome"],
            },
        )
        return EscalationUpdateResponse.model_validate(_escalation_detail(row).model_dump())

    async def start_ingestion(
        self, principal: Principal, request: IngestionRequest
    ) -> IngestionSubmissionResponse:
        if request.source_type == IngestionSourceType.STRUCTURED_DATA:
            invalid_sources = set(request.source_ids) - STRUCTURED_INGESTION_SOURCES
            if invalid_sources:
                raise InvalidIngestionRequest(
                    "Unsupported structured-data source(s): "
                    + ", ".join(sorted(invalid_sources))
                )
        else:
            def validate_sources() -> set[str]:
                with self.engine.connect() as connection:
                    rows = connection.execute(
                        select(
                            source_documents.c.source_key,
                            source_documents.c.document_id,
                        ).where(
                            source_documents.c.approved.is_(True),
                            source_documents.c.enabled.is_(True),
                            or_(
                                source_documents.c.source_key.in_(request.source_ids),
                                source_documents.c.document_id.in_(request.source_ids),
                            ),
                        )
                    ).all()
                    return {
                        identifier
                        for row in rows
                        for identifier in (row.source_key, row.document_id)
                    }

            approved = await asyncio.to_thread(validate_sources)
            missing = set(request.source_ids) - approved
            if missing:
                raise InvalidIngestionRequest(
                    "Ingestion sources are not registered, approved, and enabled: "
                    + ", ".join(sorted(missing))
                )

        now = _utcnow()
        ingestion_id = str(uuid4())

        def persist() -> None:
            with self.engine.begin() as connection:
                connection.execute(
                    insert(ingestion_runs).values(
                        ingestion_id=ingestion_id,
                        run_type="incremental",
                        status=IngestionStatus.QUEUED.value,
                        initiated_by=principal.subject,
                        pipeline_version="api-v1",
                        source_type=request.source_type.value,
                        source_ids=request.source_ids,
                        validation_errors=[],
                        created_at=now,
                    )
                )

        await asyncio.to_thread(persist)
        return IngestionSubmissionResponse(
            ingestion_id=ingestion_id,
            status=IngestionStatus.QUEUED,
            submitted_at=now,
        )

    async def get_ingestion(
        self, principal: Principal, ingestion_id: str
    ) -> IngestionDetailResponse | None:
        def fetch() -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
            with self.engine.connect() as connection:
                run = connection.execute(
                    select(ingestion_runs).where(
                        ingestion_runs.c.ingestion_id == ingestion_id,
                        ingestion_runs.c.initiated_by == principal.subject,
                    )
                ).mappings().first()
                if run is None:
                    return None, []
                versions = connection.execute(
                    select(
                        ingestion_run_items,
                        source_documents.c.source_key,
                        source_documents.c.document_id,
                    )
                    .join(
                        document_versions,
                        document_versions.c.document_version_id
                        == ingestion_run_items.c.document_version_id,
                    )
                    .join(
                        source_documents,
                        source_documents.c.document_id
                        == document_versions.c.document_id,
                    )
                    .where(ingestion_run_items.c.ingestion_id == ingestion_id)
                ).mappings()
                return dict(run), [dict(row) for row in versions]

        run, run_items = await asyncio.to_thread(fetch)
        if run is None:
            return None
        items_by_source = {
            identifier: item
            for item in run_items
            for identifier in (item["source_key"], item["document_id"])
        }
        source_results = []
        for source_id in run["source_ids"]:
            item = items_by_source.get(source_id)
            if item is not None:
                source_results.append(
                    IngestionSourceResult(
                        source_id=source_id,
                        status=_ingestion_item_status(item["status"]),
                        error_code=item.get("error_code"),
                        error_message=item.get("error_message"),
                    )
                )
                continue
            completed_without_item = run["status"] in {
                IngestionStatus.SUCCEEDED.value,
                IngestionStatus.PARTIAL.value,
                IngestionStatus.FAILED.value,
            }
            source_results.append(
                IngestionSourceResult(
                    source_id=source_id,
                    status=(
                        IngestionStatus.FAILED
                        if completed_without_item
                        else IngestionStatus(run["status"])
                    ),
                    error_code=(
                        "source_processing_failed" if completed_without_item else None
                    ),
                    error_message=(
                        "No ingestion result was recorded for this source."
                        if completed_without_item
                        else None
                    ),
                )
            )
        return IngestionDetailResponse(
            ingestion_id=run["ingestion_id"],
            source_type=IngestionSourceType(run["source_type"]),
            status=IngestionStatus(run["status"]),
            submitted_at=run["created_at"],
            completed_at=run["completed_at"],
            validation_errors=run["validation_errors"] or [],
            processed_sources=source_results,
            indexing_status=IngestionStatus(run["status"]),
        )

    async def health(self) -> dict[str, HealthStatus]:
        def check_database() -> None:
            with self.engine.connect() as connection:
                connection.exec_driver_sql("SELECT 1")
            required_tables = {
                portfolios.name,
                portfolio_holdings.name,
                asset_risk_logs.name,
                market_indicators.name,
                investment_decisions.name,
                query_requests.name,
                query_workflow_events.name,
                escalations.name,
                ingestion_runs.name,
                source_documents.name,
                document_versions.name,
                ingestion_run_items.name,
                document_chunks.name,
            }
            existing_tables = set(inspect(self.engine).get_table_names())
            missing = required_tables - existing_tables
            if missing:
                raise SQLAlchemyError(
                    "Required database tables are missing: "
                    + ", ".join(sorted(missing))
                )

        try:
            await asyncio.to_thread(check_database)
        except SQLAlchemyError:
            database_status = HealthStatus.UNAVAILABLE
        else:
            database_status = HealthStatus.OK
        return {
            "database": database_status,
            "query_worker": (
                HealthStatus.OK
                if self.query_worker_ready
                else HealthStatus.DEGRADED
            ),
            "ingestion_worker": (
                HealthStatus.OK
                if self.ingestion_worker_ready
                else HealthStatus.DEGRADED
            ),
        }

    async def aclose(self) -> None:
        await asyncio.to_thread(self.engine.dispose)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _portfolio_scope_filter(principal: Principal) -> list[Any]:
    if principal.all_portfolios_access:
        return []
    if not principal.portfolio_ids:
        return [portfolios.c.portfolio_id.in_([])]
    return [portfolios.c.portfolio_id.in_(principal.portfolio_ids)]


def _escalation_scope_filter(principal: Principal) -> list[Any]:
    if principal.all_portfolios_access:
        return []
    owned_unscoped_escalations = and_(
        escalations.c.portfolio_id.is_(None),
        escalations.c.query_id.in_(
            select(query_requests.c.query_id).where(
                query_requests.c.owner_subject == principal.subject
            )
        )
    )
    if not principal.portfolio_ids:
        return [owned_unscoped_escalations]
    return [
        or_(
            escalations.c.portfolio_id.in_(principal.portfolio_ids),
            owned_unscoped_escalations,
        )
    ]


def _require_portfolio_scope(principal: Principal, portfolio_id: int) -> None:
    if (
        not principal.all_portfolios_access
        and portfolio_id not in principal.portfolio_ids
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The caller is not authorized to access this portfolio.",
        )


def _parse_offset(cursor: str | None) -> int:
    if cursor is None:
        return 0
    if not cursor.isdecimal():
        raise InvalidCursorError("cursor must be a non-negative numeric offset")
    return int(cursor)


def _portfolio_summary(row: dict[str, Any]) -> PortfolioSummary:
    return PortfolioSummary.model_validate(
        {key: row.get(key) for key in PortfolioSummary.model_fields}
    )


def _escalation_summary(row: dict[str, Any]) -> EscalationSummary:
    return EscalationSummary(
        escalation_id=row["escalation_id"],
        query_id=row["query_id"],
        status=EscalationStatus(row["status"]),
        reason=row["reason"],
        created_at=row["created_at"],
    )


def _escalation_detail(row: dict[str, Any]) -> EscalationDetailResponse:
    return EscalationDetailResponse(
        **_escalation_summary(row).model_dump(),
        question=row["question"],
        evidence=[
            HandoffEvidence.model_validate(item) for item in (row["evidence"] or [])
        ],
        attempted_steps=row["attempted_steps"] or [],
        data_gaps=row["data_gaps"] or [],
        requested_review=row["requested_review"],
        session_id=row.get("session_id"),
        answer=row.get("answer"),
        citations=[
            Citation.model_validate(item) for item in (row.get("citations") or [])
        ],
        limitations=row.get("limitations") or [],
        updated_at=row["updated_at"],
        reviewer_notes=row["reviewer_notes"],
        outcome=ReviewOutcome(row["outcome"]) if row["outcome"] else None,
    )


def _valid_escalation_transition(
    current: EscalationStatus, target: EscalationStatus
) -> bool:
    if current == target:
        return current not in {EscalationStatus.RESOLVED, EscalationStatus.CLOSED}
    transitions = {
        EscalationStatus.OPEN: {
            EscalationStatus.IN_REVIEW,
            EscalationStatus.RESOLVED,
            EscalationStatus.CLOSED,
        },
        EscalationStatus.IN_REVIEW: {
            EscalationStatus.RESOLVED,
            EscalationStatus.CLOSED,
        },
        EscalationStatus.RESOLVED: set(),
        EscalationStatus.CLOSED: set(),
    }
    return target in transitions[current]


def _ingestion_item_status(value: str) -> IngestionStatus:
    if value in {member.value for member in IngestionStatus}:
        return IngestionStatus(value)
    if value in {"validating", "parsing", "chunking", "embedding", "indexing"}:
        return IngestionStatus.RUNNING
    if value == "failed":
        return IngestionStatus.FAILED
    return IngestionStatus.QUEUED
