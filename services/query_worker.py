"""Durable worker for asynchronous query orchestration."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import and_, insert, or_, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from agents.control_plane import (
    ControlPlaneError,
    EscalationPacket,
    OrchestrationResult,
    QueryContext,
    QueryResultQualityScores,
    SupervisorAgent,
    WorkflowEventSink,
)
from handoff.handoff_service import (
    evaluate_confidence_value,
    evaluate_score,
    generate_handoff_reference_id,
)
from schemas import EscalationStatus, HandoffEvidence, QueryFailure, QueryStatus
from services.database import (
    escalations,
    query_requests,
    query_workflow_events,
)
from services.guardrails import (
    PII_REDACTION_LIMITATION,
    GuardrailsValidator,
)
from services.langfuse_tracing import (
    is_tracing_enabled,
    observation,
    record_scores,
    trace_attributes,
)

logger = logging.getLogger(__name__)
PROCESSING_STALE_SECONDS = 300
QueryResultEvaluator = Callable[
    [str, str, OrchestrationResult], Awaitable[QueryResultQualityScores]
]
HandoffEmailSender = Callable[[dict[str, Any]], None]


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
        result_evaluator: QueryResultEvaluator | None = None,
        handoff_email_sender: HandoffEmailSender | None = None,
    ) -> None:
        if poll_seconds <= 0:
            raise ValueError("Worker polling interval must be positive")
        self.engine = engine
        self.supervisor_factory = supervisor_factory
        self.poll_seconds = poll_seconds
        self.guardrails_validator = guardrails_validator or GuardrailsValidator()
        self.result_evaluator = result_evaluator
        self.handoff_email_sender = handoff_email_sender
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
        trace_context = _query_trace_context(query["query_id"])
        trace_id = (trace_context or {}).get("trace_id")
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
        trace_created = False
        try:
            with trace_attributes(
                session_id=query.get("session_id"),
                tags=["friis", "research"],
                metadata={
                    "query_id": query["query_id"],
                    **({"trace_id": trace_id} if trace_id is not None else {}),
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
                        **({"trace_id": trace_id} if trace_id is not None else {}),
                        "portfolio_id": query.get("portfolio_id"),
                        "authorized_portfolio_count": len(
                            query.get("authorized_portfolio_ids") or ()
                        ),
                    },
                    trace_context=trace_context,
                ) as trace:
                    trace_created = trace is not None and trace_id is not None
                    if trace_created:
                        logger.info(
                            "Langfuse query trace created",
                            extra={
                                "event": "query.trace.created",
                                "query_id": query["query_id"],
                                "trace_id": trace_id,
                            },
                        )
                    result = await self.supervisor_factory(event_sink).run(context)
                    result, pii_detected = self.guardrails_validator.sanitize_result(
                        result
                    )
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
                    quality_scores = await self._evaluate_result_scores(
                        query_id=query["query_id"],
                        trace_id=trace_id,
                        question=context.question,
                        result=result,
                    )
                    result, handoff_reason, quality_threshold_failed = (
                        self._apply_handoff_thresholds(
                            question=context.question,
                            result=result,
                            quality_scores=quality_scores,
                        )
                    )
                    if quality_threshold_failed:
                        question_decision = self.guardrails_validator.validate_output(
                            context.question
                        )
                        safe_query = {
                            **query,
                            "question": question_decision.sanitized_text,
                        }
                        if question_decision.pii_detected:
                            pii_detected = True
                            if PII_REDACTION_LIMITATION not in result.limitations:
                                result = result.model_copy(
                                    update={
                                        "limitations": result.limitations
                                        + (PII_REDACTION_LIMITATION,)
                                    }
                                )
                        if pii_detected:
                            logger.info(
                                "Sensitive personal information was redacted from query output",
                                extra={"query_id": query["query_id"]},
                            )
                    if trace is not None:
                        trace_output: dict[str, Any] = {
                            "status": result.status.value,
                            "citation_count": len(result.citations),
                            "limitation_count": len(result.limitations),
                            "requires_human_review": result.escalation is not None,
                        }
                        if quality_scores is not None:
                            trace_output["quality_scores"] = quality_scores
                        trace.update(
                            output=trace_output,
                            metadata={
                                "query_id": query["query_id"],
                                "portfolio_id": query.get("portfolio_id"),
                            },
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
                "trace_id": trace_id if trace_created else None,
                "query_status": result.status.value,
            },
        )
        await asyncio.to_thread(self._persist_result, safe_query, result)
        if handoff_reason is not None:
            if self.handoff_email_sender is None:
                logger.warning(
                    "Human handoff email sender is not configured",
                    extra={"query_id": query["query_id"]},
                )
            else:
                try:
                    await asyncio.to_thread(
                        self.handoff_email_sender,
                        self._handoff_email_context(
                            query_id=query["query_id"],
                            trace_id=trace_id or query["query_id"],
                            handoff_reason=handoff_reason,
                            quality_scores=quality_scores,
                            high_priority=quality_threshold_failed,
                        ),
                    )
                except Exception as exc:
                    logger.warning(
                        "Human handoff email could not be sent",
                        extra={
                            "query_id": query["query_id"],
                            "error_type": type(exc).__name__,
                        },
                    )
        return True

    async def _evaluate_result_scores(
        self,
        *,
        query_id: str,
        trace_id: str | None,
        question: str,
        result: OrchestrationResult,
    ) -> dict[str, float] | None:
        if (
            self.result_evaluator is None
            or not (result.answer or result.clarification_question or result.escalation)
        ):
            return None

        try:
            safe_question = self.guardrails_validator.validate_output(
                question
            ).sanitized_text
            scores = await self.result_evaluator(query_id, safe_question, result)
        except Exception as exc:
            logger.warning(
                "Query result quality evaluation failed",
                extra={
                    "query_id": query_id,
                    "error_type": type(exc).__name__,
                },
            )
            return None

        score_values = scores.model_dump()
        if trace_id is not None and is_tracing_enabled():
            record_scores(
                trace_id=trace_id,
                scores=score_values,
                metadata={
                    "query_id": query_id,
                    "score_scale": "0-1",
                    "score_source": "runtime_answer_quality",
                },
            )
        return score_values

    @staticmethod
    def _apply_handoff_thresholds(
        *,
        question: str,
        result: OrchestrationResult,
        quality_scores: dict[str, float] | None,
    ) -> tuple[OrchestrationResult, str | None, bool]:
        threshold_reasons: list[str] = []
        if quality_scores is not None:
            has_evidence = bool(
                result.citations
                or (
                    result.escalation is not None
                    and result.escalation.evidence
                )
            )
            score_decision = evaluate_score(
                faithfulness=quality_scores["faithfulness"],
                relevance=quality_scores["answer_relevance"],
                user_question=question,
                no_chunks=not has_evidence,
            )
            if score_decision["trigger"]:
                threshold_reasons.append(score_decision["reason"])
            confidence_decision = evaluate_confidence_value(
                quality_scores["confidence"]
            )
            if confidence_decision["trigger"]:
                threshold_reasons.append(confidence_decision["reason"])

        if result.escalation is not None:
            reasons = [result.escalation.reason, *threshold_reasons]
            if threshold_reasons:
                result = result.model_copy(
                    update={
                        "answer": None,
                        "clarification_question": None,
                        "escalation": result.escalation.model_copy(
                            update={"reason": "; ".join(dict.fromkeys(reasons))}
                        ),
                    }
                )
            email_reason = (
                "; ".join(dict.fromkeys(threshold_reasons))
                if threshold_reasons
                else "Existing result requires human review"
            )
            return result, email_reason, bool(threshold_reasons)

        if not threshold_reasons:
            return result, None, False

        evidence = tuple(
            HandoffEvidence(
                source_id=citation.source_id,
                source_title=citation.source_title,
                source_version=citation.source_version,
                excerpt=citation.excerpt,
                page_number=citation.page_number,
                record_reference=citation.record_reference,
            )
            for citation in result.citations
        )
        reason = "; ".join(dict.fromkeys(threshold_reasons))
        escalation = EscalationPacket(
            reason=reason,
            evidence=evidence,
            attempted_steps=("query_result_quality_evaluation",),
            data_gaps=(),
            requested_review="Review the query and its cited evidence before responding.",
        )
        limitation = "Automated quality thresholds were not met; human review is required."
        return (
            result.model_copy(
                update={
                    "status": QueryStatus.ESCALATED,
                    "answer": None,
                    "clarification_question": None,
                    "escalation": escalation,
                    "limitations": result.limitations
                    if limitation in result.limitations
                    else result.limitations + (limitation,),
                }
            ),
            reason,
            True,
        )

    @staticmethod
    def _handoff_email_context(
        *,
        query_id: str,
        trace_id: str,
        handoff_reason: str,
        quality_scores: dict[str, float] | None,
        high_priority: bool,
    ) -> dict[str, Any]:
        return {
            "reference_id": generate_handoff_reference_id(),
            "trace_id": trace_id,
            "timestamp_utc": _utcnow().isoformat(),
            "priority": "high" if high_priority else "normal",
            "trigger_reason": handoff_reason,
            "user_metadata": {"email": "Not included"},
            "session_id": "Not included",
            "query_history": (
                f"Query ID: {query_id}. Retrieve details from the authorized "
                "FRIIS review queue."
            ),
            "generated_answer": "Withheld from email; review the authorized FRIIS record.",
            "evaluation_scores": {
                "faithfulness": (
                    quality_scores["faithfulness"]
                    if quality_scores is not None
                    else "unavailable"
                ),
                "relevance": (
                    quality_scores["answer_relevance"]
                    if quality_scores is not None
                    else "unavailable"
                ),
                "confidence": (
                    round(quality_scores["confidence"] * 100)
                    if quality_scores is not None
                    else "unavailable"
                ),
            },
            "retrieved_chunks": "Withheld from email; review the authorized FRIIS record.",
            "conversation_flow": f"Query ID: {query_id}",
        }

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
