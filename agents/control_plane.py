"""Bounded Supervisor workflow and narrowly scoped specialist agents."""

import asyncio
import json
import logging
import re
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Any, Protocol

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import AzureChatOpenAI
from openai import APIConnectionError, APIError, APITimeoutError
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from schemas import Citation, HandoffEvidence, QueryStatus
from prompts.catalog import get_prompt
from services.database import (
    asset_risk_logs,
    document_chunks,
    document_versions,
    investment_decisions,
    market_indicators,
    portfolio_holdings,
    portfolios,
    source_documents,
)
from services.embeddings import EmbeddingProvider, EmbeddingProviderError
from services.fusion_retrieval import bm25_rank, reciprocal_rank_fusion
from services.langfuse_tracing import observation

logger = logging.getLogger(__name__)

_SYNTHESIS_PROMPT_DEFINITION = get_prompt("finance-synthesis")
_SYNTHESIS_PROMPT = ChatPromptTemplate.from_messages(
    [
        (message["role"], message["content"])
        for message in _SYNTHESIS_PROMPT_DEFINITION["messages"]
    ]
)
_QUERY_RESULT_EVALUATOR_PROMPT_DEFINITION = get_prompt(
    "friis-query-result-evaluator"
)
_QUERY_RESULT_EVALUATOR_PROMPT = ChatPromptTemplate.from_messages(
    [
        (message["role"], message["content"])
        for message in _QUERY_RESULT_EVALUATOR_PROMPT_DEFINITION["messages"]
    ]
)

MAX_SPECIALISTS = 3
MAX_EVIDENCE_ITEMS = 12
MAX_EVIDENCE_CHARS = 1600
MAX_AGENT_SECONDS = 40.0
MAX_SYNTHESIS_SECONDS = 30.0
MAX_RESULT_EVALUATION_SECONDS = 15.0
# A specialist gets its initial attempt plus two bounded retries. The workflow
# deadline covers a leaf, a dependent manager, specialist retries, and synthesis.
MAX_WORKFLOW_SECONDS = 200.0
MAX_WORKFLOW_CORRECTIONS = 2
MAX_SPECIALIST_ATTEMPTS = MAX_WORKFLOW_CORRECTIONS + 1

_RETRIEVAL_STOP_WORDS = frozenset(
    {
        "a", "an", "and", "are", "about", "can", "do", "does", "for",
        "from", "how", "i", "in", "is", "it", "me", "my", "of", "on",
        "or", "please", "show", "tell", "that", "the", "these", "this",
        "those", "to", "was", "were", "what", "when", "where", "which",
        "who", "why", "with",
    }
)

_PORTFOLIO_TERMS = re.compile(
    r"\b(portfolio|holdings?|allocation|exposure|asset mix|risk scores?|"
    r"risk ratings?|risk levels?|risk logs?|escalation flags?|"
    r"investment decisions?|decision history|approval status|"
    r"approved investments?)\b",
    re.IGNORECASE,
)
_PORTFOLIO_ACCESS_TERMS = re.compile(
    r"\b(?:what|which)\s+portfolios?\s+(?:can\s+i\s+access|available\s+to\s+me|do\s+i\s+have\s+access\s+to)\b|"
    r"\b(?:list|show)\s+(?:all\s+)?portfolios?\b|"
    r"\bportfolios?\s+(?:i\s+can\s+access|accessible\s+to\s+me)\b",
    re.IGNORECASE,
)
_RISK_TERMS = re.compile(
    r"\b(risk|policy|compliance|regulat|basel|exposure|breach|limit)\w*\b",
    re.IGNORECASE,
)
_CURRENT_MARKET_DATA_TERMS = re.compile(
    r"\b(latest|current|recorded|indicator|indicators|value|values|data)\b|"
    r"\bmarket context\b",
    re.IGNORECASE,
)
_DECISION_TERMS = re.compile(
    r"\b(decisions?|approvals?|investment history|previously approved|"
    r"investment decisions?|decision history|approval status|"
    r"approved investments?)\b",
    re.IGNORECASE,
)
_DOCUMENT_TERMS = re.compile(
    r"\b(policy|compliance|regulat|basel|strategy|framework|guideline|"
    r"document|procedure|guide|concentration|limit|cap|issuer|prohibited|"
    r"threshold)\w*\b",
    re.IGNORECASE,
)
_UNSUPPORTED_METRICS = re.compile(
    r"\b(value at risk|var|volatility|drawdown|benchmark[- ]relative|"
    r"historical returns?|backtest(?:ing)?)\b",
    re.IGNORECASE,
)
_ADVICE_TERMS = re.compile(
    r"\b(should i buy|should i sell|should i invest|should i trade|"
    r"what should i invest in|personalized financial advice|"
    r"recommend(?:ation)?s? (?:a|an|the)? ?(?:stock|asset|investment|trade)|"
    r"execute (?:a )?(?:trade|sale|purchase)|place (?:a )?(?:trade|order)|"
    r"guaranteed (?:high[- ]?)?returns?|"
    r"approve (?:a |an |the )?(?:position|investment|trade|allocation)|"
    r"authorize (?:a |an |the )?(?:position|investment|trade|allocation)|"
    r"authorise (?:a |an |the )?(?:position|investment|trade|allocation)|"
    r"should we (?:increase|decrease|raise|lower|permit|approve)|"
    r"can i (?:override|permit|approve|authorize|authorise|treat)|"
    r"safe to approve|trade approval)\b",
    re.IGNORECASE,
)
_HUMAN_HANDOFF_REQUEST = re.compile(
    r"\b(?:need|want|request|speak|talk|connect|transfer|escalate)\b.{0,50}"
    r"\b(?:human|agent|person|representative|support)\b"
    r"|\b(?:human|live|customer)\s+(?:agent|support|representative)\b",
    re.IGNORECASE,
)


class QueryPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    specialists: tuple[str, ...] = Field(max_length=MAX_SPECIALISTS)
    intent: str = Field(min_length=1, max_length=80)
    clarification_question: str | None = None
    mandatory_escalation_reason: str | None = None
    data_gaps: tuple[str, ...] = ()


class AgentEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_id: str
    citation: Citation
    content: str = Field(min_length=1, max_length=MAX_EVIDENCE_CHARS)


class SpecialistResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    agent_name: str
    evidence: tuple[AgentEvidence, ...] = Field(max_length=MAX_EVIDENCE_ITEMS)
    data_gaps: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    requires_human_review: bool = False
    delegated_agents: tuple[str, ...] = ()


class WorkflowPhase(StrEnum):
    PLANNING = "planning"
    ACTING = "acting"
    CHECKING = "checking"
    REFLECTING = "reflecting"
    SYNTHESIZING = "synthesizing"
    COMPLETED = "completed"
    NEEDS_CLARIFICATION = "needs_clarification"
    ESCALATED = "escalated"


class CorrectionMode(StrEnum):
    RETRY_READ_ONLY = "retry_read_only"
    FOCUS_RETRIEVAL = "focus_retrieval"


class WorkflowTask(BaseModel):
    """A bounded manager-to-agent assignment included in the workflow trace."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str
    manager_agent: str
    agent_name: str
    objective: str
    child_agents: tuple[str, ...] = ()


@dataclass
class SynthesisCorrectionState:
    """Request-scoped state for the manager's Plan–Act–Check–Reflect loop."""

    phase: WorkflowPhase | None = None
    correction_used: bool = False
    correction_target: str | None = None
    task_attempts: dict[str, int] = field(default_factory=dict)


class SynthesisResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    answer: str = Field(min_length=1, max_length=8000)
    citation_ids: tuple[str, ...] = Field(min_length=1, max_length=MAX_EVIDENCE_ITEMS)
    limitations: tuple[str, ...] = ()


class EscalationPacket(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reason: str
    evidence: tuple[HandoffEvidence, ...] = ()
    attempted_steps: tuple[str, ...] = ()
    data_gaps: tuple[str, ...] = ()
    requested_review: str


class OrchestrationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: QueryStatus
    answer: str | None = None
    citations: tuple[Citation, ...] = ()
    limitations: tuple[str, ...] = ()
    clarification_question: str | None = None
    escalation: EscalationPacket | None = None


class QueryResultQualityScores(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    faithfulness: float = Field(ge=0, le=1)
    correctness: float = Field(ge=0, le=1)
    answer_relevance: float = Field(ge=0, le=1)
    context_precision: float = Field(ge=0, le=1)
    usefulness: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)


@dataclass(frozen=True)
class QueryContext:
    query_id: str
    question: str
    portfolio_id: int | None
    conversation_context: tuple[str, ...] = ()
    authorized_portfolio_ids: tuple[int, ...] = ()
    all_portfolios_access: bool = False
    principal_roles: tuple[str, ...] = ()
    child_results: tuple[SpecialistResult, ...] = ()
    task_objective: str | None = None
    correction_mode: CorrectionMode | None = None


class SpecialistAgent(Protocol):
    name: str

    async def run(self, context: QueryContext) -> SpecialistResult: ...


class SynthesisAgent(Protocol):
    async def synthesize(
        self,
        context: QueryContext,
        evidence: tuple[AgentEvidence, ...],
        *,
        correction: str | None = None,
    ) -> SynthesisResult: ...


class WorkflowEventSink(Protocol):
    async def __call__(
        self, event_type: str, agent_name: str | None, details: dict[str, Any]
    ) -> None: ...


class ControlPlaneError(RuntimeError):
    """Raised when a workflow dependency fails and no safe result can be produced."""


class QueryPlanner:
    """Deterministic, bounded planner; authorization is never delegated to a model."""

    def create_plan(self, context: QueryContext) -> QueryPlan:
        question = context.question
        if _PORTFOLIO_ACCESS_TERMS.search(question):
            return QueryPlan(
                specialists=(PortfolioMarketAnalystAgent.name,),
                intent="portfolio_access_listing",
            )
        if _HUMAN_HANDOFF_REQUEST.search(question):
            return QueryPlan(
                specialists=(),
                intent="explicit_human_handoff",
                mandatory_escalation_reason=(
                    "The user explicitly requested human assistance."
                ),
                data_gaps=("Human assistance was requested by the user.",),
            )
        if _ADVICE_TERMS.search(question):
            return QueryPlan(
                specialists=(),
                intent="personalized_or_actionable_advice",
                mandatory_escalation_reason=(
                    "The request asks for personalized investment advice or an "
                    "action the system is not permitted to provide."
                ),
                data_gaps=("Human review is required for this request.",),
            )
        if _UNSUPPORTED_METRICS.search(question):
            return QueryPlan(
                specialists=(),
                intent="unsupported_historical_metric",
                mandatory_escalation_reason=(
                    "Required validated historical portfolio or benchmark return "
                    "series are not available in the configured dataset."
                ),
                data_gaps=(
                    "Historical return series are not available.",
                    "Benchmark-relative and volatility metrics are unsupported.",
                ),
            )
        needs_portfolio = bool(_PORTFOLIO_TERMS.search(question))
        needs_document = bool(_DOCUMENT_TERMS.search(question))
        if needs_portfolio and not needs_document and context.portfolio_id is None:
            return QueryPlan(
                specialists=(),
                intent="portfolio_analysis",
                clarification_question=(
                    "Which authorized portfolio should I analyze? Please provide "
                    "its portfolio ID."
                ),
            )

        specialists: list[str] = []
        needs_market = bool(_CURRENT_MARKET_DATA_TERMS.search(question))
        if context.portfolio_id is not None or needs_market:
            specialists.append(PortfolioMarketAnalystAgent.name)
        if needs_document or not specialists:
            specialists.append(DocumentRetrievalAgent.name)
        # The risk-policy specialist only checks structured portfolio risk
        # records. Policy-only questions without a portfolio belong to RAG.
        if context.portfolio_id is not None and _RISK_TERMS.search(question):
            specialists.append(RiskPolicyAnalystAgent.name)
        specialists = list(dict.fromkeys(specialists))[:MAX_SPECIALISTS]
        if len(specialists) > 1:
            intent = "hybrid_market_analysis" if needs_market else "hybrid_risk_policy"
        elif specialists[0] == PortfolioMarketAnalystAgent.name:
            intent = (
                "portfolio_analysis"
                if context.portfolio_id is not None
                else "market_analysis"
            )
        else:
            intent = "document_question"
        return QueryPlan(specialists=tuple(specialists), intent=intent)


class DocumentRetrievalAgent:
    name = "Document Retrieval agent"

    def __init__(
        self,
        engine: Engine,
        embedder: EmbeddingProvider,
        *,
        top_k: int = 6,
    ) -> None:
        if not 1 <= top_k <= MAX_EVIDENCE_ITEMS:
            raise ValueError(f"top_k must be between 1 and {MAX_EVIDENCE_ITEMS}")
        self.engine = engine
        self.embedder = embedder
        self.top_k = top_k

    async def run(self, context: QueryContext) -> SpecialistResult:
        retrieval_query = context.question
        if context.correction_mode == CorrectionMode.FOCUS_RETRIEVAL:
            retrieval_query = _focused_retrieval_query(context.question)
        started_at = time.perf_counter()
        try:
            vectors = await self.embedder.embed([retrieval_query])
        except EmbeddingProviderError as exc:
            logger.exception(
                "RAG query embedding failed",
                extra={"query_id": context.query_id, "agent_name": self.name},
            )
            raise ControlPlaneError("Document-query embedding failed.") from exc
        if len(vectors) != 1 or len(vectors[0]) != 1536:
            logger.error(
                "RAG query embedding was invalid",
                extra={"query_id": context.query_id, "agent_name": self.name},
            )
            raise ControlPlaneError("Document-query embedding was invalid.")
        try:
            with observation(
                name="approved-document-retrieval",
                as_type="retriever",
                input={
                    "query_length_chars": len(retrieval_query),
                    "top_k": self.top_k,
                    "content_captured": False,
                },
                metadata={
                    "query_id": context.query_id,
                    "uses_vector_search": True,
                    "uses_keyword_search": True,
                    "uses_rank_fusion": True,
                    "approved_sources_only": True,
                    "correction_mode": (
                        context.correction_mode.value
                        if context.correction_mode is not None
                        else "initial"
                    ),
                },
            ) as retrieval_trace:
                evidence = await asyncio.to_thread(
                    self._retrieve, vectors[0], retrieval_query
                )
                if retrieval_trace is not None:
                    page_numbers = sorted(
                        {
                            citation.page_number
                            for item in evidence
                            if (citation := item.citation).page_number is not None
                        }
                    )
                    retrieval_trace.update(
                        output={
                            "evidence_count": len(evidence),
                            "source_count": len(
                                {item.citation.source_id for item in evidence}
                            ),
                            "page_numbers": page_numbers,
                            "evidence_types": sorted(
                                {item.citation.evidence_type for item in evidence}
                            ),
                            "content_captured": False,
                        }
                    )
        except Exception:
            logger.exception(
                "RAG document retrieval failed",
                extra={"query_id": context.query_id, "agent_name": self.name},
            )
            raise
        logger.info(
            "RAG document retrieval completed",
            extra={
                "query_id": context.query_id,
                "agent_name": self.name,
                "evidence_count": len(evidence),
                "duration_seconds": round(time.perf_counter() - started_at, 4),
            },
        )
        return SpecialistResult(
            agent_name=self.name,
            evidence=tuple(evidence),
            data_gaps=(
                ("No relevant approved document passages were found.",)
                if not evidence
                else ()
            ),
        )

    def _retrieve(self, vector: list[float], query_text: str) -> list[AgentEvidence]:
        started_at = time.perf_counter()
        distance = document_chunks.c.embedding.cosine_distance(vector).label(
            "distance"
        )
        statement = (
            select(
                document_chunks.c.chunk_id,
                document_chunks.c.chunk_text,
                document_chunks.c.page_start,
                document_chunks.c.section_path,
                document_versions.c.document_version_id,
                document_versions.c.version_label,
                source_documents.c.source_key,
                source_documents.c.title,
                source_documents.c.source_type,
            )
            .join(
                document_versions,
                document_versions.c.document_version_id
                == document_chunks.c.document_version_id,
            )
            .join(
                source_documents,
                source_documents.c.document_id == document_versions.c.document_id,
            )
            .where(
                source_documents.c.approved.is_(True),
                source_documents.c.enabled.is_(True),
                source_documents.c.access_classification == "internal",
                document_versions.c.validation_status == "valid",
                document_chunks.c.chunk_text.is_not(None),
            )
        )
        with self.engine.connect() as connection:
            vector_rows = (
                connection.execute(
                    statement.add_columns(distance)
                    .order_by(distance)
                    .limit(self.top_k)
                )
                .mappings()
                .all()
            )
            keyword_rows = (
                connection.execute(statement.order_by(document_chunks.c.chunk_id))
                .mappings()
                .all()
            )

        evidence_by_chunk: dict[str, AgentEvidence] = {}
        for row in keyword_rows:
            item = _document_evidence(row)
            if item is not None:
                evidence_by_chunk[row["chunk_id"]] = item

        vector_ranking = [
            row["chunk_id"]
            for row in vector_rows
            if row["chunk_id"] in evidence_by_chunk
        ]
        keyword_ranking = bm25_rank(
            query_text,
            [
                (row["chunk_id"], row["chunk_text"])
                for row in keyword_rows
                if row["chunk_id"] in evidence_by_chunk
            ],
            self.top_k,
        )
        fused_ids = reciprocal_rank_fusion(
            (vector_ranking, keyword_ranking),
            top_k=self.top_k,
        )
        logger.info(
            "RAG retrieval rankings fused",
            extra={
                "agent_name": self.name,
                "vector_result_count": len(vector_ranking),
                "keyword_result_count": len(keyword_ranking),
                "fused_result_count": len(fused_ids),
                "duration_seconds": round(time.perf_counter() - started_at, 4),
            },
        )
        return [evidence_by_chunk[chunk_id] for chunk_id in fused_ids]


def _document_evidence(row: Mapping[str, Any]) -> AgentEvidence | None:
    content = str(row["chunk_text"]).strip()
    if not content:
        return None
    source_id = row["source_key"]
    page_number = row["page_start"]
    return AgentEvidence(
        evidence_id=f"{source_id}:p{page_number or 0}:{row['chunk_id']}",
        citation=Citation(
            source_id=source_id,
            source_title=row["title"],
            source_version=row["version_label"],
            evidence_type="policy_document",
            excerpt=content[:MAX_EVIDENCE_CHARS],
            page_number=page_number,
            section=row["section_path"],
        ),
        content=content[:MAX_EVIDENCE_CHARS],
    )


def _focused_retrieval_query(question: str) -> str:
    """Build a deterministic keyword-focused retry from the current question."""
    terms: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(r"[A-Za-z0-9][A-Za-z0-9_-]{1,}", question):
        term = match.group(0)
        normalized = term.casefold()
        if normalized in _RETRIEVAL_STOP_WORDS or normalized in seen:
            continue
        seen.add(normalized)
        terms.append(term)
        if len(terms) >= 12:
            break
    return " ".join(terms) or question


class PortfolioMarketAnalystAgent:
    """Read-only portfolio analysis limited to the caller's requested portfolio."""

    name = "Portfolio / Market Analyst agent"

    def __init__(self, engine: Engine, *, row_limit: int = 50) -> None:
        self.engine = engine
        self.row_limit = row_limit

    async def run(self, context: QueryContext) -> SpecialistResult:
        if _PORTFOLIO_ACCESS_TERMS.search(context.question):
            return await asyncio.to_thread(self._list_accessible, context)
        needs_market = bool(_CURRENT_MARKET_DATA_TERMS.search(context.question))
        needs_risk = bool(_RISK_TERMS.search(context.question))
        needs_decisions = bool(_DECISION_TERMS.search(context.question))
        if context.portfolio_id is None and not needs_market:
            return SpecialistResult(
                agent_name=self.name,
                evidence=(),
                data_gaps=("No authorized structured-data scope was requested.",),
            )
        try:
            evidence, requires_review = await asyncio.to_thread(
                self._analyze,
                context.portfolio_id,
                needs_market,
                needs_risk,
                needs_decisions,
            )
        except SQLAlchemyError as exc:
            raise ControlPlaneError("Structured portfolio analysis failed.") from exc
        return SpecialistResult(
            agent_name=self.name,
            evidence=tuple(evidence),
            data_gaps=(
                ("The requested authorized portfolio has no available records.",)
                if not evidence
                else ()
            ),
            requires_human_review=requires_review,
        )

    def _list_accessible(self, context: QueryContext) -> SpecialistResult:
        statement = select(
            portfolios.c.portfolio_id,
            portfolios.c.portfolio_name,
        ).order_by(portfolios.c.portfolio_id)
        if not context.all_portfolios_access:
            statement = statement.where(
                portfolios.c.portfolio_id.in_(context.authorized_portfolio_ids)
            )
        with self.engine.connect() as connection:
            rows = connection.execute(statement.limit(101)).mappings().all()
        accessible = [{"portfolio_name": row["portfolio_name"]} for row in rows[:100]]
        while True:
            excerpt = json.dumps(
            {
                "principal_roles": list(context.principal_roles),
                "all_portfolios_access": context.all_portfolios_access,
                "accessible_portfolios": accessible,
            },
                ensure_ascii=False,
                separators=(",", ":"),
            )
            if len(excerpt) <= MAX_EVIDENCE_CHARS or not accessible:
                break
            accessible.pop()
        evidence = AgentEvidence(
            evidence_id=f"portfolio_access:{context.query_id}",
            citation=Citation(
                source_id="authenticated-portfolio-scope",
                source_title="Portfolios available to your account",
                evidence_type="account_scope",
                excerpt=excerpt,
            ),
            content=excerpt,
        )
        return SpecialistResult(
            agent_name=self.name,
            evidence=(evidence,),
            data_gaps=(
                ("Only the first 100 accessible portfolios are shown.",)
                if len(rows) > len(accessible)
                else ()
            ),
        )

    def _analyze(
        self,
        portfolio_id: int | None,
        include_market_indicators: bool,
        include_risk_records: bool,
        include_decisions: bool,
    ) -> tuple[list[AgentEvidence], bool]:
        evidence: list[AgentEvidence] = []
        requires_review = False
        with self.engine.connect() as connection:
            if portfolio_id is not None:
                portfolio = connection.execute(
                    select(portfolios).where(
                        portfolios.c.portfolio_id == portfolio_id
                    )
                ).mappings().first()
                if portfolio is None:
                    return [], False
                portfolio_data = {
                    key: value.isoformat() if isinstance(value, date) else value
                    for key, value in dict(portfolio).items()
                    if key != "portfolio_id"
                }
                evidence.append(
                    _structured_evidence(
                        f"portfolios:{portfolio_id}",
                        "Portfolio record",
                        portfolio_data,
                    )
                )
                holdings = connection.execute(
                    select(portfolio_holdings)
                    .where(portfolio_holdings.c.portfolio_id == portfolio_id)
                    .order_by(portfolio_holdings.c.holding_id)
                    .limit(self.row_limit)
                ).mappings().all()
                asset_names: set[str] = set()
                for row in holdings:
                    record = dict(row)
                    asset_name = record.get("asset_name")
                    if asset_name:
                        asset_names.add(asset_name)
                    if not include_risk_records and not include_decisions:
                        evidence.append(
                            _structured_evidence(
                                f"portfolio_holdings:{record['holding_id']}",
                                "Portfolio holding",
                                record,
                            )
                        )
                risks = []
                if asset_names and include_risk_records:
                    risks = connection.execute(
                        select(asset_risk_logs)
                        .where(asset_risk_logs.c.asset_name.in_(asset_names))
                        .order_by(
                            asset_risk_logs.c.assessment_date.desc(),
                            asset_risk_logs.c.risk_id.desc(),
                        )
                        .limit(self.row_limit)
                    ).mappings().all()
                for row in risks:
                    record = dict(row)
                    requires_review = requires_review or bool(
                        record.get("escalation_flag")
                    )
                    evidence.append(
                        _structured_evidence(
                            f"asset_risk_logs:{record['risk_id']}",
                            "Asset risk assessment",
                            record,
                        )
                    )
                if include_decisions:
                    decisions = connection.execute(
                        select(investment_decisions)
                        .where(investment_decisions.c.portfolio_id == portfolio_id)
                        .order_by(
                            investment_decisions.c.decision_date.desc(),
                            investment_decisions.c.decision_id.desc(),
                        )
                        .limit(self.row_limit)
                    ).mappings().all()
                    for row in decisions:
                        record = dict(row)
                        evidence.append(
                            _structured_evidence(
                                f"investment_decisions:{record['decision_id']}",
                                "Investment decision record",
                                record,
                            )
                        )
            if include_market_indicators:
                indicators = connection.execute(
                    select(market_indicators)
                    .order_by(
                        market_indicators.c.measurement_date.desc(),
                        market_indicators.c.indicator_id.desc(),
                    )
                    .limit(self.row_limit)
                ).mappings().all()
                for row in indicators:
                    record = dict(row)
                    evidence.append(
                        _structured_evidence(
                            f"market_indicators:{record['indicator_id']}",
                            "Synthetic market indicator",
                            record,
                        )
                    )
        return evidence[:MAX_EVIDENCE_ITEMS], requires_review


class RiskPolicyAnalystAgent:
    """Checks risk records for explicit escalation flags without inventing tiers."""

    name = "Risk & Policy Analyst agent"

    def __init__(self, portfolio_agent: PortfolioMarketAnalystAgent | None = None):
        self.portfolio_agent = portfolio_agent

    async def run(self, context: QueryContext) -> SpecialistResult:
        if context.portfolio_id is None or self.portfolio_agent is None:
            return SpecialistResult(
                agent_name=self.name,
                evidence=(),
                data_gaps=("No authorized structured risk records were requested.",),
            )
        portfolio_result = next(
            (
                result
                for result in context.child_results
                if result.agent_name == PortfolioMarketAnalystAgent.name
            ),
            None,
        )
        if portfolio_result is None and not context.child_results:
            # Preserve standalone use while the supervisor normally supplies
            # already-validated child outputs to avoid repeating database work.
            portfolio_result = await self.portfolio_agent.run(context)
        if portfolio_result is None:
            return SpecialistResult(
                agent_name=self.name,
                evidence=(),
                data_gaps=("The portfolio subtask did not return validated results.",),
                delegated_agents=(PortfolioMarketAnalystAgent.name,),
            )
        risks = tuple(
            evidence
            for evidence in portfolio_result.evidence
            if evidence.citation.record_reference
            and evidence.citation.record_reference.startswith("asset_risk_logs:")
        )
        flagged = tuple(
            evidence
            for evidence in risks
            if '"escalation_flag": true' in evidence.content.lower()
        )
        warnings = (
            ("One or more risk records have an explicit escalation flag.",)
            if flagged
            else ()
        )
        return SpecialistResult(
            agent_name=self.name,
            evidence=flagged,
            data_gaps=portfolio_result.data_gaps,
            warnings=warnings,
            requires_human_review=bool(flagged),
            delegated_agents=tuple(
                result.agent_name for result in context.child_results
            ) or (PortfolioMarketAnalystAgent.name,),
        )


class AzureSynthesisAgent:
    """Evidence-constrained response synthesis; it cannot select new data sources."""

    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str,
        api_version: str,
        deployment: str,
        evaluator_deployment: str | None = None,
        timeout_seconds: float = MAX_SYNTHESIS_SECONDS,
    ) -> None:
        if not all((endpoint, api_key, api_version, deployment)):
            raise ValueError("Azure OpenAI synthesis settings are required")
        self.deployment = deployment
        self.evaluator_deployment = evaluator_deployment or deployment
        chat_model_options: dict[str, Any] = {
            "azure_endpoint": endpoint,
            "api_key": api_key,
            "api_version": api_version,
            "azure_deployment": deployment,
            "timeout": timeout_seconds,
            "max_retries": 1,
        }
        chat_model_options["model"] = deployment
        deployment_name = deployment.casefold()
        if not deployment_name.startswith("gpt-5") or deployment_name.startswith(
            "gpt-5-chat"
        ):
            chat_model_options["temperature"] = 0
        self._client = AzureChatOpenAI(**chat_model_options)
        self._evaluator_client = self._client
        if self.evaluator_deployment != deployment:
            evaluator_options = {
                **chat_model_options,
                "azure_deployment": self.evaluator_deployment,
                "model": self.evaluator_deployment,
                "timeout": MAX_RESULT_EVALUATION_SECONDS,
            }
            evaluator_model_name = self.evaluator_deployment.casefold()
            if evaluator_model_name.startswith("gpt-5") and not (
                evaluator_model_name.startswith("gpt-5-chat")
            ):
                evaluator_options.pop("temperature", None)
            self._evaluator_client = AzureChatOpenAI(**evaluator_options)

    async def synthesize(
        self,
        context: QueryContext,
        evidence: tuple[AgentEvidence, ...],
        *,
        correction: str | None = None,
    ) -> SynthesisResult:
        evidence_payload = [
            {
                "citation_id": item.evidence_id,
                "citation": item.citation.model_dump(mode="json"),
                "content": item.content,
            }
            for item in evidence
        ]
        prompt = {
            "question": context.question,
            "recent_user_questions": list(context.conversation_context),
            "evidence": evidence_payload,
            "correction": correction,
        }
        try:
            with observation(
                name="evidence-constrained-synthesis",
                as_type="generation",
                input={"evidence_count": len(evidence), "content_captured": False},
                metadata={"query_id": context.query_id},
                model=self.deployment,
            ) as span:
                response = await asyncio.wait_for(
                    self._client.bind(response_format={"type": "json_object"}).ainvoke(
                        _SYNTHESIS_PROMPT.format_messages(
                            request_payload=json.dumps(prompt, default=str)
                        )
                    ),
                    timeout=MAX_SYNTHESIS_SECONDS,
                )
                usage = getattr(response, "usage_metadata", None) or {}
                if span is not None:
                    usage_details = {
                        key: usage[source]
                        for key, source in (
                            ("input", "input_tokens"),
                            ("output", "output_tokens"),
                            ("total", "total_tokens"),
                        )
                        if isinstance(usage.get(source), int)
                    }
                    updates: dict[str, Any] = {
                        "output": {"content_captured": False}
                    }
                    if usage_details:
                        updates["usage_details"] = usage_details
                    span.update(**updates)
        except (APIConnectionError, APITimeoutError, APIError, TimeoutError) as exc:
            logger.exception(
                "Response synthesis provider failed",
                extra={
                    "query_id": context.query_id,
                    "error_type": type(exc).__name__,
                    "provider_status_code": getattr(exc, "status_code", None),
                    "provider_error_code": getattr(exc, "code", None),
                    "provider_error_param": getattr(exc, "param", None),
                },
            )
            raise ControlPlaneError("Response synthesis provider failed.") from exc
        content = response.content
        if not isinstance(content, str) or not content.strip():
            raise ControlPlaneError("Response synthesis returned an empty payload.")
        try:
            result = SynthesisResult.model_validate_json(content)
        except (ValidationError, ValueError) as exc:
            raise ControlPlaneError(
                "Response synthesis returned an invalid structured result."
            ) from exc
        allowed = {item.evidence_id for item in evidence}
        if not set(result.citation_ids).issubset(allowed):
            raise ControlPlaneError(
                "Response synthesis referenced evidence outside the supplied set."
            )
        return result

    async def evaluate_result(
        self,
        query_id: str,
        question: str,
        result: OrchestrationResult,
    ) -> QueryResultQualityScores:
        """Judge a sanitized query result against its cited evidence."""
        answer = result.answer or result.clarification_question
        citations = [
            {
                "source_title": citation.source_title,
                "evidence_type": citation.evidence_type,
                "excerpt": citation.excerpt,
            }
            for citation in result.citations[:MAX_EVIDENCE_ITEMS]
        ]
        escalation_reason = None
        if result.escalation is not None:
            answer = answer or result.escalation.requested_review
            escalation_reason = result.escalation.reason
            if not citations:
                citations = [
                    {
                        "source_title": item.source_title,
                        "excerpt": item.excerpt,
                    }
                    for item in result.escalation.evidence[:MAX_EVIDENCE_ITEMS]
                ]
        if not answer:
            raise ValueError("A query result needs text before it can be evaluated.")

        payload = {
            "question": question,
            "status": result.status.value,
            "answer": answer,
            "escalation_reason": escalation_reason,
            "limitations": list(result.limitations),
            "citations": citations,
        }
        try:
            with observation(
                name="query-result-quality-evaluation",
                as_type="generation",
                input={"citation_count": len(citations), "content_captured": False},
                metadata={
                    "query_id": query_id,
                    "evaluator_prompt": _QUERY_RESULT_EVALUATOR_PROMPT_DEFINITION[
                        "name"
                    ],
                    "evaluator_prompt_version": _QUERY_RESULT_EVALUATOR_PROMPT_DEFINITION[
                        "version"
                    ],
                },
                model=self.evaluator_deployment,
            ) as span:
                response = await asyncio.wait_for(
                    self._evaluator_client.bind(
                        response_format={"type": "json_object"}
                    ).ainvoke(
                        _QUERY_RESULT_EVALUATOR_PROMPT.format_messages(
                            evaluation_payload=json.dumps(payload, default=str)
                        )
                    ),
                    timeout=MAX_RESULT_EVALUATION_SECONDS,
                )
        except (APIConnectionError, APITimeoutError, APIError, TimeoutError) as exc:
            logger.warning(
                "Query result quality evaluation provider failed",
                extra={
                    "query_id": query_id,
                    "error_type": type(exc).__name__,
                    "provider_status_code": getattr(exc, "status_code", None),
                },
            )
            raise ControlPlaneError("Query result quality evaluation failed.") from exc

        content = response.content
        if not isinstance(content, str) or not content.strip():
            raise ControlPlaneError(
                "Query result quality evaluation returned an empty payload."
            )
        try:
            scores = QueryResultQualityScores.model_validate_json(content)
        except (ValidationError, ValueError) as exc:
            raise ControlPlaneError(
                "Query result quality evaluation returned invalid scores."
            ) from exc
        if span is not None:
            span.update(output={"scores": scores.model_dump()})
        return scores

    async def aclose(self) -> None:
        await self._client.root_async_client.close()
        if self._evaluator_client is not self._client:
            await self._evaluator_client.root_async_client.close()


class SupervisorAgent:
    """Owns plan, bounded parallel delegation, evidence checks, and final outcome."""

    name = "Supervisor agent"

    def __init__(
        self,
        agents: tuple[SpecialistAgent, ...],
        synthesizer: SynthesisAgent,
        *,
        planner: QueryPlanner | None = None,
        event_sink: WorkflowEventSink | None = None,
        agent_timeout_seconds: float = MAX_AGENT_SECONDS,
        workflow_timeout_seconds: float = MAX_WORKFLOW_SECONDS,
    ) -> None:
        if not 0 < agent_timeout_seconds <= MAX_AGENT_SECONDS:
            raise ValueError("Agent timeout must be within the bounded limit")
        if not 0 < workflow_timeout_seconds <= MAX_WORKFLOW_SECONDS:
            raise ValueError("Workflow timeout must be within the bounded limit")
        self.agents = {agent.name: agent for agent in agents}
        self.synthesizer = synthesizer
        self.planner = planner or QueryPlanner()
        self.event_sink = event_sink
        self.agent_timeout_seconds = agent_timeout_seconds
        self.workflow_timeout_seconds = workflow_timeout_seconds
        from agents.workflow_graph import compile_workflow

        self._graph = compile_workflow(self)

    async def run(self, context: QueryContext) -> OrchestrationResult:
        from agents.workflow_graph import run_workflow

        return await run_workflow(self, context)

    def _workflow_task(
        self,
        index: int,
        agent_name: str,
        context: QueryContext,
        *,
        child_agent_names: tuple[str, ...] = (),
    ) -> WorkflowTask:
        child_agents = (
            child_agent_names
            if agent_name == RiskPolicyAnalystAgent.name
            else ()
        )
        objectives = {
            DocumentRetrievalAgent.name: (
                "Retrieve approved, relevant document evidence."
            ),
            PortfolioMarketAnalystAgent.name: (
                "Analyze only the explicitly authorized structured-data scope."
            ),
            RiskPolicyAnalystAgent.name: (
                "Coordinate risk checks and flag records requiring human review."
            ),
        }
        return WorkflowTask(
            task_id=f"task-{index}",
            manager_agent=self.name,
            agent_name=agent_name,
            objective=objectives.get(
                agent_name, "Complete the assigned bounded analysis."
            ),
            child_agents=child_agents,
        )

    async def _run_specialist(
        self, agent: SpecialistAgent, context: QueryContext
    ) -> SpecialistResult:
        await self._emit("agent_started", agent.name, {})
        try:
            with observation(
                name=f"specialist:{agent.name}",
                as_type="agent",
                input={"content_captured": False},
                metadata={
                    "query_id": context.query_id,
                    "portfolio_id": context.portfolio_id,
                    "has_task_objective": context.task_objective is not None,
                },
            ) as span:
                result = await asyncio.wait_for(
                    agent.run(context), timeout=self.agent_timeout_seconds
                )
            if result.agent_name != agent.name:
                raise ControlPlaneError("Specialist identity did not match its contract.")
            evidence_ids: set[str] = set()
            for item in result.evidence:
                if item.evidence_id in evidence_ids:
                    raise ControlPlaneError("Specialist returned duplicate evidence IDs.")
                evidence_ids.add(item.evidence_id)
                if not all(
                    value.strip()
                    for value in (
                        item.citation.source_id,
                        item.citation.source_title,
                        item.citation.evidence_type,
                        item.content,
                    )
                ):
                    raise ControlPlaneError("Specialist evidence provenance was incomplete.")
            await self._emit(
                "agent_completed",
                agent.name,
                {
                    "evidence_count": len(result.evidence),
                    "data_gap_count": len(result.data_gaps),
                },
            )
            if span is not None:
                span.update(
                    output={
                        "evidence_count": len(result.evidence),
                        "data_gap_count": len(result.data_gaps),
                        "warning_count": len(result.warnings),
                        "requires_human_review": result.requires_human_review,
                    }
                )
            return result
        except TimeoutError as exc:
            await self._emit("agent_timed_out", agent.name, {})
            raise ControlPlaneError(f"{agent.name} timed out.") from exc
        except Exception as exc:
            await self._emit("agent_failed", agent.name, {})
            cause_types: list[str] = []
            cause: BaseException | None = exc.__cause__ or exc.__context__
            while cause is not None and len(cause_types) < 5:
                cause_types.append(type(cause).__name__)
                cause = cause.__cause__ or cause.__context__
            logger.error(
                "Specialist execution raised an exception",
                extra={
                    "query_id": context.query_id,
                    "agent_name": agent.name,
                    "error_type": type(exc).__name__,
                    "cause_types": cause_types,
                },
            )
            raise ControlPlaneError(f"{agent.name} failed.") from exc

    async def _synthesize(
        self,
        context: QueryContext,
        evidence: tuple[AgentEvidence, ...],
        *,
        allow_correction: bool = True,
        workflow_state: SynthesisCorrectionState | None = None,
    ) -> SynthesisResult:
        try:
            result = await asyncio.wait_for(
                self.synthesizer.synthesize(context, evidence),
                timeout=MAX_SYNTHESIS_SECONDS,
            )
            allowed = {item.evidence_id for item in evidence}
            if (
                not result.answer.strip()
                or not result.citation_ids
                or not set(result.citation_ids).issubset(allowed)
            ):
                raise ControlPlaneError("Synthesis output failed evidence validation.")
            return result
        except (ControlPlaneError, TimeoutError) as first_error:
            if not allow_correction:
                raise ControlPlaneError(
                    "Synthesis failed after the workflow correction budget was used."
                ) from first_error
            first_error = (
                first_error
                if isinstance(first_error, ControlPlaneError)
                else ControlPlaneError("Response synthesis timed out.")
            )
            if workflow_state is not None:
                workflow_state.correction_used = True
                workflow_state.correction_target = "response synthesis"
            await self._emit(
                "bounded_reflection",
                self.name,
                {
                    "attempt": 1,
                    "reason": "Synthesis failed response or citation validation.",
                },
            )
            try:
                result = await asyncio.wait_for(
                    self.synthesizer.synthesize(
                        context, evidence, correction=str(first_error)
                    ),
                    timeout=MAX_SYNTHESIS_SECONDS,
                )
            except (ControlPlaneError, TimeoutError) as second_error:
                raise ControlPlaneError(
                    "Synthesis remained invalid after one correction attempt."
                ) from second_error
            allowed = {item.evidence_id for item in evidence}
            if (
                not result.answer.strip()
                or not result.citation_ids
                or not set(result.citation_ids).issubset(allowed)
            ):
                raise ControlPlaneError(
                    "Synthesis remained invalid after one correction attempt."
                )
            return result

    async def _emit(
        self, event_type: str, agent_name: str | None, details: dict[str, Any]
    ) -> None:
        trace_fields = {
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
                "status",
                "citation_count",
                "route",
                "specialist_count",
            }
        }
        with observation(
            name=f"workflow-{event_type}",
            as_type="span",
            input={"content_captured": False},
            metadata={
                "event_type": event_type,
                "agent_name": agent_name or self.name,
                **(
                    {"query_id": details["query_id"]}
                    if details.get("query_id") is not None
                    else {}
                ),
            },
        ) as trace:
            if trace is not None:
                trace.update(
                    output={"event_type": event_type, **trace_fields},
                    metadata={"event_type": event_type},
                )
        logger.info(
            "Multi-agent workflow event",
            extra={
                "workflow_event": event_type,
                "agent_name": agent_name or self.name,
                "evidence_count": details.get("evidence_count"),
                "data_gap_count": details.get("data_gap_count"),
                "intent": details.get("intent"),
                "specialists": details.get("specialists"),
                **{
                    key: value
                    for key, value in trace_fields.items()
                    if key in {
                        "from",
                        "to",
                        "task_id",
                        "attempt",
                        "accepted",
                        "correction_mode",
                        "scope_unchanged",
                        "route",
                    }
                },
            },
        )
        if self.event_sink is not None:
            await self.event_sink(event_type, agent_name, details)

    @staticmethod
    def _escalate(
        reason: str,
        *,
        evidence: tuple[AgentEvidence, ...] = (),
        attempted: list[str] | tuple[str, ...] = (),
        data_gaps: list[str] | tuple[str, ...] = (),
    ) -> OrchestrationResult:
        handoff = tuple(
            HandoffEvidence(
                source_id=item.citation.source_id,
                source_title=item.citation.source_title,
                source_version=item.citation.source_version,
                excerpt=item.citation.excerpt,
                page_number=item.citation.page_number,
                record_reference=item.citation.record_reference,
            )
            for item in evidence
        )
        packet = EscalationPacket(
            reason=reason,
            evidence=handoff,
            attempted_steps=tuple(attempted),
            data_gaps=tuple(data_gaps),
            requested_review=(
                "Review the evidence, data limitations, and requested analysis; "
                "provide human guidance without authorizing a trade or portfolio change."
            ),
        )
        return OrchestrationResult(
            status=QueryStatus.ESCALATED,
            limitations=("The result requires human review.",),
            escalation=packet,
        )


def _structured_evidence(
    record_reference: str,
    title: str,
    record: dict[str, Any],
) -> AgentEvidence:
    safe_record = {
        key: value.isoformat() if isinstance(value, date) else value
        for key, value in record.items()
        if key not in {"portfolio_id"}
    }
    excerpt = json.dumps(safe_record, default=str, sort_keys=True)
    return AgentEvidence(
        evidence_id=record_reference,
        citation=Citation(
            source_id="friis-finance-dataset",
            source_title=title,
            evidence_type="structured_data",
            excerpt=excerpt[:MAX_EVIDENCE_CHARS],
            record_reference=record_reference,
        ),
        content=excerpt[:MAX_EVIDENCE_CHARS],
    )
