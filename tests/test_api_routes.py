from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.factory import create_app
from schemas import (
    EscalationStatus,
    HealthStatus,
    IngestionStatus,
    QueryStatus,
)
from security.auth import AuthenticationError, Principal, Role
from services.api_service import EscalationConflictError

NOW = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)


class FakeAuthenticator:
    async def authenticate(self, token: str) -> Principal:
        principals = {
            "analyst": Principal(
                subject="analyst-1",
                roles=frozenset({Role.ANALYST}),
                portfolio_ids=frozenset({1}),
            ),
            "reviewer": Principal(
                subject="reviewer-1",
                roles=frozenset({Role.COMPLIANCE_REVIEWER}),
                portfolio_ids=frozenset({1}),
            ),
            "operator": Principal(
                subject="operator-1",
                roles=frozenset({Role.OPERATOR}),
                portfolio_ids=frozenset(),
            ),
            "no-scope": Principal(
                subject="analyst-no-scope",
                roles=frozenset({Role.ANALYST}),
            ),
        }
        try:
            return principals[token]
        except KeyError as exc:
            raise AuthenticationError from exc


class FakeAPIService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.health_checks = {"database": HealthStatus.OK}
        self.escalation_conflict = False

    async def submit_query(self, principal: Principal, request: Any) -> Any:
        self.calls.append(("submit_query", (principal, request)))
        return {
            "query_id": "query-1",
            "status": QueryStatus.QUEUED,
            "submitted_at": NOW,
        }

    async def get_query(self, principal: Principal, query_id: str) -> Any:
        self.calls.append(("get_query", (principal, query_id)))
        if query_id == "missing":
            return None
        return {"query_id": query_id, "status": QueryStatus.PROCESSING}

    async def list_portfolios(self, principal: Principal, query: Any) -> Any:
        self.calls.append(("list_portfolios", (principal, query)))
        return {
            "items": [
                {
                    "portfolio_id": 1,
                    "portfolio_name": "Global Growth Fund",
                    "risk_category": "High",
                }
            ],
            "next_cursor": None,
        }

    async def get_portfolio(self, principal: Principal, portfolio_id: int) -> Any:
        self.calls.append(("get_portfolio", (principal, portfolio_id)))
        if portfolio_id != 1:
            return None
        return {
            "portfolio_id": 1,
            "portfolio_name": "Global Growth Fund",
            "holdings": [],
            "risk_assessments": [],
        }

    async def list_escalations(self, principal: Principal, query: Any) -> Any:
        self.calls.append(("list_escalations", (principal, query)))
        return {
            "items": [
                {
                    "escalation_id": "escalation-1",
                    "query_id": "query-1",
                    "status": EscalationStatus.OPEN,
                    "reason": "Insufficient evidence",
                    "created_at": NOW,
                }
            ]
        }

    async def get_escalation(self, principal: Principal, escalation_id: str) -> Any:
        self.calls.append(("get_escalation", (principal, escalation_id)))
        if escalation_id == "missing":
            return None
        return {
            "escalation_id": escalation_id,
            "query_id": "query-1",
            "status": EscalationStatus.OPEN,
            "reason": "Insufficient evidence",
            "question": "Can this exposure be assessed?",
            "requested_review": "Review the evidence.",
            "created_at": NOW,
            "updated_at": NOW,
        }

    async def update_escalation(
        self, principal: Principal, escalation_id: str, update: Any
    ) -> Any:
        self.calls.append(("update_escalation", (principal, escalation_id, update)))
        if self.escalation_conflict:
            raise EscalationConflictError("Closed escalations cannot be changed.")
        if escalation_id == "missing":
            return None
        return {
            **(await self.get_escalation(principal, escalation_id)),
            "status": update.status or EscalationStatus.OPEN,
            "outcome": update.outcome,
            "reviewer_notes": update.reviewer_notes,
        }

    async def start_ingestion(self, principal: Principal, request: Any) -> Any:
        self.calls.append(("start_ingestion", (principal, request)))
        return {
            "ingestion_id": "ingestion-1",
            "status": IngestionStatus.QUEUED,
            "submitted_at": NOW,
        }

    async def health(self) -> dict[str, HealthStatus]:
        return self.health_checks


@pytest.fixture
def service() -> FakeAPIService:
    return FakeAPIService()


@pytest.fixture
def client(service: FakeAPIService) -> TestClient:
    return TestClient(create_app(service, FakeAuthenticator()))


def _auth(token: str = "analyst") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_http_traces_include_operation_and_success_outcome(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    updates: list[dict[str, Any]] = []

    class FakeSpan:
        def update(self, **kwargs: Any) -> None:
            updates.append(kwargs)

    @contextmanager
    def fake_observation(**_kwargs: Any):
        yield FakeSpan()

    monkeypatch.setattr("app.factory.observation", fake_observation)

    response = client.get("/health")

    assert response.status_code == 200
    assert updates[-1]["metadata"] == {
        "operation": "GET /health",
        "http_method": "GET",
        "http_route": "/health",
        "outcome": "success",
    }
    assert updates[-1]["output"]["content_captured"] is False


def test_http_traces_include_handled_client_error(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    updates: list[dict[str, Any]] = []

    class FakeSpan:
        def update(self, **kwargs: Any) -> None:
            updates.append(kwargs)

    @contextmanager
    def fake_observation(**_kwargs: Any):
        yield FakeSpan()

    monkeypatch.setattr("app.factory.observation", fake_observation)

    response = client.get("/api/v1/queries/missing", headers=_auth())

    assert response.status_code == 404
    assert updates[-1]["metadata"]["operation"] == "GET /api/v1/queries/{query_id}"
    assert updates[-1]["metadata"]["outcome"] == "client_error"
    assert updates[-1]["output"]["status_code"] == 404


def test_http_traces_capture_unhandled_exception_type_without_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    updates: list[dict[str, Any]] = []

    class FakeSpan:
        def update(self, **kwargs: Any) -> None:
            updates.append(kwargs)

    @contextmanager
    def fake_observation(**_kwargs: Any):
        yield FakeSpan()

    async def fail_get_query(_principal: Principal, _query_id: str) -> None:
        raise RuntimeError("sensitive failure detail")

    monkeypatch.setattr("app.factory.observation", fake_observation)
    service = FakeAPIService()
    service.get_query = fail_get_query
    error_client = TestClient(
        create_app(service, FakeAuthenticator()), raise_server_exceptions=False
    )

    response = error_client.get("/api/v1/queries/query-1", headers=_auth())

    assert response.status_code == 500
    assert updates[-1]["metadata"]["operation"] == "GET /api/v1/queries/{query_id}"
    assert updates[-1]["metadata"]["outcome"] == "exception"
    assert updates[-1]["output"]["error_type"] == "RuntimeError"
    assert "sensitive failure detail" not in str(updates[-1])


def test_query_routes_submit_and_retrieve_query(client: TestClient) -> None:
    submit = client.post(
        "/api/v1/queries",
        headers=_auth(),
        json={"question": "Summarize portfolio risk", "portfolio_id": 1},
    )
    assert submit.status_code == 202
    assert submit.json()["status"] == "queued"

    result = client.get("/api/v1/queries/query-1", headers=_auth())
    assert result.status_code == 200
    assert result.json()["status"] == "processing"
    assert client.get("/api/v1/queries/missing", headers=_auth()).status_code == 404


def test_portfolio_routes_validate_role_scope_and_pagination(
    client: TestClient, service: FakeAPIService
) -> None:
    listing = client.get(
        "/api/v1/portfolios?limit=10&risk_category=High", headers=_auth()
    )
    assert listing.status_code == 200
    assert listing.json()["items"][0]["portfolio_id"] == 1
    passed_query = next(args[1] for name, args in service.calls if name == "list_portfolios")
    assert passed_query.limit == 10
    assert passed_query.risk_category == "High"

    detail = client.get("/api/v1/portfolios/1", headers=_auth())
    assert detail.status_code == 200
    assert client.get("/api/v1/portfolios/2", headers=_auth()).status_code == 403
    no_scope_client = TestClient(create_app(service, FakeAuthenticator()))
    assert no_scope_client.get(
        "/api/v1/portfolios/1",
        headers=_auth("no-scope"),
    ).status_code == 403
    assert client.get("/api/v1/portfolios?limit=101", headers=_auth()).status_code == 422


def test_escalation_routes_restrict_access_and_surface_transition_conflicts(
    client: TestClient, service: FakeAPIService
) -> None:
    assert client.get(
        "/api/v1/escalations?status=open", headers=_auth("reviewer")
    ).status_code == 200
    assert client.get("/api/v1/escalations", headers=_auth()).status_code == 403

    detail = client.get(
        "/api/v1/escalations/escalation-1", headers=_auth("reviewer")
    )
    assert detail.status_code == 200

    update = client.patch(
        "/api/v1/escalations/escalation-1",
        headers=_auth("reviewer"),
        json={"status": "resolved", "reviewer_notes": "Reviewed evidence."},
    )
    assert update.status_code == 200
    assert update.json()["status"] == "resolved"

    service.escalation_conflict = True
    conflict = client.patch(
        "/api/v1/escalations/escalation-1",
        headers=_auth("reviewer"),
        json={"status": "closed"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "conflict"
    assert client.get(
        "/api/v1/escalations/missing", headers=_auth("reviewer")
    ).status_code == 404


def test_ingestion_routes_upload_and_process_files(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("INFO")
    processed: dict[str, Any] = {}

    def fake_process_and_store_file(
        file_path: Any,
        chunk_size: int,
        chunk_overlap: int,
        *,
        filename: str,
    ) -> dict[str, Any]:
        processed.update(
            {
                "file_exists": file_path.is_file(),
                "temp_path": file_path,
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
                "filename": filename,
            }
        )
        return {
            "status": "success",
            "filename": filename,
            "file_type": "pdf",
            "total_chunks": 1,
            "average_chunk_length": 45.0,
            "min_chunk_length": 45,
            "max_chunk_length": 45,
            "processing_time_seconds": 0.1,
            "collection_name": "friis_uploaded_documents",
            "chunk_ids": ["chunk-1"],
            "source_documents": 1,
        }

    monkeypatch.setattr(
        "routes.api.process_and_store_file", fake_process_and_store_file
    )
    start = client.post(
        "/api/v1/admin/ingestions",
        headers=_auth("operator"),
        files={"file": ("risk-policy.pdf", b"pdf contents", "application/pdf")},
        params={"chunk_size": 500, "chunk_overlap": 50},
    )
    assert start.status_code == 200
    assert start.json()["filename"] == "risk-policy.pdf"
    assert start.json()["total_chunks"] == 1
    assert {
        record.event
        for record in caplog.records
        if hasattr(record, "event")
    } >= {
        "document_ingestion.received",
        "document_ingestion.validated",
        "document_ingestion.upload_read_started",
        "document_ingestion.staging_started",
        "document_ingestion.pipeline_started",
        "document_ingestion.completed",
        "document_ingestion.temp_file_removed",
    }
    log_file = Path(__file__).resolve().parents[1] / "logger.txt"
    log_contents = log_file.read_text(encoding="utf-8")
    assert "Document ingestion pipeline completed" in log_contents
    assert '"total_chunks": 1' in log_contents
    assert '"storage_table": "langchain_pg_embedding"' in log_contents
    assert '"uploaded_filename": "risk-policy.pdf"' in log_contents
    assert any(
        record.event == "document_ingestion.pipeline_started"
        and record.storage_table == "langchain_pg_embedding"
        for record in caplog.records
    )
    assert processed == {
        "file_exists": True,
        "chunk_size": 500,
        "chunk_overlap": 50,
        "filename": "risk-policy.pdf",
        "temp_path": processed["temp_path"],
    }
    assert not processed["temp_path"].exists()

    assert client.get(
        "/api/v1/admin/ingestions/ingestion-1", headers=_auth("operator")
    ).status_code == 404
    assert client.post(
        "/api/v1/admin/ingestions",
        headers=_auth(),
        files={"file": ("risk-policy.pdf", b"pdf contents", "application/pdf")},
    ).status_code == 403


def test_ingestion_route_rejects_empty_or_unsupported_uploads(
    client: TestClient,
) -> None:
    empty = client.post(
        "/api/v1/admin/ingestions",
        headers=_auth("operator"),
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert empty.status_code == 422

    unsupported = client.post(
        "/api/v1/admin/ingestions",
        headers=_auth("operator"),
        files={"file": ("archive.zip", b"data", "application/zip")},
    )
    assert unsupported.status_code == 422

    invalid_overlap = client.post(
        "/api/v1/admin/ingestions",
        headers=_auth("operator"),
        files={"file": ("source.txt", b"content", "text/plain")},
        params={"chunk_size": 10, "chunk_overlap": 10},
    )
    assert invalid_overlap.status_code == 422

    too_large = client.post(
        "/api/v1/admin/ingestions",
        headers=_auth("operator"),
        files={"file": ("large.txt", b"x" * (10 * 1024 * 1024 + 1), "text/plain")},
    )
    assert too_large.status_code == 413


def test_authentication_errors_and_missing_integrations_fail_closed() -> None:
    unconfigured = TestClient(create_app())
    missing_auth = unconfigured.get("/api/v1/portfolios")
    assert missing_auth.status_code == 401
    no_auth_provider = unconfigured.get(
        "/api/v1/portfolios", headers=_auth("analyst")
    )
    assert no_auth_provider.status_code == 503
    assert no_auth_provider.json()["code"] == "service_unavailable"
    assert unconfigured.get("/health").status_code == 503

    client = TestClient(create_app(FakeAPIService(), FakeAuthenticator()))
    assert client.get("/api/v1/portfolios").status_code == 401
    assert client.get("/api/v1/portfolios", headers=_auth("unknown")).status_code == 401


def test_health_reports_degraded_dependencies_as_unavailable(
    client: TestClient, service: FakeAPIService
) -> None:
    healthy = client.get("/health")
    assert healthy.status_code == 200
    assert healthy.json()["status"] == "ok"

    service.health_checks = {"database": HealthStatus.UNAVAILABLE}
    unhealthy = client.get("/health")
    assert unhealthy.status_code == 503
    assert unhealthy.json()["status"] == "degraded"


def test_openapi_exposes_all_ten_documented_routes(client: TestClient) -> None:
    openapi = client.get("/openapi.json").json()
    paths = openapi["paths"]
    expected = {
        "/api/v1/queries": {"post"},
        "/api/v1/queries/{query_id}": {"get"},
        "/api/v1/portfolios": {"get"},
        "/api/v1/portfolios/{portfolio_id}": {"get"},
        "/api/v1/escalations": {"get"},
        "/api/v1/escalations/{escalation_id}": {"get", "patch"},
        "/api/v1/admin/ingestions": {"post"},
        "/health": {"get"},
    }
    for path, methods in expected.items():
        assert methods <= paths[path].keys()
    assert sum(len(methods) for methods in expected.values()) == 9

    upload_operation = paths["/api/v1/admin/ingestions"]["post"]
    request_body = upload_operation["requestBody"]
    assert request_body["content"]["multipart/form-data"]["schema"] == {
        "$ref": "#/components/schemas/Body_start_ingestion_api_v1_admin_ingestions_post"
    }
    upload_schema = openapi["components"]["schemas"][
        "Body_start_ingestion_api_v1_admin_ingestions_post"
    ]
    assert upload_schema["required"] == ["file"]
    assert upload_schema["properties"]["file"] == {
        "type": "string",
        "format": "binary",
        "title": "File",
    }
