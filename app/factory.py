"""FastAPI application factory."""

import asyncio
import logging
import time
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from functools import partial

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from agents.control_plane import (
    AzureSynthesisAgent,
    DocumentRetrievalAgent,
    PortfolioMarketAnalystAgent,
    RiskPolicyAnalystAgent,
    SupervisorAgent,
    WorkflowEventSink,
)
from agents.tool_enabled_agent import create_finance_tool_agent
from config.log_config import setup_logging
from config.runtime import RuntimeSettings
from routes.api import router
from schemas import ErrorResponse
from security.auth import Auth0Authenticator, Authenticator
from services.api_service import APIService
from services.database import create_schema
from services.database_api_service import DatabaseAPIService
from services.document_ingestion import (
    DocumentIngestionWorker,
    register_project_pdf_sources,
)
from services.embeddings import AzureOpenAIEmbedder
from services.file_ingestion import process_and_store_file
from services.guardrails import GuardrailsValidator
from services.langfuse_tracing import (
    flush as flush_langfuse,
)
from services.langfuse_tracing import (
    observation,
)
from services.query_worker import QueryWorker

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

def create_app(
    api_service: APIService | None = None,
    authenticator: Authenticator | None = None,
    ingestion_worker: DocumentIngestionWorker | None = None,
    query_worker: QueryWorker | None = None,
    source_registration: Callable[[], list[str]] | None = None,
    embedding_client: AzureOpenAIEmbedder | None = None,
    synthesis_client: AzureSynthesisAgent | None = None,
    finance_agent: object | None = None,
    file_ingestion_processor: Callable[..., dict[str, object]] | None = None,
    cors_allowed_origins: tuple[str, ...] = (),
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
        workers = [
            worker for worker in (ingestion_worker, query_worker) if worker is not None
        ]
        worker_tasks: list[asyncio.Task[None]] = []
        try:
            if source_registration is not None:
                await asyncio.to_thread(source_registration)
            worker_tasks = [
                asyncio.create_task(worker.run_forever()) for worker in workers
            ]
            yield
        finally:
            for worker in workers:
                worker.stop()
            if worker_tasks:
                task_results = await asyncio.gather(
                    *worker_tasks, return_exceptions=True
                )
                for result in task_results:
                    if isinstance(result, BaseException) and not isinstance(
                        result, asyncio.CancelledError
                    ):
                        logger.error(
                            "Background worker stopped with an error",
                            extra={"error_type": type(result).__name__},
                        )
            service_close = getattr(api_service, "aclose", None)
            if callable(service_close):
                await service_close()
            authenticator_close = getattr(authenticator, "aclose", None)
            if callable(authenticator_close):
                await authenticator_close()
            if embedding_client is not None:
                await embedding_client.aclose()
            if synthesis_client is not None:
                await synthesis_client.aclose()
            flush_langfuse()

    app = FastAPI(
        title="FRIIS — Finance Risk & Investment Intelligence System API",
        summary="Evidence-grounded portfolio and financial risk research API.",
        description=(
            "REST API for submitting investment research questions, retrieving "
            "authorized portfolio data, reviewing escalated cases, and ingesting "
            "knowledge documents. Query submission is asynchronous: use the returned "
            "query ID to poll for a result. Protected routes require a bearer token "
            "with the role and portfolio grants required by each operation. Answers "
            "and citations depend on available source data; the API does not execute "
            "trades or change portfolio allocations."
        ),
        version="1.0.0",
        openapi_tags=[
            {
                "name": "Research",
                "description": "Submit questions and retrieve asynchronous research results.",
            },
            {
                "name": "Portfolios",
                "description": "Read portfolio summaries, holdings, and risk assessments within the caller's access scope.",
            },
            {
                "name": "Human review",
                "description": "Review and update cases escalated for authorized human guidance.",
            },
            {
                "name": "Knowledge operations",
                "description": "Ingest documents into the searchable knowledge collection.",
            },
            {
                "name": "Finance agent",
                "description": "Run the tool-enabled finance agent for principals granted all-portfolio access.",
            },
            {
                "name": "Health",
                "description": "Check API service and dependency health.",
            },
        ],
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(cors_allowed_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.api_service = api_service
    app.state.authenticator = authenticator
    app.state.ingestion_worker = ingestion_worker
    app.state.query_worker = query_worker
    app.state.finance_agent = finance_agent
    app.state.file_ingestion_processor = file_ingestion_processor
    app.include_router(router)

    @app.middleware("http")
    async def trace_http_flow(request: Request, call_next):
        """Trace every API flow without capturing query, body, or response data."""
        started_at = time.perf_counter()
        method = request.method
        response_status = status.HTTP_500_INTERNAL_SERVER_ERROR
        error_type: str | None = None
        try:
            with observation(
                name="friis-http-request",
                as_type="span",
                input={"content_captured": False},
                metadata={"http_method": method},
            ) as trace:
                try:
                    response = await call_next(request)
                except Exception as exc:
                    route = request.scope.get("route")
                    route_path = getattr(route, "path", "unmatched")
                    duration = round(time.perf_counter() - started_at, 4)
                    if trace is not None:
                        trace.update(
                            output={
                                "status_code": response_status,
                                "duration_seconds": duration,
                                "error_type": type(exc).__name__,
                                "content_captured": False,
                            },
                            metadata={
                                "operation": f"{method} {route_path}",
                                "http_method": method,
                                "http_route": route_path,
                                "outcome": "exception",
                            },
                        )
                    raise
                response_status = response.status_code
                route = request.scope.get("route")
                route_path = getattr(route, "path", "unmatched")
                duration = round(time.perf_counter() - started_at, 4)
                outcome = (
                    "success"
                    if response_status < status.HTTP_400_BAD_REQUEST
                    else "client_error"
                    if response_status < status.HTTP_500_INTERNAL_SERVER_ERROR
                    else "server_error"
                )
                if trace is not None:
                    trace.update(
                        output={
                            "status_code": response_status,
                            "duration_seconds": duration,
                            "outcome": outcome,
                            "content_captured": False,
                        },
                        metadata={
                            "operation": f"{method} {route_path}",
                            "http_method": method,
                            "http_route": route_path,
                            "outcome": outcome,
                        },
                    )
            extra = {
                "event": "http.request.completed",
                "http_method": method,
                "http_route": route_path,
                "http_status_code": response_status,
                "duration_seconds": duration,
            }
            if response_status >= status.HTTP_500_INTERNAL_SERVER_ERROR:
                logger.error("HTTP request completed with server error", extra=extra)
            elif response_status >= status.HTTP_400_BAD_REQUEST:
                logger.warning("HTTP request completed with client error", extra=extra)
            else:
                logger.info("HTTP request completed", extra=extra)
            return response
        except Exception as exc:
            error_type = type(exc).__name__
            route = request.scope.get("route")
            route_path = getattr(route, "path", "unmatched")
            duration = round(time.perf_counter() - started_at, 4)
            logger.exception(
                "HTTP request raised an unhandled exception",
                extra={
                    "event": "http.request.failed",
                    "http_method": method,
                    "http_route": route_path,
                    "http_status_code": response_status,
                    "duration_seconds": duration,
                    "error_type": error_type,
                },
            )
            raise

    @app.exception_handler(HTTPException)
    async def handle_http_exception(
        _request: Request, exc: HTTPException
    ) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        body = ErrorResponse(code=_error_code(exc.status_code), message=message)
        return JSONResponse(
            status_code=exc.status_code,
            content=body.model_dump(mode="json"),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_exception(
        _request: Request, _exc: RequestValidationError
    ) -> JSONResponse:
        body = ErrorResponse(
            code="invalid_request",
            message="Request validation failed.",
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=body.model_dump(mode="json"),
        )

    return app


def create_runtime_app(
    settings: RuntimeSettings | None = None,
) -> FastAPI:
    runtime = settings or RuntimeSettings.from_environment()
    database_url = make_url(runtime.database_url)
    connect_args = (
        {"check_same_thread": False}
        if database_url.drivername.startswith("sqlite")
        else {}
    )
    engine = create_engine(
        runtime.database_url,
        pool_pre_ping=True,
        connect_args=connect_args,
    )
    if runtime.auto_create_schema:
        create_schema(engine)
    service = DatabaseAPIService(
        engine,
        query_worker_ready=runtime.query_worker_enabled,
        ingestion_worker_ready=runtime.ingestion_worker_enabled,
    )
    authenticator = Auth0Authenticator(
        domain=runtime.auth0_domain,
        audience=runtime.auth0_api_audience,
        roles_claim=runtime.auth0_roles_claim,
        portfolio_ids_claim=runtime.auth0_portfolio_ids_claim,
        all_portfolios_claim=runtime.auth0_all_portfolios_claim,
        cache_seconds=runtime.auth0_jwks_cache_seconds,
        timeout_seconds=runtime.auth0_timeout_seconds,
    )
    if not runtime.ingestion_worker_enabled and not runtime.query_worker_enabled:
        return create_app(
            service,
            authenticator,
            cors_allowed_origins=runtime.cors_allowed_origins,
            file_ingestion_processor=partial(process_and_store_file, engine=engine),
        )

    embedder = AzureOpenAIEmbedder(
        endpoint=runtime.azure_openai_endpoint,
        api_key=runtime.azure_openai_api_key,
        api_version=runtime.azure_openai_api_version,
        deployment=runtime.azure_openai_embedding_deployment,
        dimensions=runtime.embedding_dimensions,
    )
    ingestion_worker = (
        DocumentIngestionWorker(
            engine,
            embedder,
            runtime.documents_root,
            poll_seconds=runtime.ingestion_poll_seconds,
            chunk_size=runtime.document_chunk_size,
            chunk_overlap=runtime.document_chunk_overlap,
            embedding_batch_size=runtime.embedding_batch_size,
        )
        if runtime.ingestion_worker_enabled
        else None
    )
    query_worker = None
    synthesis_client = None
    if runtime.query_worker_enabled:
        synthesizer = AzureSynthesisAgent(
            endpoint=runtime.azure_openai_endpoint,
            api_key=runtime.azure_openai_api_key,
            api_version=runtime.azure_openai_api_version,
            deployment=runtime.azure_openai_llm_deployment,
        )
        synthesis_client = synthesizer
        document_agent = DocumentRetrievalAgent(engine, embedder)
        portfolio_agent = PortfolioMarketAnalystAgent(engine)
        risk_agent = RiskPolicyAnalystAgent(portfolio_agent)

        def create_supervisor(
            event_sink: WorkflowEventSink | None,
        ) -> SupervisorAgent:
            return SupervisorAgent(
                agents=(document_agent, portfolio_agent, risk_agent),
                synthesizer=synthesizer,
                event_sink=event_sink,
            )

        query_worker = QueryWorker(
            engine,
            create_supervisor,
            poll_seconds=runtime.ingestion_poll_seconds,
            guardrails_validator=GuardrailsValidator(),
        )
    source_registration = None
    if runtime.ingestion_worker_enabled:
        source_registration = lambda: register_project_pdf_sources(
            engine, runtime.documents_root
        )

    finance_agent = None
    if (
        runtime.azure_openai_endpoint
        and runtime.azure_openai_api_key
        and runtime.azure_openai_api_version
        and runtime.azure_openai_llm_deployment
    ):
        try:
            finance_agent = create_finance_tool_agent(
                engine,
                endpoint=runtime.azure_openai_endpoint,
                api_key=runtime.azure_openai_api_key,
                api_version=runtime.azure_openai_api_version,
                deployment=runtime.azure_openai_llm_deployment,
            )
        except RuntimeError:
            finance_agent = None

    return create_app(
        service,
        authenticator,
        cors_allowed_origins=runtime.cors_allowed_origins,
        ingestion_worker=ingestion_worker,
        query_worker=query_worker,
        source_registration=source_registration,
        embedding_client=embedder,
        synthesis_client=synthesis_client,
        finance_agent=finance_agent,
        file_ingestion_processor=partial(process_and_store_file, engine=engine),
    )


def _error_code(status_code: int) -> str:
    return {
        status.HTTP_401_UNAUTHORIZED: "unauthorized",
        status.HTTP_403_FORBIDDEN: "forbidden",
        status.HTTP_404_NOT_FOUND: "not_found",
        status.HTTP_409_CONFLICT: "conflict",
        status.HTTP_422_UNPROCESSABLE_CONTENT: "invalid_request",
        status.HTTP_503_SERVICE_UNAVAILABLE: "service_unavailable",
    }.get(status_code, "request_failed")
