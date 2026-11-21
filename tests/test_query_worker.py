import logging
from contextlib import nullcontext
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, insert, select
from sqlalchemy.pool import StaticPool

from agents.control_plane import (
    EscalationPacket,
    OrchestrationResult,
    QueryResultQualityScores,
)
from schemas import Citation, QueryStatus
from services.database import (
    escalations,
    metadata,
    query_requests,
    query_workflow_events,
)
from services.guardrails import GuardrailsValidator
from services import query_worker as query_worker_module
from services.query_worker import QueryWorker


@pytest.mark.parametrize(
    ("quality_scores", "expected_reason"),
    [
        (
            {"faithfulness": 0.59, "answer_relevance": 0.9, "confidence": 0.9},
            "faithfulness below",
        ),
        (
            {"faithfulness": 0.9, "answer_relevance": 0.49, "confidence": 0.9},
            "answer relevance below",
        ),
        (
            {"faithfulness": 0.9, "answer_relevance": 0.9, "confidence": 0.39},
            "LLM confidence below",
        ),
    ],
)
def test_worker_applies_each_quality_handoff_threshold(
    quality_scores, expected_reason
):
    result = OrchestrationResult(
        status=QueryStatus.COMPLETED,
        answer="Evidence-backed answer.",
        citations=(
            Citation(
                source_id="policy-1",
                source_title="Approved policy",
                evidence_type="policy_document",
            ),
        ),
    )

    updated_result, reason, threshold_failed = (
        QueryWorker._apply_handoff_thresholds(
            question="Summarize the policy.",
            result=result,
            quality_scores=quality_scores,
        )
    )

    assert updated_result.status == QueryStatus.ESCALATED
    assert threshold_failed
    assert expected_reason in reason


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
async def test_worker_persists_escalation_and_links_query(engine, caplog):
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
    def failing_email_sender(_context):
        raise RuntimeError("SMTP credentials unavailable")

    worker = QueryWorker(
        engine,
        lambda sink: FakeSupervisor(result, sink),
        guardrails_validator=GuardrailsValidator(pii_scanner=lambda text: text),
        handoff_email_sender=failing_email_sender,
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
    assert "Human handoff email could not be sent" in caplog.text


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
async def test_worker_scores_sanitized_result_on_its_langfuse_trace(
    engine, monkeypatch, caplog
):
    caplog.set_level(logging.INFO, logger="services.query_worker")
    sensitive_value = "analyst@example.com"
    query_id = _insert_query(
        engine,
        question=f"Contact {sensitive_value} about this policy.",
    )
    result = OrchestrationResult(
        status=QueryStatus.COMPLETED,
        answer=f"Contact {sensitive_value}.",
        citations=(
            Citation(
                source_id="policy-1",
                source_title="Approved policy",
                evidence_type="policy_document",
                excerpt=f"Email {sensitive_value}.",
            ),
        ),
    )
    evaluator_calls = []
    recorded_scores = []
    observations = []

    class FakeSpan:
        def update(self, **_kwargs):
            pass

    async def evaluate_result(evaluated_query_id, question, evaluated_result):
        evaluator_calls.append(
            (evaluated_query_id, question, evaluated_result)
        )
        return QueryResultQualityScores(
            faithfulness=0.9,
            correctness=0.9,
            answer_relevance=0.8,
            context_precision=0.9,
            usefulness=0.9,
            confidence=0.7,
        )

    monkeypatch.setattr(query_worker_module, "is_tracing_enabled", lambda: True)
    monkeypatch.setattr(
        query_worker_module,
        "record_scores",
        lambda **kwargs: recorded_scores.append(kwargs),
    )
    monkeypatch.setattr(
        query_worker_module,
        "observation",
        lambda **kwargs: (
            observations.append(kwargs)
            or nullcontext(
                FakeSpan()
                if kwargs["name"] == "friis-research-query"
                else None
            )
        ),
    )
    monkeypatch.setattr(
        query_worker_module,
        "trace_attributes",
        lambda **_kwargs: nullcontext(),
    )
    worker = QueryWorker(
        engine,
        lambda sink: FakeSupervisor(result, sink),
        guardrails_validator=GuardrailsValidator(
            pii_scanner=lambda text: text.replace(sensitive_value, "[REDACTED]")
        ),
        result_evaluator=evaluate_result,
        handoff_email_sender=lambda context: pytest.fail(
            f"Passing quality scores unexpectedly triggered email: {context}"
        ),
    )

    assert await worker.run_once()

    trace_id = query_id.replace("-", "")
    assert any(
        record.getMessage() == "Langfuse query trace created"
        and getattr(record, "query_id", None) == query_id
        and getattr(record, "trace_id", None) == trace_id
        for record in caplog.records
    )
    root_trace = next(
        item for item in observations if item["name"] == "friis-research-query"
    )
    assert root_trace["trace_context"] == {"trace_id": trace_id}
    assert root_trace["metadata"]["trace_id"] == trace_id

    evaluated_query_id, evaluated_question, evaluated_result = evaluator_calls[0]
    assert evaluated_query_id == query_id
    assert sensitive_value not in evaluated_question
    assert sensitive_value not in evaluated_result.answer
    assert sensitive_value not in evaluated_result.citations[0].excerpt
    assert recorded_scores == [
        {
            "trace_id": trace_id,
            "scores": {
                "faithfulness": 0.9,
                "correctness": 0.9,
                "answer_relevance": 0.8,
                "context_precision": 0.9,
                "usefulness": 0.9,
                "confidence": 0.7,
            },
            "metadata": {
                "query_id": query_id,
                "score_scale": "0-1",
                "score_source": "runtime_answer_quality",
            },
        }
    ]
    with engine.connect() as connection:
        query = connection.execute(
            select(query_requests).where(query_requests.c.query_id == query_id)
        ).mappings().one()
    assert query["status"] == QueryStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_worker_escalates_low_scores_and_emails_only_review_metadata(
    engine, monkeypatch
):
    query_id = _insert_query(engine, question="Review the portfolio risk.")
    private_excerpt = "Portfolio allocation contains confidential values."
    result = OrchestrationResult(
        status=QueryStatus.COMPLETED,
        answer="This answer must be withheld for review.",
        citations=(
            Citation(
                source_id="portfolio-record-1",
                source_title="Portfolio holdings",
                evidence_type="portfolio_record",
                excerpt=private_excerpt,
            ),
        ),
    )
    emails = []
    evaluator_calls = []

    async def evaluate_result(evaluated_query_id, question, evaluated_result):
        evaluator_calls.append((evaluated_query_id, question, evaluated_result))
        return QueryResultQualityScores(
            faithfulness=0.4,
            correctness=0.5,
            answer_relevance=0.3,
            context_precision=0.4,
            usefulness=0.4,
            confidence=0.2,
        )

    monkeypatch.setattr(query_worker_module, "is_tracing_enabled", lambda: False)
    monkeypatch.setattr(
        query_worker_module,
        "observation",
        lambda **_kwargs: nullcontext(None),
    )
    monkeypatch.setattr(
        query_worker_module,
        "trace_attributes",
        lambda **_kwargs: nullcontext(),
    )
    worker = QueryWorker(
        engine,
        lambda sink: FakeSupervisor(result, sink),
        guardrails_validator=GuardrailsValidator(pii_scanner=lambda text: text),
        result_evaluator=evaluate_result,
        handoff_email_sender=emails.append,
    )

    assert await worker.run_once()

    with engine.connect() as connection:
        query = connection.execute(
            select(query_requests).where(query_requests.c.query_id == query_id)
        ).mappings().one()
        escalation = connection.execute(
            select(escalations).where(escalations.c.query_id == query_id)
        ).mappings().one()
    assert len(evaluator_calls) == 1
    assert query["status"] == QueryStatus.ESCALATED.value
    assert query["answer"] is None
    assert "faithfulness below 0.6" in escalation["reason"]
    assert "LLM confidence below 40" in escalation["reason"]
    assert len(emails) == 1
    email = emails[0]
    assert email["priority"] == "high"
    assert email["evaluation_scores"] == {
        "faithfulness": 0.4,
        "relevance": 0.3,
        "confidence": 20,
    }
    assert email["query_history"].endswith("authorized FRIIS review queue.")
    serialized_email = repr(email)
    assert query_id in serialized_email
    assert "This answer must be withheld" not in serialized_email
    assert private_excerpt not in serialized_email


@pytest.mark.asyncio
async def test_worker_keeps_result_when_quality_evaluation_fails(
    engine, monkeypatch, caplog
):
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
            ),
        ),
    )

    async def failing_evaluator(_query_id, _question, _result):
        raise RuntimeError("judge unavailable")

    monkeypatch.setattr(query_worker_module, "is_tracing_enabled", lambda: True)
    monkeypatch.setattr(
        query_worker_module,
        "observation",
        lambda **_kwargs: nullcontext(None),
    )
    monkeypatch.setattr(
        query_worker_module,
        "trace_attributes",
        lambda **_kwargs: nullcontext(),
    )
    worker = QueryWorker(
        engine,
        lambda sink: FakeSupervisor(result, sink),
        guardrails_validator=GuardrailsValidator(pii_scanner=lambda text: text),
        result_evaluator=failing_evaluator,
        handoff_email_sender=lambda context: pytest.fail(
            f"Failed quality evaluation unexpectedly triggered email: {context}"
        ),
    )

    assert await worker.run_once()

    with engine.connect() as connection:
        query = connection.execute(
            select(query_requests).where(query_requests.c.query_id == query_id)
        ).mappings().one()
    assert query["status"] == QueryStatus.COMPLETED.value
    assert "Query result quality evaluation failed" in caplog.text


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
