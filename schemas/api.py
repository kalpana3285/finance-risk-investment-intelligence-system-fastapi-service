"""Pydantic contracts for the FRIIS HTTP API."""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ResourceId = Annotated[str, Field(min_length=1, max_length=128)]
NonEmptyText = Annotated[str, Field(min_length=1)]


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class QueryStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    NEEDS_CLARIFICATION = "needs_clarification"
    ESCALATED = "escalated"
    FAILED = "failed"


class Citation(APIModel):
    source_id: ResourceId
    source_title: NonEmptyText
    source_version: str | None = None
    evidence_type: str
    excerpt: str | None = None
    page_number: int | None = Field(default=None, ge=1)
    section: str | None = None
    record_reference: str | None = None


class QueryRequest(APIModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"question": "What are the portfolio's main concentration risks?", "portfolio_id": 42, "session_id": "session-abc123"}]})
    question: NonEmptyText = Field(max_length=4000)
    portfolio_id: int | None = Field(default=None, gt=0)
    session_id: ResourceId | None = None


class QuerySubmissionResponse(APIModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"query_id": "query-abc123", "status": "queued", "submitted_at": "2026-11-11T12:00:00Z"}]})
    query_id: ResourceId
    status: QueryStatus
    submitted_at: datetime


class QueryFailure(APIModel):
    code: NonEmptyText = Field(max_length=100)
    message: NonEmptyText = Field(max_length=1000)
    retryable: bool = False


class QueryResponse(APIModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"query_id": "query-abc123", "status": "completed", "answer": "The policy caps sector exposure at 25% for medium and high-risk portfolios.", "citations": [{"source_id": "risk-policy-v1", "source_title": "Risk Management & Exposure Policy", "source_version": "1.0", "evidence_type": "document", "excerpt": "Sector exposure must remain below 25%.", "page_number": 12, "section": "Concentration limits", "record_reference": None}], "limitations": [], "clarification_question": None, "escalation_id": None, "escalation_reason": None, "escalation_data_gaps": [], "failure": None}]})
    query_id: ResourceId
    status: QueryStatus
    answer: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    clarification_question: str | None = None
    escalation_id: ResourceId | None = None
    escalation_reason: str | None = None
    escalation_data_gaps: list[str] = Field(default_factory=list)
    failure: QueryFailure | None = None

    @model_validator(mode="after")
    def validate_terminal_result(self) -> "QueryResponse":
        if self.status == QueryStatus.COMPLETED and not self.answer:
            raise ValueError("completed queries must include an answer")
        if (
            self.status == QueryStatus.NEEDS_CLARIFICATION
            and not self.clarification_question
        ):
            raise ValueError("queries needing clarification must include a question")
        if self.status == QueryStatus.ESCALATED and not self.escalation_id:
            raise ValueError("escalated queries must include an escalation_id")
        if self.status == QueryStatus.FAILED and not self.failure:
            raise ValueError("failed queries must include failure details")
        return self


class PageQuery(APIModel):
    limit: int = Field(default=50, ge=1, le=100)
    cursor: str | None = Field(default=None, min_length=1, max_length=512)


class PortfolioListQuery(PageQuery):
    risk_category: str | None = Field(default=None, min_length=1, max_length=50)


class PortfolioSummary(APIModel):
    portfolio_id: int = Field(gt=0)
    portfolio_name: NonEmptyText = Field(max_length=150)
    portfolio_manager: str | None = Field(default=None, max_length=150)
    risk_category: str | None = Field(default=None, max_length=50)
    total_value: Decimal | None = Field(default=None, ge=0)
    benchmark_index: str | None = Field(default=None, max_length=100)


class PortfolioHolding(APIModel):
    holding_id: int = Field(gt=0)
    asset_name: str | None = Field(default=None, max_length=150)
    asset_type: str | None = Field(default=None, max_length=100)
    sector: str | None = Field(default=None, max_length=100)
    allocation_percentage: Decimal | None = Field(default=None, ge=0, le=100)
    market_value: Decimal | None = Field(default=None, ge=0)
    last_updated: date | None = None


class AssetRiskAssessment(APIModel):
    risk_id: int = Field(gt=0)
    asset_name: str | None = Field(default=None, max_length=150)
    risk_type: str | None = Field(default=None, max_length=100)
    risk_score: int | None = Field(default=None, ge=0, le=100)
    risk_level: str | None = Field(default=None, max_length=50)
    risk_description: str | None = None
    assessment_date: date | None = None
    escalation_flag: bool = False


class PortfolioListResponse(APIModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"items": [{"portfolio_id": 42, "portfolio_name": "Global Growth Portfolio", "portfolio_manager": "Ravi Patel", "risk_category": "Medium", "total_value": "1250000.00", "benchmark_index": "NASDAQ 100"}], "next_cursor": None}]})
    items: list[PortfolioSummary]
    next_cursor: str | None = None


class PortfolioDetailResponse(PortfolioSummary):
    model_config = ConfigDict(json_schema_extra={"examples": [{"portfolio_id": 42, "portfolio_name": "Global Growth Portfolio", "portfolio_manager": "Ravi Patel", "risk_category": "Medium", "total_value": "1250000.00", "benchmark_index": "NASDAQ 100", "holdings": [], "risk_assessments": []}]})
    holdings: list[PortfolioHolding] = Field(default_factory=list)
    risk_assessments: list[AssetRiskAssessment] = Field(default_factory=list)


class EscalationStatus(StrEnum):
    OPEN = "open"
    IN_REVIEW = "in_review"
    RESOLVED = "resolved"
    CLOSED = "closed"


class ReviewOutcome(StrEnum):
    GUIDANCE_PROVIDED = "guidance_provided"
    MORE_INFORMATION_REQUESTED = "more_information_requested"
    NO_FURTHER_ACTION = "no_further_action"


class EscalationListQuery(PageQuery):
    status: EscalationStatus | None = None


class EscalationSummary(APIModel):
    escalation_id: ResourceId
    query_id: ResourceId
    status: EscalationStatus
    reason: NonEmptyText
    created_at: datetime


class EscalationListResponse(APIModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"items": [{"escalation_id": "review-abc123", "query_id": "query-abc123", "status": "open", "reason": "Evidence was insufficient to answer confidently.", "created_at": "2026-11-11T12:00:00Z"}], "next_cursor": None}]})
    items: list[EscalationSummary]
    next_cursor: str | None = None


class HandoffEvidence(APIModel):
    source_id: ResourceId
    source_title: NonEmptyText
    source_version: str | None = None
    excerpt: str | None = None
    page_number: int | None = Field(default=None, ge=1)
    record_reference: str | None = None


class EscalationDetailResponse(EscalationSummary):
    model_config = ConfigDict(json_schema_extra={"examples": [{"escalation_id": "review-abc123", "query_id": "query-abc123", "status": "open", "reason": "Evidence was insufficient to answer confidently.", "created_at": "2026-11-11T12:00:00Z", "question": "What are the concentration limits?", "evidence": [], "attempted_steps": ["document_retrieval"], "data_gaps": ["No relevant approved passages found."], "requested_review": "Review evidence and data gaps.", "session_id": None, "answer": None, "citations": [], "limitations": [], "updated_at": "2026-11-11T12:00:00Z", "reviewer_notes": None, "outcome": None}]})
    question: NonEmptyText
    evidence: list[HandoffEvidence] = Field(default_factory=list)
    attempted_steps: list[str] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)
    requested_review: NonEmptyText
    session_id: ResourceId | None = None
    answer: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    updated_at: datetime
    reviewer_notes: str | None = None
    outcome: ReviewOutcome | None = None


class EscalationUpdateRequest(APIModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"status": "resolved", "outcome": "guidance_provided", "reviewer_notes": "Reviewed the approved policy evidence and provided guidance."}]})
    status: EscalationStatus | None = None
    outcome: ReviewOutcome | None = None
    reviewer_notes: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def require_update(self) -> "EscalationUpdateRequest":
        if all(
            value is None
            for value in (self.status, self.outcome, self.reviewer_notes)
        ):
            raise ValueError("at least one escalation field must be provided")
        return self


class EscalationUpdateResponse(EscalationDetailResponse):
    pass


class IngestionSourceType(StrEnum):
    DOCUMENTS = "documents"
    STRUCTURED_DATA = "structured_data"


class IngestionStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"


class IngestionRequest(APIModel):
    source_type: IngestionSourceType
    source_ids: list[ResourceId] = Field(min_length=1, max_length=100)


class IngestionSubmissionResponse(APIModel):
    ingestion_id: ResourceId
    status: IngestionStatus
    submitted_at: datetime


class FileIngestionResponse(APIModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"status": "success", "ingestion_id": "b16a4d16-0b3c-4587-8f02-d893b816d57a", "filename": "risk-policy.pdf", "file_type": "pdf", "total_chunks": 31, "average_chunk_length": 842.5, "min_chunk_length": 210, "max_chunk_length": 1200, "table_nodes": 0, "image_nodes": 0, "processing_time_seconds": 4.2, "collection_name": "document_chunks", "chunk_ids": ["chunk-001"], "source_documents": 1}]})
    status: Literal["success"]
    ingestion_id: ResourceId
    filename: str = Field(min_length=1, max_length=255)
    file_type: str
    total_chunks: int = Field(ge=1)
    average_chunk_length: float = Field(ge=0)
    min_chunk_length: int = Field(ge=0)
    max_chunk_length: int
    table_nodes: int = Field(default=0, ge=0)
    image_nodes: int = Field(default=0, ge=0)
    processing_time_seconds: float = Field(ge=0)
    collection_name: ResourceId
    chunk_ids: list[ResourceId] = Field(min_length=1)
    source_documents: int = Field(ge=0)


class IngestionSourceResult(APIModel):
    source_id: ResourceId
    status: IngestionStatus
    version: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class IngestionDetailResponse(APIModel):
    ingestion_id: ResourceId
    source_type: IngestionSourceType
    status: IngestionStatus
    submitted_at: datetime
    completed_at: datetime | None = None
    validation_errors: list[str] = Field(default_factory=list)
    processed_sources: list[IngestionSourceResult] = Field(default_factory=list)
    indexing_status: IngestionStatus | None = None


class HealthStatus(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class HealthResponse(APIModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"status": "ok", "checked_at": "2026-11-11T12:00:00Z", "checks": {"database": "ok", "query_worker": "ok"}}]})
    status: HealthStatus
    checked_at: datetime
    checks: dict[str, HealthStatus] = Field(default_factory=dict)


class ErrorResponse(APIModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"code": "not_found", "message": "The requested resource was not found.", "request_id": None}]})
    code: NonEmptyText = Field(max_length=100)
    message: NonEmptyText = Field(max_length=1000)
    request_id: ResourceId | None = None


class AgentAskResponse(APIModel):
    """Answer returned by the tool-enabled finance agent."""

    model_config = ConfigDict(json_schema_extra={"examples": [{"query": "Summarize current portfolio risk.", "response": "The portfolio's largest exposure is in equities."}]})

    query: NonEmptyText
    response: NonEmptyText
