"""Environment-backed settings for Auth0 and FRIIS persistence."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

AUTH0_CLAIMS_NAMESPACE = "https://friis-api"


@dataclass(frozen=True)
class RuntimeSettings:
    database_url: str
    auth0_domain: str
    auth0_api_audience: str
    auth0_swagger_client_id: str = ""
    cors_allowed_origins: tuple[str, ...] = ()
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = ""
    azure_openai_embedding_deployment: str = ""
    azure_openai_llm_deployment: str = ""
    azure_openai_judge_deployment: str = ""
    documents_root: Path = Path("Documents")
    embedding_dimensions: int = 1536
    ingestion_worker_enabled: bool = False
    query_worker_enabled: bool = False
    ingestion_poll_seconds: float = 2.0
    document_chunk_size: int = 1200
    document_chunk_overlap: int = 200
    embedding_batch_size: int = 32
    auth0_roles_claim: str = f"{AUTH0_CLAIMS_NAMESPACE}/roles"
    auth0_portfolio_ids_claim: str = f"{AUTH0_CLAIMS_NAMESPACE}/portfolio_ids"
    auth0_all_portfolios_claim: str = (
        f"{AUTH0_CLAIMS_NAMESPACE}/all_portfolios_access"
    )
    auth0_jwks_cache_seconds: int = 300
    auth0_timeout_seconds: float = 5.0
    auto_create_schema: bool = False
    query_worker_ready: bool = False
    ingestion_worker_ready: bool = False

    @classmethod
    def from_environment(cls, env_file: Path | None = None) -> "RuntimeSettings":
        project_root = Path(__file__).resolve().parents[1]
        default_env_file = project_root / ".env"
        load_dotenv(dotenv_path=env_file or default_env_file, override=False)
        database_url = _database_url_from_environment()
        required = {
            "FRIIS_DATABASE_URL": database_url,
            "FRIIS_AUTH0_DOMAIN": os.getenv("FRIIS_AUTH0_DOMAIN"),
            "FRIIS_AUTH0_API_AUDIENCE": os.getenv("FRIIS_AUTH0_API_AUDIENCE"),
        }
        ingestion_worker_enabled = _boolean("FRIIS_INGESTION_WORKER_ENABLED")
        query_worker_enabled = _boolean("FRIIS_QUERY_WORKER_ENABLED")
        embedding_settings = {
            "AZURE_OPENAI_ENDPOINT": os.getenv("AZURE_OPENAI_ENDPOINT"),
            "AZURE_OPENAI_API_KEY": os.getenv("AZURE_OPENAI_API_KEY"),
            "AZURE_OPENAI_API_VERSION": os.getenv("AZURE_OPENAI_API_VERSION"),
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT": os.getenv(
                "AZURE_OPENAI_EMBEDDING_DEPLOYMENT"
            ),
        }
        if ingestion_worker_enabled:
            required.update(embedding_settings)
        if query_worker_enabled:
            required.update(embedding_settings)
            required["AZURE_OPENAI_LLM_DEPLOYMENT"] = os.getenv(
                "AZURE_OPENAI_LLM_DEPLOYMENT"
            )
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise RuntimeError(
                "Missing required runtime settings: " + ", ".join(missing)
            )
        embedding_dimensions = _positive_int(
            "FRIIS_EMBEDDING_DIMENSIONS", default=1536
        )
        if embedding_dimensions != 1536:
            raise RuntimeError(
                "FRIIS_EMBEDDING_DIMENSIONS must be 1536 for the current pgvector schema"
            )
        return cls(
            database_url=required["FRIIS_DATABASE_URL"] or "",
            auth0_domain=required["FRIIS_AUTH0_DOMAIN"] or "",
            auth0_api_audience=required["FRIIS_AUTH0_API_AUDIENCE"] or "",
            auth0_swagger_client_id=os.getenv(
                "FRIIS_AUTH0_SWAGGER_CLIENT_ID", ""
            ).strip(),
            cors_allowed_origins=tuple(
                origin.strip().rstrip("/")
                for origin in os.getenv("FRIIS_CORS_ALLOW_ORIGINS", "").split(",")
                if origin.strip()
            ),
            azure_openai_endpoint=embedding_settings["AZURE_OPENAI_ENDPOINT"] or "",
            azure_openai_api_key=embedding_settings["AZURE_OPENAI_API_KEY"] or "",
            azure_openai_api_version=embedding_settings["AZURE_OPENAI_API_VERSION"] or "",
            azure_openai_embedding_deployment=(
                embedding_settings["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"] or ""
            ),
            azure_openai_llm_deployment=(
                os.getenv("AZURE_OPENAI_LLM_DEPLOYMENT") or ""
            ),
            azure_openai_judge_deployment=(
                os.getenv("AZURE_OPENAI_JUDGE_DEPLOYMENT") or ""
            ),
            documents_root=(
                project_root / os.getenv("FRIIS_DOCUMENTS_ROOT", "Documents")
            ).resolve(),
            embedding_dimensions=embedding_dimensions,
            ingestion_worker_enabled=ingestion_worker_enabled,
            query_worker_enabled=query_worker_enabled,
            ingestion_poll_seconds=_positive_float(
                "FRIIS_INGESTION_POLL_SECONDS", default=2.0
            ),
            document_chunk_size=_positive_int(
                "FRIIS_DOCUMENT_CHUNK_SIZE", default=1200
            ),
            document_chunk_overlap=_nonnegative_int(
                "FRIIS_DOCUMENT_CHUNK_OVERLAP", default=200
            ),
            embedding_batch_size=_positive_int(
                "FRIIS_EMBEDDING_BATCH_SIZE", default=32
            ),
            auth0_roles_claim=os.getenv(
                "FRIIS_AUTH0_ROLES_CLAIM",
                f"{AUTH0_CLAIMS_NAMESPACE}/roles",
            ),
            auth0_portfolio_ids_claim=os.getenv(
                "FRIIS_AUTH0_PORTFOLIO_IDS_CLAIM",
                f"{AUTH0_CLAIMS_NAMESPACE}/portfolio_ids",
            ),
            auth0_all_portfolios_claim=os.getenv(
                "FRIIS_AUTH0_ALL_PORTFOLIOS_CLAIM",
                f"{AUTH0_CLAIMS_NAMESPACE}/all_portfolios_access",
            ),
            auth0_jwks_cache_seconds=_positive_int(
                "FRIIS_AUTH0_JWKS_CACHE_SECONDS", default=300
            ),
            auth0_timeout_seconds=_positive_float(
                "FRIIS_AUTH0_TIMEOUT_SECONDS", default=5.0
            ),
            auto_create_schema=_boolean("FRIIS_AUTO_CREATE_SCHEMA"),
            query_worker_ready=query_worker_enabled,
            ingestion_worker_ready=ingestion_worker_enabled,
        )


def _database_url_from_environment() -> str | None:
    for key in ("FRIIS_DATABASE_URL", "DATABASE_URL_POOLED", "DATABASE_URL"):
        raw_url = os.getenv(key)
        if raw_url:
            try:
                url = make_url(raw_url)
            except (ArgumentError, ValueError) as exc:
                raise RuntimeError(f"{key} must be a valid database URL") from exc
            if url.drivername in {"sqlite", "sqlite+pysqlite"}:
                return raw_url
            if url.drivername not in {
                "postgres",
                "postgresql",
                "postgresql+psycopg",
                "postgresql+psycopg2",
            }:
                raise RuntimeError(f"{key} must use PostgreSQL or SQLite")
            return url.set(drivername="postgresql+psycopg").render_as_string(
                hide_password=False
            )

    keys = ("DB_USER", "DB_PASSWORD", "DB_HOST", "DB_PORT", "DB_NAME")
    values = {key: os.getenv(key) for key in keys}
    if all(value for value in values.values()):
        try:
            port = int(values["DB_PORT"] or "")
        except ValueError as exc:
            raise RuntimeError("DB_PORT must be an integer") from exc
        if not 1 <= port <= 65535:
            raise RuntimeError("DB_PORT must be between 1 and 65535")
        return URL.create(
            "postgresql+psycopg",
            username=values["DB_USER"],
            password=values["DB_PASSWORD"],
            host=values["DB_HOST"],
            port=port,
            database=values["DB_NAME"],
        ).render_as_string(hide_password=False)
    if any(value for value in values.values()):
        missing = [key for key, value in values.items() if not value]
        raise RuntimeError(
            "Incomplete PostgreSQL settings; missing: " + ", ".join(missing)
        )
    return os.getenv("FRIIS_DATABASE_URL")


def _positive_int(name: str, *, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a positive integer") from exc
    if value <= 0:
        raise RuntimeError(f"{name} must be a positive integer")
    return value


def _nonnegative_int(name: str, *, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a non-negative integer") from exc
    if value < 0:
        raise RuntimeError(f"{name} must be a non-negative integer")
    return value


def _positive_float(name: str, *, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a positive number") from exc
    if value <= 0:
        raise RuntimeError(f"{name} must be a positive number")
    return value


def _boolean(name: str) -> bool:
    value = os.getenv(name, "false").strip().lower()
    if value not in {"true", "false"}:
        raise RuntimeError(f"{name} must be 'true' or 'false'")
    return value == "true"
