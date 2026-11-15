"""Service boundary consumed by the HTTP route handlers."""

from typing import Protocol

from schemas import (
    EscalationDetailResponse,
    EscalationListQuery,
    EscalationListResponse,
    EscalationUpdateRequest,
    EscalationUpdateResponse,
    HealthStatus,
    IngestionDetailResponse,
    IngestionRequest,
    IngestionSubmissionResponse,
    PortfolioDetailResponse,
    PortfolioListQuery,
    PortfolioListResponse,
    QueryRequest,
    QueryResponse,
    QuerySubmissionResponse,
)
from security.auth import Principal


class EscalationConflictError(Exception):
    """Raised when an escalation update violates the review workflow."""


class InvalidCursorError(ValueError):
    """Raised when a pagination cursor cannot be interpreted."""


class InvalidIngestionRequest(ValueError):
    """Raised when a requested source is not eligible for ingestion."""


class InvalidQueryError(ValueError):
    """Raised when a query does not pass input guardrails."""


class APIService(Protocol):
    """Application operations; implementations must enforce principal data scope."""

    async def submit_query(
        self, principal: Principal, request: QueryRequest
    ) -> QuerySubmissionResponse: ...

    async def reset_conversation_memory(self, principal: Principal, session_id: str) -> None: ...

    async def get_query(
        self, principal: Principal, query_id: str
    ) -> QueryResponse | None: ...

    async def list_portfolios(
        self, principal: Principal, query: PortfolioListQuery
    ) -> PortfolioListResponse: ...

    async def get_portfolio(
        self, principal: Principal, portfolio_id: int
    ) -> PortfolioDetailResponse | None: ...

    async def list_escalations(
        self, principal: Principal, query: EscalationListQuery
    ) -> EscalationListResponse: ...

    async def get_escalation(
        self, principal: Principal, escalation_id: str
    ) -> EscalationDetailResponse | None: ...

    async def update_escalation(
        self,
        principal: Principal,
        escalation_id: str,
        update: EscalationUpdateRequest,
    ) -> EscalationUpdateResponse | None: ...

    async def start_ingestion(
        self, principal: Principal, request: IngestionRequest
    ) -> IngestionSubmissionResponse: ...

    async def get_ingestion(
        self, principal: Principal, ingestion_id: str
    ) -> IngestionDetailResponse | None: ...

    async def health(self) -> dict[str, HealthStatus]: ...
