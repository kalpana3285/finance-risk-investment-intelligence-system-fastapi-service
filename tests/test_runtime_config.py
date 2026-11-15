import os
from pathlib import Path

import pytest

from config.runtime import AUTH0_CLAIMS_NAMESPACE, RuntimeSettings

ENV_KEYS = (
    "FRIIS_DATABASE_URL",
    "DATABASE_URL_POOLED",
    "DATABASE_URL",
    "DB_USER",
    "DB_PASSWORD",
    "DB_HOST",
    "DB_PORT",
    "DB_NAME",
    "DB_SSLMODE",
    "DB_CHANNELBINDING",
    "FRIIS_AUTH0_DOMAIN",
    "FRIIS_AUTH0_API_AUDIENCE",
    "FRIIS_CORS_ALLOW_ORIGINS",
    "FRIIS_AUTH0_ROLES_CLAIM",
    "FRIIS_AUTH0_PORTFOLIO_IDS_CLAIM",
    "FRIIS_AUTH0_ALL_PORTFOLIOS_CLAIM",
    "FRIIS_AUTH0_JWKS_CACHE_SECONDS",
    "FRIIS_AUTH0_TIMEOUT_SECONDS",
    "FRIIS_AUTO_CREATE_SCHEMA",
    "FRIIS_QUERY_WORKER_READY",
    "FRIIS_QUERY_WORKER_ENABLED",
    "FRIIS_INGESTION_WORKER_READY",
    "FRIIS_INGESTION_WORKER_ENABLED",
    "FRIIS_EMBEDDING_DIMENSIONS",
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_API_VERSION",
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT",
    "AZURE_OPENAI_LLM_DEPLOYMENT",
)


def test_runtime_prefers_pooled_postgres_url_and_preserves_ssl(
    tmp_path: Path,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_URL_POOLED=postgresql://pooled-user:pooled-password@pool.example.neon.tech/app?sslmode=require&channel_binding=require\nDATABASE_URL=postgresql://direct-user:direct-password@direct.example.neon.tech/app?sslmode=require\nDB_USER=legacy-user\nDB_PASSWORD=legacy-password\nDB_HOST=localhost\nDB_PORT=5432\nDB_NAME=legacy\nFRIIS_AUTH0_DOMAIN=tenant.example.auth0.com\nFRIIS_AUTH0_API_AUDIENCE=https://api.example.test"
    )
    before = {key: os.environ.get(key) for key in ENV_KEYS}
    for key in ENV_KEYS:
        os.environ.pop(key, None)
    try:
        settings = RuntimeSettings.from_environment(env_file)
    finally:
        for key in ENV_KEYS:
            os.environ.pop(key, None)
            if before[key] is not None:
                os.environ[key] = before[key] or ""

    assert settings.database_url.startswith("postgresql+psycopg://")
    assert "pool.example.neon.tech" in settings.database_url
    assert "sslmode=require" in settings.database_url
    assert "channel_binding=require" in settings.database_url


def test_explicit_friis_database_url_takes_precedence_over_neon_urls(
    tmp_path: Path,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "FRIIS_DATABASE_URL=postgresql://explicit-user:explicit-password@explicit.example.neon.tech/app?sslmode=require\nDATABASE_URL_POOLED=postgresql://pooled-user:pooled-password@pool.example.neon.tech/app?sslmode=require\nFRIIS_AUTH0_DOMAIN=tenant.example.auth0.com\nFRIIS_AUTH0_API_AUDIENCE=https://api.example.test"
    )
    before = {key: os.environ.get(key) for key in ENV_KEYS}
    for key in ENV_KEYS:
        os.environ.pop(key, None)
    try:
        settings = RuntimeSettings.from_environment(env_file)
    finally:
        for key in ENV_KEYS:
            os.environ.pop(key, None)
            if before[key] is not None:
                os.environ[key] = before[key] or ""

    assert "explicit.example.neon.tech" in settings.database_url
    assert "pool.example.neon.tech" not in settings.database_url


def test_runtime_settings_load_auth0_configuration_from_env_file(
    tmp_path: Path,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "FRIIS_DATABASE_URL=sqlite:///./test.db\nFRIIS_AUTH0_DOMAIN=tenant.example.auth0.com\nFRIIS_AUTH0_API_AUDIENCE=https://api.example.test\nFRIIS_CORS_ALLOW_ORIGINS=https://app.example.test/, https://preview.example.test\nFRIIS_AUTO_CREATE_SCHEMA=true"
    )
    before = {key: os.environ.get(key) for key in ENV_KEYS}
    for key in ENV_KEYS:
        os.environ.pop(key, None)
    try:
        settings = RuntimeSettings.from_environment(env_file)
    finally:
        for key in ENV_KEYS:
            os.environ.pop(key, None)
            if before[key] is not None:
                os.environ[key] = before[key] or ""

    assert settings.database_url == "sqlite:///./test.db"
    assert settings.auth0_domain == "tenant.example.auth0.com"
    assert settings.auth0_api_audience == "https://api.example.test"
    assert settings.auth0_roles_claim == f"{AUTH0_CLAIMS_NAMESPACE}/roles"
    assert settings.cors_allowed_origins == (
        "https://app.example.test",
        "https://preview.example.test",
    )
    assert settings.auto_create_schema is True
    assert settings.query_worker_ready is False


def test_runtime_settings_fail_when_required_values_are_missing(
    tmp_path: Path,
) -> None:
    env_file = tmp_path / "empty.env"
    env_file.write_text("")
    before = {key: os.environ.get(key) for key in ENV_KEYS}
    for key in ENV_KEYS:
        os.environ.pop(key, None)
    try:
        with pytest.raises(RuntimeError, match="FRIIS_AUTH0_DOMAIN"):
            RuntimeSettings.from_environment(env_file)
    finally:
        for key in ENV_KEYS:
            os.environ.pop(key, None)
            if before[key] is not None:
                os.environ[key] = before[key] or ""


def test_ingestion_worker_requires_embedding_config_and_fixed_vector_size(
    tmp_path: Path,
) -> None:
    env_file = tmp_path / "ingestion.env"
    env_file.write_text(
        "FRIIS_DATABASE_URL=sqlite:///./test.db\nFRIIS_AUTH0_DOMAIN=tenant.example.auth0.com\nFRIIS_AUTH0_API_AUDIENCE=https://api.example.test\nFRIIS_INGESTION_WORKER_ENABLED=true"
    )
    before = {key: os.environ.get(key) for key in ENV_KEYS}
    for key in ENV_KEYS:
        os.environ.pop(key, None)
    try:
        with pytest.raises(RuntimeError, match="AZURE_OPENAI_ENDPOINT"):
            RuntimeSettings.from_environment(env_file)
    finally:
        for key in ENV_KEYS:
            os.environ.pop(key, None)
            if before[key] is not None:
                os.environ[key] = before[key] or ""

    env_file.write_text(
        env_file.read_text()
        + "\n"
        + "AZURE_OPENAI_ENDPOINT=https://example.openai.azure.com/\nAZURE_OPENAI_API_KEY=placeholder\nAZURE_OPENAI_API_VERSION=2024-06-01\nAZURE_OPENAI_EMBEDDING_DEPLOYMENT=embedding\nFRIIS_EMBEDDING_DIMENSIONS=1024"
    )
    before = {key: os.environ.get(key) for key in ENV_KEYS}
    for key in ENV_KEYS:
        os.environ.pop(key, None)
    try:
        with pytest.raises(RuntimeError, match="must be 1536"):
            RuntimeSettings.from_environment(env_file)
    finally:
        for key in ENV_KEYS:
            os.environ.pop(key, None)
            if before[key] is not None:
                os.environ[key] = before[key] or ""


def test_query_worker_requires_chat_deployment(tmp_path: Path) -> None:
    env_file = tmp_path / "query-worker.env"
    env_file.write_text(
        "FRIIS_DATABASE_URL=sqlite:///./test.db\nFRIIS_AUTH0_DOMAIN=tenant.example.auth0.com\nFRIIS_AUTH0_API_AUDIENCE=https://api.example.test\nFRIIS_QUERY_WORKER_ENABLED=true\nAZURE_OPENAI_ENDPOINT=https://example.openai.azure.com/\nAZURE_OPENAI_API_KEY=placeholder\nAZURE_OPENAI_API_VERSION=2024-06-01\nAZURE_OPENAI_EMBEDDING_DEPLOYMENT=embedding"
    )
    before = {key: os.environ.get(key) for key in ENV_KEYS}
    for key in ENV_KEYS:
        os.environ.pop(key, None)
    try:
        with pytest.raises(RuntimeError, match="AZURE_OPENAI_LLM_DEPLOYMENT"):
            RuntimeSettings.from_environment(env_file)
    finally:
        for key in ENV_KEYS:
            os.environ.pop(key, None)
            if before[key] is not None:
                os.environ[key] = before[key] or ""
