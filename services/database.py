"""SQLAlchemy schema for FRIIS finance data and durable API work records."""

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.engine import Engine
from sqlalchemy.schema import Index

metadata = MetaData()
EMBEDDING_DIMENSIONS = 1536

portfolios = Table(
    "portfolios",
    metadata,
    Column("portfolio_id", Integer, primary_key=True, autoincrement=True),
    Column("portfolio_name", String(150), nullable=False),
    Column("portfolio_manager", String(150)),
    Column("risk_category", String(50)),
    Column("total_value", Numeric),
    Column("benchmark_index", String(100)),
    Column("created_at", DateTime(timezone=True)),
)

portfolio_holdings = Table(
    "portfolio_holdings",
    metadata,
    Column("holding_id", Integer, primary_key=True, autoincrement=True),
    Column("portfolio_id", ForeignKey("portfolios.portfolio_id", ondelete="CASCADE")),
    Column("asset_name", String(150)),
    Column("asset_type", String(100)),
    Column("sector", String(100)),
    Column("allocation_percentage", Numeric),
    Column("market_value", Numeric),
    Column("last_updated", Date),
)

asset_risk_logs = Table(
    "asset_risk_logs",
    metadata,
    Column("risk_id", Integer, primary_key=True, autoincrement=True),
    Column("asset_name", String(150)),
    Column("risk_type", String(100)),
    Column("risk_score", Integer),
    Column("risk_level", String(50)),
    Column("risk_description", Text),
    Column("assessment_date", Date),
    Column("escalation_flag", Boolean, nullable=False, default=False),
    Column("created_at", DateTime(timezone=True)),
    CheckConstraint("risk_score IS NULL OR risk_score BETWEEN 0 AND 100"),
)

market_indicators = Table(
    "market_indicators",
    metadata,
    Column("indicator_id", Integer, primary_key=True, autoincrement=True),
    Column("indicator_name", String(150)),
    Column("region", String(100)),
    Column("indicator_value", Numeric),
    Column("measurement_date", Date),
    Column("trend_direction", String(50)),
    Column("created_at", DateTime(timezone=True)),
)

investment_decisions = Table(
    "investment_decisions",
    metadata,
    Column("decision_id", Integer, primary_key=True, autoincrement=True),
    Column("portfolio_id", ForeignKey("portfolios.portfolio_id", ondelete="CASCADE")),
    Column("asset_name", String(150)),
    Column("decision_type", String(50)),
    Column("decision_reason", Text),
    Column("risk_assessment_reference", ForeignKey("asset_risk_logs.risk_id")),
    Column("decision_date", Date),
    Column("approval_status", String(50)),
    Column("created_at", DateTime(timezone=True)),
)

query_requests = Table(
    "query_requests",
    metadata,
    Column("query_id", String(36), primary_key=True),
    Column("owner_subject", String(255), nullable=False, index=True),
    Column("question", Text, nullable=False),
    Column("portfolio_id", ForeignKey("portfolios.portfolio_id")),
    Column("session_id", String(128)),
    Column("conversation_context", JSON, nullable=False, default=list),
    Column("authorized_portfolio_ids", JSON, nullable=False, default=list),
    Column("all_portfolios_access", Boolean, nullable=False, default=False),
    Column("principal_roles", JSON, nullable=False, default=list),
    Column("status", String(32), nullable=False, index=True),
    Column("answer", Text),
    Column("citations", JSON, nullable=False, default=list),
    Column("limitations", JSON, nullable=False, default=list),
    Column("clarification_question", Text),
    Column("escalation_id", String(128)),
    Column("failure", JSON),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

# Short-lived continuity state contains only explicit user questions. Assistant
# answers and financial evidence are never written to this table.
conversation_sessions = Table(
    "conversation_sessions",
    metadata,
    Column("owner_subject", String(255), primary_key=True),
    Column("session_id", String(128), primary_key=True),
    Column("user_questions", JSON, nullable=False, default=list),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

query_workflow_events = Table(
    "query_workflow_events",
    metadata,
    Column("event_id", String(36), primary_key=True),
    Column(
        "query_id",
        ForeignKey("query_requests.query_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("event_type", String(64), nullable=False),
    Column("agent_name", String(100)),
    Column("details", JSON, nullable=False, default=dict),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

escalations = Table(
    "escalations",
    metadata,
    Column("escalation_id", String(128), primary_key=True),
    Column("query_id", ForeignKey("query_requests.query_id"), nullable=False, index=True),
    Column("portfolio_id", ForeignKey("portfolios.portfolio_id"), index=True),
    Column("status", String(32), nullable=False, index=True),
    Column("reason", Text, nullable=False),
    Column("question", Text, nullable=False),
    Column("evidence", JSON, nullable=False, default=list),
    Column("attempted_steps", JSON, nullable=False, default=list),
    Column("data_gaps", JSON, nullable=False, default=list),
    Column("requested_review", Text, nullable=False),
    Column("reviewer_notes", Text),
    Column("outcome", String(64)),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

ingestion_runs = Table(
    "ingestion_runs",
    metadata,
    Column("ingestion_id", String(36), primary_key=True),
    Column("run_type", String(20), nullable=False),
    Column("status", String(20), nullable=False, index=True),
    Column("initiated_by", String(200), nullable=False),
    Column("pipeline_version", String(100), nullable=False),
    Column("source_type", String(32), nullable=False),
    Column("source_ids", JSON, nullable=False),
    Column("validation_errors", JSON, nullable=False, default=list),
    Column("started_at", DateTime(timezone=True)),
    Column("completed_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint(
        "completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at"
    ),
)

source_documents = Table(
    "source_documents",
    metadata,
    Column("document_id", String(36), primary_key=True),
    Column("source_key", String(200), nullable=False, unique=True),
    Column("title", String(500), nullable=False),
    Column("source_type", String(50), nullable=False),
    Column("source_uri", Text, nullable=False),
    Column("owner", String(200)),
    Column("access_classification", String(50), nullable=False, default="internal"),
    Column("approved", Boolean, nullable=False, default=False),
    Column("enabled", Boolean, nullable=False, default=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

document_versions = Table(
    "document_versions",
    metadata,
    Column("document_version_id", String(36), primary_key=True),
    Column("document_id", ForeignKey("source_documents.document_id"), nullable=False),
    Column("version_label", String(100), nullable=False),
    Column("content_sha256", String(64), nullable=False),
    Column("content_type", String(150), nullable=False),
    Column("storage_uri", Text, nullable=False),
    Column("published_at", Date),
    Column("effective_from", Date),
    Column("effective_to", Date),
    Column("validation_status", String(20), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("document_id", "version_label"),
    UniqueConstraint("document_id", "content_sha256"),
    CheckConstraint(
        "effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from"
    ),
)

ingestion_run_items = Table(
    "ingestion_run_items",
    metadata,
    Column("ingestion_id", ForeignKey("ingestion_runs.ingestion_id"), primary_key=True),
    Column(
        "document_version_id",
        ForeignKey("document_versions.document_version_id"),
        primary_key=True,
    ),
    Column("status", String(20), nullable=False),
    Column("records_processed", Integer, nullable=False, default=0),
    Column("chunks_created", Integer, nullable=False, default=0),
    Column("chunks_indexed", Integer, nullable=False, default=0),
    Column("error_code", String(100)),
    Column("error_message", Text),
    Column("started_at", DateTime(timezone=True)),
    Column("completed_at", DateTime(timezone=True)),
    CheckConstraint("records_processed >= 0"),
    CheckConstraint("chunks_created >= 0"),
    CheckConstraint("chunks_indexed >= 0"),
    CheckConstraint(
        "completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at"
    ),
)

document_chunks = Table(
    "document_chunks",
    metadata,
    Column("chunk_id", String(36), primary_key=True),
    Column(
        "document_version_id",
        ForeignKey("document_versions.document_version_id"),
        nullable=False,
    ),
    Column("chunking_profile", String(100), nullable=False),
    Column("chunk_index", Integer, nullable=False),
    Column("chunk_text", Text),
    Column("text_storage_uri", Text),
    Column("page_start", Integer),
    Column("page_end", Integer),
    Column("section_path", Text),
    Column("metadata", JSON, nullable=False, default=dict),
    Column("vector_record_id", String(300)),
    Column("embedding", Vector(EMBEDDING_DIMENSIONS), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("document_version_id", "chunking_profile", "chunk_index"),
    CheckConstraint("chunk_index >= 0"),
    CheckConstraint("chunk_text IS NOT NULL OR text_storage_uri IS NOT NULL"),
    CheckConstraint("page_start IS NULL OR page_start > 0"),
    CheckConstraint("page_end IS NULL OR page_start IS NULL OR page_end >= page_start"),
)

Index("idx_portfolio_holdings_portfolio", portfolio_holdings.c.portfolio_id)
Index("idx_risk_logs_asset", asset_risk_logs.c.asset_name)
Index("idx_escalations_portfolio_created", escalations.c.portfolio_id, escalations.c.created_at)
Index("idx_ingestion_runs_created", ingestion_runs.c.created_at)
Index(
    "idx_query_workflow_events_query",
    query_workflow_events.c.query_id,
    query_workflow_events.c.created_at,
)
Index("idx_document_versions_document", document_versions.c.document_id)
Index("idx_document_chunks_version", document_chunks.c.document_version_id)


def create_schema(engine: Engine) -> None:
    """Create missing FRIIS tables; intended for local setup, not production migrations."""
    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
    metadata.create_all(engine)
    # Additive upgrades for databases created before query scope snapshots.
    if engine.dialect.name == "sqlite":
        with engine.begin() as connection:
            columns = {
                row["name"]
                for row in connection.exec_driver_sql(
                    "PRAGMA table_info(query_requests)"
                ).mappings()
            }
            if "conversation_context" not in columns:
                connection.exec_driver_sql(
                    "ALTER TABLE query_requests ADD COLUMN conversation_context JSON NOT NULL DEFAULT '[]'"
                )
            if "authorized_portfolio_ids" not in columns:
                connection.exec_driver_sql(
                    "ALTER TABLE query_requests ADD COLUMN authorized_portfolio_ids JSON NOT NULL DEFAULT '[]'"
                )
            if "all_portfolios_access" not in columns:
                connection.exec_driver_sql(
                    "ALTER TABLE query_requests ADD COLUMN all_portfolios_access BOOLEAN NOT NULL DEFAULT 0"
                )
            if "principal_roles" not in columns:
                connection.exec_driver_sql(
                    "ALTER TABLE query_requests ADD COLUMN principal_roles JSON NOT NULL DEFAULT '[]'"
                )
    elif engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "ALTER TABLE query_requests ADD COLUMN IF NOT EXISTS conversation_context JSON NOT NULL DEFAULT '[]'::json"
            )
            connection.exec_driver_sql(
                "ALTER TABLE query_requests ADD COLUMN IF NOT EXISTS authorized_portfolio_ids JSON NOT NULL DEFAULT '[]'::json"
            )
            connection.exec_driver_sql(
                "ALTER TABLE query_requests ADD COLUMN IF NOT EXISTS all_portfolios_access BOOLEAN NOT NULL DEFAULT FALSE"
            )
            connection.exec_driver_sql(
                "ALTER TABLE query_requests ADD COLUMN IF NOT EXISTS principal_roles JSON NOT NULL DEFAULT '[]'::json"
            )
    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.exec_driver_sql(
                """
                CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding
                ON document_chunks USING hnsw (embedding vector_cosine_ops)
                """
            )
