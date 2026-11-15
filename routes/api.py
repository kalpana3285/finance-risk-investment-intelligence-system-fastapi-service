"""HTTP handlers for the documented FRIIS API."""

import asyncio
import logging
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path as FilePath
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)

from schemas import (
    AgentAskResponse,
    EscalationDetailResponse,
    EscalationListQuery,
    EscalationListResponse,
    EscalationStatus,
    EscalationUpdateRequest,
    EscalationUpdateResponse,
    ErrorResponse,
    FileIngestionResponse,
    HealthResponse,
    HealthStatus,
    PortfolioDetailResponse,
    PortfolioListQuery,
    PortfolioListResponse,
    QueryRequest,
    QueryResponse,
    QuerySubmissionResponse,
)
from security.auth import Principal, Role, require_any_role
from services.api_service import (
    APIService,
    EscalationConflictError,
    InvalidCursorError,
    InvalidQueryError,
)
from services.file_ingestion import (
    DOCUMENT_CHUNKS_TABLE,
    process_and_store_file,
)
from services.langfuse_tracing import observation

router = APIRouter()
logger = logging.getLogger(__name__)
MAX_UPLOAD_SIZE = 10 * 1024 * 1024
ALLOWED_UPLOAD_EXTENSIONS = {".pdf", ".txt", ".md", ".markdown", ".html", ".htm"}

AnalystPrincipal = Annotated[
    Principal,
    Depends(
        require_any_role(
            Role.USER,
            Role.ADMIN,
            Role.ANALYST, Role.RISK_MANAGER, Role.COMPLIANCE_REVIEWER
        )
    ),
]
FinanceAgentPrincipal = Annotated[
    Principal,
    Depends(
        require_any_role(
            Role.ADMIN,
            Role.ANALYST,
            Role.RISK_MANAGER,
            Role.COMPLIANCE_REVIEWER,
        )
    ),
]
ReviewerPrincipal = Annotated[
    Principal,
    Depends(
        require_any_role(
            Role.ADMIN, Role.RISK_MANAGER, Role.COMPLIANCE_REVIEWER
        )
    ),
]
OperatorPrincipal = Annotated[
    Principal, Depends(require_any_role(Role.ADMIN, Role.OPERATOR))
]


def _get_service(request: Request) -> APIService:
    service: APIService | None = getattr(request.app.state, "api_service", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API service is not configured.",
        )
    return service


@router.get(
    "/api/v1/agent/ask",
    tags=["Finance agent"],
    summary="Ask the tool-enabled finance agent",
    description=(
        "Runs a finance-agent query for principals with an explicit all-portfolio "
        "access grant. This operation is read-only."
    ),
    response_model=AgentAskResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
async def ask_tool_enabled_agent(
    query: Annotated[str, Query(min_length=1, max_length=2000)],
    principal: FinanceAgentPrincipal,
    request: Request,
) -> AgentAskResponse:
    """Ask the finance agent to answer a question using its configured tools."""
    # The agent's tools are not request-scoped. Require an explicit global
    # portfolio grant before allowing tool calls through this endpoint.
    if not principal.all_portfolios_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The caller is not authorized for all-portfolio agent access.",
        )
    agent = getattr(request.app.state, "finance_agent", None)
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The tool-enabled finance agent is not configured.",
        )
    try:
        with observation(
            name="friis-tool-enabled-finance-agent",
            as_type="agent",
            input={"content_captured": False},
            metadata={"principal_roles": list(principal.roles)},
        ) as trace:
            response = agent.invoke(
                {"messages": [{"role": "user", "content": query}]}
            )
            if trace is not None:
                messages = response.get("messages", []) if isinstance(response, dict) else []
                trace.update(
                    output={
                        "status": "completed",
                        "message_count": len(messages),
                        "content_captured": False,
                    }
                )
    except Exception as exc:  # pragma: no cover - infrastructure error handling.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"The finance agent could not answer the request: {exc}",
        ) from exc
    messages = response.get("messages", []) if isinstance(response, dict) else []
    final_answer = messages[-1].content if messages else "No response generated."
    return AgentAskResponse(query=query, response=final_answer)


def _ensure_portfolio_access(principal: Principal, portfolio_id: int) -> None:
    if (
        not principal.all_portfolios_access
        and portfolio_id not in principal.portfolio_ids
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The caller is not authorized to access this portfolio.",
        )


@router.post(
    "/api/v1/queries",
    response_model=QuerySubmissionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Research"],
    summary="Submit a research query",
    description=(
        "Queues a research request. The optional portfolio ID is checked against "
        "the caller's access grants. Poll the returned query ID with "
        "GET /api/v1/queries/{query_id}."
    ),
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
async def submit_query(
    body: QueryRequest,
    principal: AnalystPrincipal,
    service: Annotated[APIService, Depends(_get_service)],
) -> QuerySubmissionResponse:
    """Queue a question for the research workflow and return its query ID."""
    if body.portfolio_id is not None:
        _ensure_portfolio_access(principal, body.portfolio_id)
    try:
        return await service.submit_query(principal, body)
    except InvalidQueryError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc


@router.delete(
    "/api/v1/sessions/{session_id}/memory",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Research"],
    summary="Clear session memory",
    description="Clears conversational memory associated with this session for the authenticated principal.",
    responses={
        401: {"model": ErrorResponse},
        "204": {"description": "Session memory cleared."},
    },
)
async def reset_session_memory(
    session_id: Annotated[str, Path(min_length=1, max_length=128)],
    principal: AnalystPrincipal,
    service: Annotated[APIService, Depends(_get_service)],
) -> Response:
    """Clear stored conversation memory for a session."""
    await service.reset_conversation_memory(principal, session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/api/v1/queries/{query_id}",
    response_model=QueryResponse,
    tags=["Research"],
    summary="Get a research query result",
    description="Returns the current query status and, when available, its answer, citations, limitations, clarification request, escalation, or failure details.",
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def get_query(
    query_id: Annotated[str, Path(min_length=1, max_length=128)],
    principal: AnalystPrincipal,
    service: Annotated[APIService, Depends(_get_service)],
) -> QueryResponse:
    """Retrieve a query's current state and any completed result."""
    result = await service.get_query(principal, query_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Query not found.",
        )
    return result


@router.get(
    "/api/v1/portfolios",
    response_model=PortfolioListResponse,
    tags=["Portfolios"],
    summary="List accessible portfolios",
    description="Returns portfolios visible to the caller, with optional risk-category filtering and cursor pagination.",
    responses={401: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def list_portfolios(
    principal: AnalystPrincipal,
    service: Annotated[APIService, Depends(_get_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(min_length=1, max_length=512)] = None,
    risk_category: Annotated[str | None, Query(min_length=1, max_length=50)] = None,
) -> PortfolioListResponse:
    """List portfolios allowed by the caller's identity scope."""
    filters = PortfolioListQuery(
        limit=limit, cursor=cursor, risk_category=risk_category
    )
    try:
        return await service.list_portfolios(principal, filters)
    except InvalidCursorError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc


@router.get(
    "/api/v1/portfolios/{portfolio_id}",
    response_model=PortfolioDetailResponse,
    tags=["Portfolios"],
    summary="Get portfolio details",
    description="Returns a single authorized portfolio with its available holdings and risk assessments.",
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def get_portfolio(
    portfolio_id: Annotated[int, Path(gt=0)],
    principal: AnalystPrincipal,
    service: Annotated[APIService, Depends(_get_service)],
) -> PortfolioDetailResponse:
    """Get a portfolio and its associated holdings and risk assessments."""
    _ensure_portfolio_access(principal, portfolio_id)
    result = await service.get_portfolio(principal, portfolio_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio not found.",
        )
    return result


@router.get(
    "/api/v1/escalations",
    response_model=EscalationListResponse,
    tags=["Human review"],
    summary="List human-review cases",
    description="Returns review cases visible to an administrator, risk manager, or compliance reviewer. Supports status filtering and cursor pagination.",
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def list_escalations(
    principal: ReviewerPrincipal,
    service: Annotated[APIService, Depends(_get_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(min_length=1, max_length=512)] = None,
    escalation_status: Annotated[
        EscalationStatus | None, Query(alias="status")
    ] = None,
) -> EscalationListResponse:
    """List review cases available to the authenticated reviewer."""
    filters = EscalationListQuery(
        limit=limit, cursor=cursor, status=escalation_status
    )
    try:
        return await service.list_escalations(principal, filters)
    except InvalidCursorError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc


@router.get(
    "/api/v1/escalations/{escalation_id}",
    response_model=EscalationDetailResponse,
    tags=["Human review"],
    summary="Get a human-review case",
    description="Returns the case question, available evidence, data gaps, requested review, and current reviewer notes and outcome.",
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def get_escalation(
    escalation_id: Annotated[str, Path(min_length=1, max_length=128)],
    principal: ReviewerPrincipal,
    service: Annotated[APIService, Depends(_get_service)],
) -> EscalationDetailResponse:
    """Retrieve review context and current resolution fields for a case."""
    result = await service.get_escalation(principal, escalation_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Escalation not found.",
        )
    return result


@router.patch(
    "/api/v1/escalations/{escalation_id}",
    response_model=EscalationUpdateResponse,
    tags=["Human review"],
    summary="Update a human-review case",
    description="Updates review status, reviewer notes, and/or outcome. Invalid state transitions may return 409 Conflict.",
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def update_escalation(
    escalation_id: Annotated[str, Path(min_length=1, max_length=128)],
    body: EscalationUpdateRequest,
    principal: ReviewerPrincipal,
    service: Annotated[APIService, Depends(_get_service)],
) -> EscalationUpdateResponse:
    """Save reviewer notes or update the case status and outcome."""
    try:
        result = await service.update_escalation(principal, escalation_id, body)
    except EscalationConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Escalation not found.",
        )
    return result


@router.post(
    "/api/v1/admin/ingestions",
    response_model=FileIngestionResponse,
    status_code=status.HTTP_200_OK,
    tags=["Knowledge operations"],
    summary="Ingest a knowledge document",
    description=(
        "Uploads a PDF, text, Markdown, or HTML document for synchronous chunking, "
        "embedding, and indexing. Maximum upload size is 10 MiB. Restricted to "
        "administrators and operators."
    ),
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
async def start_ingestion(
    _principal: OperatorPrincipal,
    request: Request,
    file: Annotated[UploadFile, File(...)],
    chunk_size: Annotated[int, Query(ge=1, le=8000)] = 1000,
    chunk_overlap: Annotated[int, Query(ge=0, le=4000)] = 100,
) -> FileIngestionResponse:
    """Validate, chunk, embed, and store an uploaded knowledge document."""
    request_started = time.perf_counter()
    del _principal
    original_filename = (file.filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    logger.info(
        "Document ingestion request received",
        extra={
            "event": "document_ingestion.received",
            "uploaded_filename": original_filename or None,
            "content_type": file.content_type,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
        },
    )
    if not original_filename:
        logger.warning(
            "Document ingestion request rejected: no filename",
            extra={"event": "document_ingestion.rejected", "reason": "empty_filename"},
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="No file was uploaded.",
        )
    suffix = FilePath(original_filename).suffix.lower()
    if suffix not in ALLOWED_UPLOAD_EXTENSIONS:
        logger.warning(
            "Document ingestion request rejected: unsupported file type",
            extra={
                "event": "document_ingestion.rejected",
                "uploaded_filename": original_filename,
                "file_extension": suffix or None,
                "reason": "unsupported_file_type",
            },
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Unsupported file type: {suffix or '(no extension)'}.",
        )

    logger.info(
        "Reading uploaded document",
        extra={
            "event": "document_ingestion.upload_read_started",
            "uploaded_filename": original_filename,
            "max_upload_size_bytes": MAX_UPLOAD_SIZE,
        },
    )
    try:
        content = await file.read(MAX_UPLOAD_SIZE + 1)
    except Exception as exc:
        logger.exception(
            "Failed to read uploaded document",
            extra={
                "event": "document_ingestion.upload_read_failed",
                "uploaded_filename": original_filename,
                "error_type": type(exc).__name__,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file could not be read.",
        ) from exc
    if not content:
        logger.warning(
            "Document ingestion request rejected: empty upload",
            extra={
                "event": "document_ingestion.rejected",
                "uploaded_filename": original_filename,
                "reason": "empty_file",
            },
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The uploaded file is empty.",
        )
    if len(content) > MAX_UPLOAD_SIZE:
        logger.warning(
            "Document ingestion request rejected: upload exceeds size limit",
            extra={
                "event": "document_ingestion.rejected",
                "uploaded_filename": original_filename,
                "upload_size_bytes": len(content),
                "max_upload_size_bytes": MAX_UPLOAD_SIZE,
                "reason": "file_too_large",
            },
        )
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Uploaded files must be no larger than {MAX_UPLOAD_SIZE} bytes.",
        )

    logger.info(
        "Document upload validated",
        extra={
            "event": "document_ingestion.validated",
            "uploaded_filename": original_filename,
            "file_extension": suffix,
            "upload_size_bytes": len(content),
            "max_upload_size_bytes": MAX_UPLOAD_SIZE,
        },
    )
    temp_path: FilePath | None = None
    try:
        logger.info(
            "Staging uploaded document for processing",
            extra={"event": "document_ingestion.staging_started"},
        )
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            temp_path = FilePath(tmp.name)
            tmp.write(content)

        logger.info(
            "Uploaded document staged; starting ingestion pipeline",
            extra={
                "event": "document_ingestion.pipeline_started",
                "uploaded_filename": original_filename,
                "upload_size_bytes": len(content),
                "file_type": suffix.lstrip("."),
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
                "storage_table": DOCUMENT_CHUNKS_TABLE,
            },
        )
        pipeline_started = time.perf_counter()
        processor = (
            getattr(request.app.state, "file_ingestion_processor", None)
            or process_and_store_file
        )
        with observation(
            name="uploaded-document-ingestion",
            as_type="chain",
            input={"file_type": suffix.lstrip("."), "content_captured": False},
            metadata={
                "file_type": suffix.lstrip("."),
                "upload_size_bytes": len(content),
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
            },
        ) as trace:
            result = await asyncio.to_thread(
                processor,
                temp_path,
                chunk_size,
                chunk_overlap,
                filename=original_filename,
            )
            if trace is not None:
                trace.update(
                    output={
                        "status": result.get("status"),
                        "total_chunks": result.get("total_chunks"),
                        "source_documents": result.get("source_documents"),
                        "content_captured": False,
                    }
                )
        response = FileIngestionResponse.model_validate(result)
        logger.info(
            "Document ingestion pipeline completed",
            extra={
                "event": "document_ingestion.completed",
                "uploaded_filename": original_filename,
                "file_type": response.file_type,
                "source_documents": response.source_documents,
                "total_chunks": response.total_chunks,
                "collection_name": response.collection_name,
                "storage_table": DOCUMENT_CHUNKS_TABLE,
                "processing_time_seconds": round(
                    time.perf_counter() - pipeline_started, 3
                ),
                "request_time_seconds": round(
                    time.perf_counter() - request_started, 3
                ),
            },
        )
        return response
    except ValueError as exc:
        logger.warning(
            "Document ingestion pipeline rejected the uploaded content",
            extra={
                "event": "document_ingestion.rejected",
                "uploaded_filename": original_filename,
                "error_type": type(exc).__name__,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        logger.exception(
            "Document ingestion pipeline is unavailable",
            extra={
                "event": "document_ingestion.unavailable",
                "uploaded_filename": original_filename,
                "error_type": type(exc).__name__,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document ingestion is not configured.",
        ) from exc
    except Exception as exc:
        logger.exception(
            "Uploaded document processing failed",
            extra={
                "event": "document_ingestion.failed",
                "uploaded_filename": original_filename,
                "error_type": type(exc).__name__,
                "storage_table": DOCUMENT_CHUNKS_TABLE,
                "request_time_seconds": round(
                    time.perf_counter() - request_started, 3
                ),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document processing failed.",
        ) from exc
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
                logger.info(
                    "Temporary upload removed",
                    extra={
                        "event": "document_ingestion.temp_file_removed",
                        "uploaded_filename": original_filename,
                    },
                )
            except OSError:
                logger.exception(
                    "Failed to clean up uploaded temporary file",
                    extra={
                        "event": "document_ingestion.cleanup_failed",
                        "uploaded_filename": original_filename,
                    },
                )

@router.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Check API health",
    description="Reports API dependency health. Returns 503 with a degraded or unavailable status when a required service is unhealthy.",
    responses={503: {"model": HealthResponse, "description": "The API is unavailable or one or more dependencies are degraded."}},
    dependencies=[],
)
async def health(request: Request, response: Response) -> HealthResponse:
    """Report the health of the API service and its dependencies."""
    service: APIService | None = getattr(request.app.state, "api_service", None)
    if service is None:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(
            status=HealthStatus.UNAVAILABLE,
            checked_at=datetime.now(UTC),
            checks={"api_service": HealthStatus.UNAVAILABLE},
        )
    checks = await service.health()
    overall_status = (
        HealthStatus.OK
        if checks and all(check == HealthStatus.OK for check in checks.values())
        else HealthStatus.DEGRADED
    )
    if overall_status != HealthStatus.OK:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(
        status=overall_status,
        checked_at=datetime.now(UTC),
        checks=checks,
    )
