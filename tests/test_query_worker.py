from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, insert, select
from sqlalchemy.pool import StaticPool

from agents.control_plane import (
    EscalationPacket,
    OrchestrationResult,
)
from schemas import Citation, QueryStatus
from services.database import (
    escalations,
    metadata,
    query_requests,
    query_workflow_events,
)
from services.guardrails import GuardrailsValidator
from services.query_worker import QueryWorker


class FakeSupervisor:
    def __init__(self, result, event_sink):
        self.result = result
        self.event_sink = event_sink

    async def run(self, context):
        await self.event_sink("plan_created", "Supervisor agent", {"intent": "test"})
        return self.result


@pytest.fixture
def engine():
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata.create_all(test_engine)
    yield test_engine
    test_engine.dispose()


def _insert_query(
    engine,
    *,
    portfolio_id=None,
    question="Summarize approved policy evidence.",
):
    query_id = str(uuid4())
    now = datetime.now(UTC)
    with engine.begin() as connection:
        connection.execute(
            insert(query_requests).values(
                query_id=query_id,
                owner_subject="auth0|analyst",
                question=question,
                portfolio_id=portfolio_id,
                status=QueryStatus.QUEUED.value,
                citations=[],
                limitations=[],
                created_at=now,
                updated_at=now,
            )
        )
    return query_id


@pytest.mark.asyncio
async def test_worker_persists_completed_answer_and_redacted_workflow_events(engine):
    query_id = _insert_query(engine)
    result = OrchestrationResult(
        status=QueryStatus.COMPLETED,
        answer="The evidence supports this summary.",
        citations=(
            Citation(
                source_id="policy-1",
                source_title="Approved policy",
                evidence_type="policy_document",
                excerpt="Relevant excerpt.",
                page_number=2,
            ),
        ),
        limitations=("Educational data.",),
    )
    worker = QueryWorker(
        engine,
        lambda sink: FakeSupervisor(result, sink),
        guardrails_validator=GuardrailsValidator(pii_scanner=lambda text: text),
    )

    assert await worker.run_once()

    with engine.connect() as connection:
        query = connection.execute(
            select(query_requests).where(query_requests.c.query_id == query_id)
        ).mappings().one()
        events = connection.execute(
            select(query_workflow_events).where(
                query_workflow_events.c.query_id == query_id
            )
        ).mappings().all()
    assert query["status"] == QueryStatus.COMPLETED.value
    assert query["answer"] == "The evidence supports this summary."
    assert query["citations"][0]["source_id"] == "policy-1"
    assert {event["event_type"] for event in events} >= {
        "query_claimed",
        "plan_created",
        "query_terminal",
    }


@pytest.mark.asyncio
async def test_worker_persists_escalation_and_links_query(engine):
    query_id = _insert_query(engine, portfolio_id=4)
    result = OrchestrationResult(
        status=QueryStatus.ESCALATED,
        limitations=("Human review required.",),
        escalation=EscalationPacket(
            reason="Evidence is insufficient.",
            attempted_steps=("Run the document retrieval agent.",),
            data_gaps=("No relevant passages.",),
            requested_review="Review the available evidence.",
        ),
    )
    worker = QueryWorker(
        engine,
        lambda sink: FakeSupervisor(result, sink),
        guardrails_validator=GuardrailsValidator(pii_scanner=lambda text: text),
    )

    assert await worker.run_once()

    with engine.connect() as connection:
        query = connection.execute(
            select(query_requests).where(query_requests.c.query_id == query_id)
        ).mappings().one()
        escalation = connection.execute(
            select(escalations).where(escalations.c.query_id == query_id)
        ).mappings().one()
    assert query["status"] == QueryStatus.ESCALATED.value
    assert query["escalation_id"] == escalation["escalation_id"]
    assert escalation["portfolio_id"] == 4
    assert escalation["status"] == "open"


@pytest.mark.asyncio
async def test_worker_marks_unexpected_workflow_failure_without_leaking_details(engine):
    query_id = _insert_query(engine)

    class BrokenSupervisor:
        async def run(self, context):
            raise RuntimeError("sensitive provider detail")

    worker = QueryWorker(
        engine,
        lambda sink: BrokenSupervisor(),
        guardrails_validator=GuardrailsValidator(pii_scanner=lambda text: text),
    )

    assert await worker.run_once()

    with engine.connect() as connection:
        query = connection.execute(
            select(query_requests).where(query_requests.c.query_id == query_id)
        ).mappings().one()
    assert query["status"] == QueryStatus.FAILED.value
    assert query["failure"]["code"] == "workflow_failed"
    assert "sensitive provider detail" not in query["failure"]["message"]


@pytest.mark.asyncio
async def test_worker_redacts_pii_from_persisted_answers_and_citations(engine):
    query_id = _insert_query(engine)
    sensitive_value = "analyst@example.com"
    result = OrchestrationResult(
        status=QueryStatus.COMPLETED,
        answer=f"Contact {sensitive_value}.",
        citations=(
            Citation(
                source_id="policy-1",
                source_title="Approved policy",
                evidence_type="policy_document",
                excerpt=f"Email: {sensitive_value}",
            ),
        ),
    )
    validator = GuardrailsValidator(
        pii_scanner=lambda text: text.replace(sensitive_value, "[REDACTED]")
    )
    worker = QueryWorker(
        engine,
        lambda sink: FakeSupervisor(result, sink),
        guardrails_validator=validator,
    )

    assert await worker.run_once()

    with engine.connect() as connection:
        query = connection.execute(
            select(query_requests).where(query_requests.c.query_id == query_id)
        ).mappings().one()
    assert "[REDACTED]" in query["answer"]
    assert "[REDACTED]" in query["citations"][0]["excerpt"]
    assert sensitive_value not in query["answer"]
    assert any("redacted" in item.lower() for item in query["limitations"])


@pytest.mark.asyncio
async def test_worker_redacts_pii_from_escalation_question(engine):
    sensitive_value = "analyst@example.com"
    query_id = _insert_query(
        engine,
        question=f"Contact {sensitive_value} about this policy.",
    )
    result = OrchestrationResult(
        status=QueryStatus.ESCALATED,
        escalation=EscalationPacket(
            reason="Evidence is insufficient.",
            requested_review="Review the available evidence.",
        ),
    )
    validator = GuardrailsValidator(
        pii_scanner=lambda text: text.replace(sensitive_value, "[REDACTED]")
    )
    worker = QueryWorker(
        engine,
        lambda sink: FakeSupervisor(result, sink),
        guardrails_validator=validator,
    )

    assert await worker.run_once()

    with engine.connect() as connection:
        escalation = connection.execute(
            select(escalations).where(escalations.c.query_id == query_id)
        ).mappings().one()
    assert "[REDACTED]" in escalation["question"]
    assert sensitive_value not in escalation["question"]


@pytest.mark.asyncio
async def test_worker_fails_closed_when_output_validation_fails(engine):
    query_id = _insert_query(engine)
    result = OrchestrationResult(
        status=QueryStatus.COMPLETED,
        answer="This answer must not be persisted.",
        citations=(
            Citation(
                source_id="policy-1",
                source_title="Approved policy",
                evidence_type="policy_document",
                excerpt="Relevant excerpt.",
            ),
        ),
    )

    def broken_scanner(_text: str) -> str:
        raise RuntimeError("local PII validator unavailable")

    worker = QueryWorker(
        engine,
        lambda sink: FakeSupervisor(result, sink),
        guardrails_validator=GuardrailsValidator(pii_scanner=broken_scanner),
    )

    assert await worker.run_once()

    with engine.connect() as connection:
        query = connection.execute(
            select(query_requests).where(query_requests.c.query_id == query_id)
        ).mappings().one()
    assert query["status"] == QueryStatus.FAILED.value
    assert query["answer"] is None
    assert query["failure"]["code"] == "workflow_failed"
