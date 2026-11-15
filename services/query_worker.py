"""Durable worker for asynchronous query orchestration."""

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import and_, insert, or_, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from agents.control_plane import (
    ControlPlaneError,
    QueryContext,
    SupervisorAgent,
    WorkflowEventSink,
)
from schemas import EscalationStatus, QueryFailure, QueryStatus
from services.database import (
    escalations,
    query_requests,
    query_workflow_events,
)
from services.guardrails import (
    PII_REDACTION_LIMITATION,
    GuardrailsValidator,
)
from services.langfuse_tracing import observation, trace_attributes

logger = logging.getLogger(__name__)
PROCESSING_STALE_SECONDS = 300


class QueryWorker:
    def __init__(
        self,
        engine: Engine,
        supervisor_factory: Callable[
            [WorkflowEventSink | None], SupervisorAgent
        ],
        *,
        poll_seconds: float = 2.0,
        guardrails_validator: GuardrailsValidator | None = None,
    ) -> None:
        if poll_seconds <= 0:
            raise ValueError("Worker polling interval must be positive")
        self.engine = engine
        self.supervisor_factory = supervisor_factory
        self.poll_seconds = poll_seconds
        self.guardrails_validator = guardrails_validator or GuardrailsValidator()
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    async def run_forever(self) -> None:
        while not self._stop.is_set():
            try:
                processed = await self.run_once()
            except SQLAlchemyError:
                logger.exception("Query worker database operation failed")
                # Discard pooled connections after server-side disconnects so
                # the next poll opens fresh connections.
                self.engine.dispose()
                processed = False
            if not processed:
                try:
                    await asyncio.wait_for(
                        self._stop.wait(), timeout=self.poll_seconds
                    )
                except TimeoutError:
                    continue

    async def run_once(self) -> bool:
        query = await asyncio.to_thread(self._claim_next_query)
        if query is None:
            return False
        context = QueryContext(
            query_id=query["query_id"],
            question=query["question"],
            portfolio_id=query["portfolio_id"],
            conversation_context=tuple(query.get("conversation_context") or ()),
            authorized_portfolio_ids=tuple(
                query.get("authorized_portfolio_ids") or ()
            ),
            all_portfolios_access=bool(query.get("all_portfolios_access")),
            principal_roles=tuple(query.get("principal_roles") or ()),
        )
        input_decision = self.guardrails_validator.validate_input(context.question)
        if not input_decision.allowed:
            logger.warning(
                "Queued query failed input validation",
                extra={"query_id": query["query_id"]},
            )
            await asyncio.to_thread(
                self._mark_failed,
                query["query_id"],
                QueryFailure(
                    code="invalid_query",
                    message=input_decision.reason or "Query input is invalid.",
                    retryable=False,
                ),
            )
            return True
        logger.info(
            "Query processing started",
            extra={
                "event": "query.processing.started",
                "query_id": query["query_id"],
                "portfolio_id": query.get("portfolio_id"),
            },
        )
        event_sink = self._event_sink(query["query_id"])
        safe_query = query
        trace_context = _query_trace_context(query["query_id"])
        try:
            with trace_attributes(
                session_id=query.get("session_id"),
                tags=["friis", "research"],
                metadata={
                    "query_id": query["query_id"],
                    **(
                        {"portfolio_id": str(query["portfolio_id"])}
                        if query.get("portfolio_id") is not None
                        else {}
                    ),
                },
            ):
                with observation(
                    name="friis-research-query",
                    as_type="agent",
                    input={"content_captured": False},
                    metadata={
                        "query_id": query["query_id"],
                        "portfolio_id": query.get("portfolio_id"),
                        "authorized_portfolio_count": len(
                            query.get("authorized_portfolio_ids") or ()
                        ),
                    },
                    trace_context=trace_context,
                ) as trace:
                    result = await self.supervisor_factory(event_sink).run(context)
                    if trace is not None:
                        trace.update(
                            output={
                                "status": result.status.value,
                                "citation_count": len(result.citations),
                                "limitation_count": len(result.limitations),
                                "requires_human_review": result.escalation is not None,
                            },
                            metadata={
                                "query_id": query["query_id"],
                                "portfolio_id": query.get("portfolio_id"),
                            },
                        )
            result, pii_detected = self.guardrails_validator.sanitize_result(result)
            if result.escalation is not None:
                question_decision = self.guardrails_validator.validate_output(
                    context.question
                )
                if question_decision.pii_detected:
                    safe_query = {
                        **query,
                        "question": question_decision.sanitized_text,
                    }
                    if PII_REDACTION_LIMITATION not in result.limitations:
                        result = result.model_copy(
                            update={
                                "limitations": result.limitations
                                + (PII_REDACTION_LIMITATION,)
                            }
                        )
                    pii_detected = True
            if pii_detected:
                logger.info(
                    "Sensitive personal information was redacted from query output",
                    extra={"query_id": query["query_id"]},
                )
        except ControlPlaneError:
            logger.exception(
                "Query control plane failed",
                extra={"query_id": query["query_id"]},
            )
            await asyncio.to_thread(
                self._mark_failed,
                query["query_id"],
                QueryFailure(
                    code="workflow_failed",
                    message="Query processing failed; retry later or contact support.",
                    retryable=True,
                ),
            )
            return True
        except Exception:
            logger.exception(
                "Unexpected query worker failure",
                extra={"query_id": query["query_id"]},
            )
            await asyncio.to_thread(
                self._mark_failed,
                query["query_id"],
                QueryFailure(
                    code="workflow_failed",
                    message="Query processing failed; retry later or contact support.",
                    retryable=True,
                ),
            )
            return True
        logger.info(
            "Query workflow produced a terminal result",
            extra={
                "query_id": query["query_id"],
                "query_status": result.status.value,
            },
        )
        await asyncio.to_thread(self._persist_result, safe_query, result)
        return True

    def _claim_next_query(self) -> dict[str, Any] | None:
        now = _utcnow()
        stale_before = now - timedelta(seconds=PROCESSING_STALE_SECONDS)
        with self.engine.begin() as connection:
            statement = (
                select(query_requests)
                .where(
                    or_(
                        query_requests.c.status == QueryStatus.QUEUED.value,
                        and_(
                            query_requests.c.status == QueryStatus.PROCESSING.value,
                            query_requests.c.updated_at < stale_before,
                        ),
                    )
                )
                .order_by(query_requests.c.created_at)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            row = connection.execute(statement).mappings().first()
            if row is None:
                return None
            was_stale = row["status"] == QueryStatus.PROCESSING.value
            connection.execute(
                update(query_requests)
                .where(query_requests.c.query_id == row["query_id"])
                .values(status=QueryStatus.PROCESSING.value, updated_at=now)
            )
            connection.execute(
                insert(query_workflow_events).values(
                    event_id=str(uuid4()),
                    query_id=row["query_id"],
                    event_type="query_claimed",
                    agent_name="Supervisor agent",
                    details={},
                    created_at=now,
                )
            )
            if was_stale:
                connection.execute(
                    insert(query_workflow_events).values(
                        event_id=str(uuid4()),
                        query_id=row["query_id"],
                        event_type="query_reclaimed",
                        agent_name="Supervisor agent",
                        details={
                            "reason": "stale_processing_lease",
                            "stale_after_seconds": PROCESSING_STALE_SECONDS,
                        },
                        created_at=now,
                    )
                )
        if was_stale:
            logger.warning(
                "Reclaimed query left in processing state",
                extra={"query_id": row["query_id"]},
            )
        else:
            logger.info(
                "Claimed queued query",
                extra={"query_id": row["query_id"]},
            )
        return dict(row)

    def _event_sink(self, query_id: str) -> WorkflowEventSink:
        async def record(
            event_type: str,
            agent_name: str | None,
            details: dict[str, Any],
        ) -> None:
            safe_details = {
                key: value
                for key, value in details.items()
                if key
                in {
                    "intent",
                    "specialists",
                    "tasks",
                    "task_id",
                    "manager_agent",
                    "agent_name",
                    "objective",
                    "child_agents",
                    "attempt",
                    "accepted",
                    "reason",
                    "scope_unchanged",
                    "from",
                    "to",
                    "correction_budget",
                    "correction_mode",
                    "delegated_agents",
                    "evidence_count",
                    "data_gap_count",
                    "route",
                    "specialist_count",
                    "citation_count",
                    "status",
                }
            }
            await asyncio.to_thread(
                self._write_event,
                query_id,
                event_type,
                agent_name,
                safe_details,
            )

        return record

    def _write_event(
        self,
        query_id: str,
        event_type: str,
        agent_name: str | None,
        details: dict[str, Any],
    ) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                insert(query_workflow_events).values(
                    event_id=str(uuid4()),
                    query_id=query_id,
                    event_type=event_type,
                    agent_name=agent_name,
                    details=details,
                    created_at=_utcnow(),
                )
            )

    def _persist_result(self, query: dict[str, Any], result: Any) -> None:
        now = _utcnow()
        with self.engine.begin() as connection:
            escalation_id = None
            if result.escalation is not None:
                escalation_id = str(uuid4())
                packet = result.escalation
                connection.execute(
                    insert(escalations).values(
                        escalation_id=escalation_id,
                        query_id=query["query_id"],
                        portfolio_id=query["portfolio_id"],
                        status=EscalationStatus.OPEN.value,
                        reason=packet.reason,
                        question=query["question"],
                        evidence=[
                            item.model_dump(mode="json") for item in packet.evidence
                        ],
                        attempted_steps=list(packet.attempted_steps),
                        data_gaps=list(packet.data_gaps),
                        requested_review=packet.requested_review,
                        created_at=now,
                        updated_at=now,
                    )
                )
            connection.execute(
                update(query_requests)
                .where(query_requests.c.query_id == query["query_id"])
                .values(
                    status=result.status.value,
                    answer=result.answer,
                    citations=[
                        item.model_dump(mode="json") for item in result.citations
                    ],
                    limitations=list(result.limitations),
                    clarification_question=result.clarification_question,
                    escalation_id=escalation_id,
                    conversation_context=[],
                    updated_at=now,
                )
            )
            connection.execute(
                insert(query_workflow_events).values(
                    event_id=str(uuid4()),
                    query_id=query["query_id"],
                    event_type="query_terminal",
                    agent_name="Supervisor agent",
                    details={
                        "status": result.status.value,
                        "citation_count": len(result.citations),
                        "escalated": escalation_id is not None,
                    },
                    created_at=now,
                )
            )
        logger.info(
            "Persisted terminal query result",
            extra={
                "query_id": query["query_id"],
                "query_status": result.status.value,
            },
        )

    def _mark_failed(self, query_id: str, failure: QueryFailure) -> None:
        now = _utcnow()
        with self.engine.begin() as connection:
            connection.execute(
                update(query_requests)
                .where(query_requests.c.query_id == query_id)
                .values(
                    status=QueryStatus.FAILED.value,
                    failure=failure.model_dump(mode="json"),
                    conversation_context=[],
                    updated_at=now,
                )
            )
            connection.execute(
                insert(query_workflow_events).values(
                    event_id=str(uuid4()),
                    query_id=query_id,
                    event_type="query_failed",
                    agent_name="Supervisor agent",
                    details={"failure_code": failure.code},
                    created_at=now,
                )
            )


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _query_trace_context(query_id: str) -> dict[str, str] | None:
    """Use the durable UUID as a stable Langfuse trace ID for later scoring."""
    try:
        trace_id = UUID(query_id).hex
    except (ValueError, AttributeError, TypeError):
        return None
    return {"trace_id": trace_id}
