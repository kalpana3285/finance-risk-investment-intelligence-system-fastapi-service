from pathlib import Path

from fastapi.testclient import TestClient

from app.factory import create_runtime_app
from config.runtime import RuntimeSettings
from security.auth import Auth0Authenticator
from services.database_api_service import DatabaseAPIService
from services.guardrails import GuardrailsValidator
from services.query_worker import QueryWorker


def test_runtime_app_wires_auth0_database_service_and_optional_schema_creation(
    tmp_path: Path,
) -> None:
    settings = RuntimeSettings(
        database_url=f"sqlite:///{tmp_path / 'friis.db'}",
        auth0_domain="tenant.example.auth0.com",
        auth0_api_audience="https://api.example.test",
        cors_allowed_origins=("https://frontend.example.test",),
        auto_create_schema=True,
    )
    app = create_runtime_app(settings)

    assert isinstance(app.state.authenticator, Auth0Authenticator)
    assert isinstance(app.state.api_service, DatabaseAPIService)
    with TestClient(app) as client:
        response = client.get("/health")
        cors_response = client.options(
            "/health",
            headers={
                "Origin": "https://frontend.example.test",
                "Access-Control-Request-Method": "GET",
            },
        )
    assert response.status_code == 503
    assert response.json()["checks"]["database"] == "ok"
    assert cors_response.status_code == 200
    assert (
        cors_response.headers["access-control-allow-origin"]
        == "https://frontend.example.test"
    )
    assert (tmp_path / "friis.db").is_file()


def test_runtime_app_wires_optional_query_control_plane_and_worker(
    tmp_path: Path,
) -> None:
    settings = RuntimeSettings(
        database_url=f"sqlite:///{tmp_path / 'friis.db'}",
        auth0_domain="tenant.example.auth0.com",
        auth0_api_audience="https://api.example.test",
        azure_openai_endpoint="https://example.openai.azure.com/",
        azure_openai_api_key="test-key",
        azure_openai_api_version="2024-06-01",
        azure_openai_embedding_deployment="embedding",
        azure_openai_llm_deployment="chat",
        query_worker_enabled=True,
        ingestion_poll_seconds=0.01,
        auto_create_schema=True,
    )
    app = create_runtime_app(settings)

    assert isinstance(app.state.query_worker, QueryWorker)
    assert isinstance(app.state.query_worker.guardrails_validator, GuardrailsValidator)
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["checks"]["database"] == "ok"
    assert response.json()["checks"]["query_worker"] == "ok"
