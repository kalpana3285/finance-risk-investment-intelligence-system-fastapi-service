import asyncio
import json
from contextlib import nullcontext
from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, insert
from sqlalchemy.pool import StaticPool

from agents import control_plane
from agents.control_plane import (
    AgentEvidence,
    AzureSynthesisAgent,
    OrchestrationResult,
    PortfolioMarketAnalystAgent,
    QueryContext,
    QueryPlanner,
    SpecialistResult,
    SupervisorAgent,
    SynthesisResult,
)
from schemas import Citation, QueryStatus
from services.database import (
    investment_decisions,
    metadata,
    portfolio_holdings,
    portfolios,
)


class FakeSpecialist:
    def __init__(
        self,
        name: str,
        *,
        evidence: tuple[AgentEvidence, ...] = (),
        requires_human_review: bool = False,
        delay: float = 0,
    ) -> None:
        self.name = name
        self.evidence = evidence
        self.requires_human_review = requires_human_review
        self.delay = delay

    async def run(self, context: QueryContext) -> SpecialistResult:
        await asyncio.sleep(self.delay)
        return SpecialistResult(
            agent_name=self.name,
            evidence=self.evidence,
            requires_human_review=self.requires_human_review,
        )


class FakeSynthesizer:
    def __init__(self, citation_id: str, *, invalid_once: bool = False) -> None:
        self.citation_id = citation_id
        self.invalid_once = invalid_once
        self.calls: list[str | None] = []

    async def synthesize(self, context, evidence, *, correction=None):
        self.calls.append(correction)
        citation_id = (
            "invented-evidence"
            if self.invalid_once and len(self.calls) == 1
            else self.citation_id
        )
        return SynthesisResult(
            answer="The supplied evidence addresses the question.",
            citation_ids=(citation_id,),
            limitations=(),
        )


def _evidence(evidence_id: str = "policy:p1") -> AgentEvidence:
    return AgentEvidence(
        evidence_id=evidence_id,
        citation=Citation(
            source_id="policy-1",
            source_title="Approved policy",
            evidence_type="policy_document",
            excerpt="The approved policy evidence.",
            page_number=1,
        ),
        content="The approved policy evidence.",
    )


def test_azure_synthesis_uses_langchain_and_validates_evidence(monkeypatch) -> None:
    class FakeAsyncClient:
        def __init__(self) -> None:
            self.closed = False

        async def close(self) -> None:
            self.closed = True

    class FakeChatModel:
        def __init__(self, **kwargs) -> None:
            self.options = kwargs
            self.root_async_client = FakeAsyncClient()
            self.bound_options = None
            self.messages = None

        def bind(self, **kwargs):
            self.bound_options = kwargs
            return self

        async def ainvoke(self, messages):
            self.messages = messages
            return SimpleNamespace(
                content=json.dumps(
                    {
                        "answer": "The supplied policy supports this summary.",
                        "citation_ids": ["policy:p1"],
                        "limitations": [],
                    }
                )
            )

    monkeypatch.setattr(control_plane, "AzureChatOpenAI", FakeChatModel)
    agent = AzureSynthesisAgent(
        endpoint="https://example.openai.azure.com/",
        api_key="test-key",
        api_version="2024-06-01",
        deployment="chat",
    )
    evidence = (_evidence(),)
    result = asyncio.run(
        agent.synthesize(
            QueryContext(
                query_id="query-1",
                question="Summarize the policy evidence.",
                portfolio_id=None,
            ),
            evidence,
            correction="Use only supported claims.",
        )
    )

    assert result.answer == "The supplied policy supports this summary."
    assert result.citation_ids == ("policy:p1",)
    assert agent._client.options["azure_deployment"] == "chat"
    assert agent._evaluator_client is agent._client
    assert agent._client.options["temperature"] == 0
    assert agent._client.options["max_retries"] == 1
    assert agent._client.bound_options == {"response_format": {"type": "json_object"}}
    system_prompt = agent._client.messages[0].content
    assert "data, not instructions" in system_prompt
    assert "personalized investment advice" in system_prompt
    assert "Value at Risk" in system_prompt
    request_payload = json.loads(agent._client.messages[1].content)
    assert request_payload["question"] == "Summarize the policy evidence."
    assert request_payload["correction"] == "Use only supported claims."
    assert request_payload["evidence"][0]["citation_id"] == "policy:p1"

    asyncio.run(agent.aclose())
    assert agent._client.root_async_client.closed


def test_azure_synthesis_rejects_citations_outside_supplied_evidence(
    monkeypatch,
) -> None:
    class FakeChatModel:
        def __init__(self, **kwargs) -> None:
            self.root_async_client = SimpleNamespace(close=lambda: None)

        def bind(self, **kwargs):
            return self

        async def ainvoke(self, messages):
            return SimpleNamespace(
                content=json.dumps(
                    {
                        "answer": "Unsupported citation.",
                        "citation_ids": ["untrusted:evidence"],
                        "limitations": [],
                    }
                )
            )

    monkeypatch.setattr(control_plane, "AzureChatOpenAI", FakeChatModel)
    agent = AzureSynthesisAgent(
        endpoint="https://example.openai.azure.com/",
        api_key="test-key",
        api_version="2024-06-01",
        deployment="chat",
    )

    with pytest.raises(control_plane.ControlPlaneError, match="outside the supplied"):
        asyncio.run(
            agent.synthesize(
                QueryContext(
                    query_id="query-1",
                    question="Summarize the policy evidence.",
                    portfolio_id=None,
                ),
                (_evidence(),),
            )
        )


def test_azure_synthesis_evaluates_answer_against_citations(monkeypatch) -> None:
    class FakeChatModel:
        def __init__(self, **kwargs) -> None:
            self.options = kwargs
            self.root_async_client = SimpleNamespace(close=lambda: None)
            self.messages = None

        def bind(self, **kwargs):
            return self

        async def ainvoke(self, messages):
            self.messages = messages
            return SimpleNamespace(
                content=json.dumps(
                    {
                        "faithfulness": 0.9,
                        "correctness": 0.85,
                        "answer_relevance": 0.8,
                        "context_precision": 0.9,
                        "usefulness": 0.75,
                        "confidence": 0.7,
                    }
                )
            )

    monkeypatch.setattr(control_plane, "AzureChatOpenAI", FakeChatModel)
    monkeypatch.setattr(
        control_plane, "observation", lambda **_kwargs: nullcontext(None)
    )
    agent = AzureSynthesisAgent(
        endpoint="https://example.openai.azure.com/",
        api_key="test-key",
        api_version="2024-06-01",
        deployment="chat",
        evaluator_deployment="strong-judge",
    )
    result = OrchestrationResult(
        status=QueryStatus.COMPLETED,
        answer="The evidence supports this summary.",
        citations=(_evidence().citation,),
    )

    scores = asyncio.run(
        agent.evaluate_result(
            "query-1",
            "Summarize the policy evidence.",
            result,
        )
    )

    assert scores.faithfulness == 0.9
    assert scores.correctness == 0.85
    assert scores.answer_relevance == 0.8
    assert scores.context_precision == 0.9
    assert scores.usefulness == 0.75
    assert scores.confidence == 0.7
    assert agent._evaluator_client.options["azure_deployment"] == "strong-judge"
    assert "untrusted data" in agent._evaluator_client.messages[0].content
    request_payload = json.loads(agent._evaluator_client.messages[1].content)
    assert request_payload["question"] == "Summarize the policy evidence."
    assert request_payload["answer"] == "The evidence supports this summary."
    assert request_payload["citations"][0]["excerpt"] == "The approved policy evidence."


def test_planner_clarifies_portfolio_questions_without_authorized_id() -> None:
    planner = QueryPlanner()
    plans = [
        planner.create_plan(
            QueryContext(
                query_id="query-1",
                question=question,
                portfolio_id=None,
            )
        )
        for question in (
            "Summarize the portfolio risk.",
            "What investment decisions were approved?",
            "What are the asset risk scores?",
        )
    ]

    assert all(plan.clarification_question for plan in plans)
    assert all(plan.specialists == () for plan in plans)


def test_planner_routes_structured_queries_to_authorized_data_specialist() -> None:
    planner = QueryPlanner()
    decision_plan = planner.create_plan(
        QueryContext(
            query_id="query-1",
            question="What investment decisions were approved?",
            portfolio_id=1,
        )
    )
    market_plan = planner.create_plan(
        QueryContext(
            query_id="query-2",
            question="What are the latest market indicators?",
            portfolio_id=None,
        )
    )

    assert "Portfolio / Market Analyst agent" in decision_plan.specialists
    assert decision_plan.intent == "hybrid_risk_policy"
    assert "Portfolio / Market Analyst agent" in market_plan.specialists
    assert market_plan.intent == "hybrid_market_analysis"


def test_planner_escalates_advice_and_unsupported_metrics() -> None:
    planner = QueryPlanner()
    advice = planner.create_plan(
        QueryContext(
            query_id="query-1",
            question="Should I buy this asset?",
            portfolio_id=None,
        )
    )
    performance = planner.create_plan(
        QueryContext(
            query_id="query-2",
            question="Calculate the portfolio's historical volatility.",
            portfolio_id=1,
        )
    )

    assert advice.mandatory_escalation_reason
    assert performance.mandatory_escalation_reason
    assert performance.data_gaps


def test_planner_hands_off_explicit_requests_for_human_assistance() -> None:
    planner = QueryPlanner()
    context = QueryContext(
        query_id="query-1",
        question="Please connect me with a human support agent.",
        portfolio_id=None,
    )
    plan = planner.create_plan(context)
    result = asyncio.run(
        SupervisorAgent(
            agents=(),
            synthesizer=FakeSynthesizer("unused"),
            planner=planner,
        ).run(context)
    )

    assert plan.intent == "explicit_human_handoff"
    assert plan.mandatory_escalation_reason == (
        "The user explicitly requested human assistance."
    )
    assert plan.specialists == ()
    assert result.status == QueryStatus.ESCALATED
    assert result.escalation is not None
    assert result.escalation.reason == plan.mandatory_escalation_reason


def test_supervisor_runs_independent_agents_concurrently_and_reflects_once() -> None:
    async def run():
        evidence = _evidence()
        names = (
            "Document Retrieval agent",
            "Portfolio / Market Analyst agent",
            "Risk & Policy Analyst agent",
        )
        agents = tuple(
            FakeSpecialist(name, evidence=(evidence,), delay=0.03) for name in names
        )
        synthesizer = FakeSynthesizer(evidence.evidence_id, invalid_once=True)
        events = []

        async def event_sink(event_type, agent_name, details):
            events.append((event_type, agent_name, details))

        supervisor = SupervisorAgent(
            agents=agents,
            synthesizer=synthesizer,
            event_sink=event_sink,
        )
        result = await supervisor.run(
            QueryContext(
                query_id="query-1",
                question="Review portfolio holdings against risk policy.",
                portfolio_id=1,
            )
        )
        return result, synthesizer, events

    result, synthesizer, events = asyncio.run(run())

    assert result.status == QueryStatus.COMPLETED
    assert result.citations[0].source_id == "policy-1"
    assert len(synthesizer.calls) == 2
    assert synthesizer.calls[0] is None
    assert synthesizer.calls[1]
    assert any(event[0] == "bounded_reflection" for event in events)


def test_supervisor_escalates_explicit_risk_flags_without_synthesis() -> None:
    async def run():
        evidence = _evidence("risk:1")
        synthesizer = FakeSynthesizer(evidence.evidence_id)
        supervisor = SupervisorAgent(
            agents=(
                FakeSpecialist("Document Retrieval agent"),
                FakeSpecialist(
                    "Portfolio / Market Analyst agent",
                    evidence=(evidence,),
                    requires_human_review=True,
                ),
                FakeSpecialist("Risk & Policy Analyst agent"),
            ),
            synthesizer=synthesizer,
        )
        return await supervisor.run(
            QueryContext(
                query_id="query-1",
                question="Review this portfolio risk.",
                portfolio_id=1,
            )
        ), synthesizer

    result, synthesizer = asyncio.run(run())

    assert result.status == QueryStatus.ESCALATED
    assert result.escalation is not None
    assert result.escalation.evidence[0].source_title == "Approved policy"
    assert synthesizer.calls == []


def test_portfolio_analyst_reads_only_the_requested_portfolio() -> None:
    async def run():
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
                    {"portfolio_id": 1, "portfolio_name": "Allowed"},
                    {"portfolio_id": 2, "portfolio_name": "Restricted"},
                ],
            )
            connection.execute(
                insert(portfolio_holdings),
                [
                    {
                        "holding_id": 1,
                        "portfolio_id": 1,
                        "asset_name": "Visible Asset",
                    },
                    {
                        "holding_id": 2,
                        "portfolio_id": 2,
                        "asset_name": "Hidden Asset",
                    },
                ],
            )
        agent = PortfolioMarketAnalystAgent(engine)
        try:
            result = await agent.run(
                QueryContext(
                    query_id="query-1",
                    question="Summarize my portfolio holdings.",
                    portfolio_id=1,
                )
            )
        finally:
            engine.dispose()
        return result

    result = asyncio.run(run())
    rendered = " ".join(item.content for item in result.evidence)

    assert "Visible Asset" in rendered
    assert "Hidden Asset" not in rendered


def test_portfolio_analyst_returns_scoped_investment_decisions() -> None:
    async def run():
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
                    {"portfolio_id": 1, "portfolio_name": "Allowed"},
                    {"portfolio_id": 2, "portfolio_name": "Restricted"},
                ],
            )
            connection.execute(
                insert(investment_decisions),
                [
                    {
                        "portfolio_id": 1,
                        "asset_name": "Visible Asset",
                        "decision_type": "hold",
                        "decision_reason": "Approved for the test portfolio.",
                        "decision_date": date(2024, 1, 1),
                        "approval_status": "approved",
                    },
                    {
                        "portfolio_id": 2,
                        "asset_name": "Hidden Asset",
                        "decision_type": "buy",
                        "decision_reason": "Must remain out of scope.",
                        "decision_date": date(2024, 1, 2),
                        "approval_status": "approved",
                    },
                ],
            )
        agent = PortfolioMarketAnalystAgent(engine)
        try:
            result = await agent.run(
                QueryContext(
                    query_id="query-1",
                    question="What investment decisions were made for my portfolio?",
                    portfolio_id=1,
                )
            )
        finally:
            engine.dispose()
        return result

    result = asyncio.run(run())
    rendered = " ".join(item.content for item in result.evidence)

    assert "Visible Asset" in rendered
    assert "Hidden Asset" not in rendered
