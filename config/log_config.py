import json
import logging
import os
import sys
from pathlib import Path

LOG_FILE_PATH = Path(__file__).resolve().parents[1] / "logger.txt"
CONTEXT_FIELDS = (
    "event",
    "uploaded_filename",
    "content_type",
    "file_extension",
    "upload_size_bytes",
    "max_upload_size_bytes",
    "chunk_size",
    "chunk_overlap",
    "reason",
    "error_type",
    "file_type",
    "source_documents",
    "total_chunks",
    "collection_name",
    "storage_table",
    "processing_time_seconds",
    "request_time_seconds",
    "query_id",
    "trace_id",
    "query_status",
    "user_query",
    "portfolio_id",
    "agent_name",
    "intent",
    "specialists",
    "evidence_count",
    "data_gap_count",
    "vector_result_count",
    "keyword_result_count",
    "fused_result_count",
    "duration_seconds",
    "workflow_event",
    "stored_chunk_count",
    "provider_status_code",
    "provider_error_code",
    "provider_error_param",
    "http_method",
    "http_route",
    "http_status_code",
    "task_id",
    "attempt",
    "accepted",
    "correction_mode",
    "scope_unchanged",
    "from",
    "to",
    "specialist_count",
    "citation_count",
    "route",
    "ingestion_id",
    "source_id",
    "error_code",
    "chunk_count",
    "source_count",
    "succeeded_count",
    "failed_count",
    "escalation_id",
    "review_status",
    "review_outcome",
)


class ContextFormatter(logging.Formatter):
    """Append approved structured context fields to each log message."""

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        context = {
            field: getattr(record, field)
            for field in CONTEXT_FIELDS
            if hasattr(record, field) and getattr(record, field) is not None
        }
        if context:
            message = f"{message} | {json.dumps(context, sort_keys=True, default=str)}"
        return message


def setup_logging(level: int = logging.INFO) -> None:
    """
    Configure application logging to stdout and, outside Vercel, the log file.
    
    Args:
        level: Logging level (default: INFO)
    """
    formatter = ContextFormatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    handlers: list[logging.Handler] = [console_handler]
    if os.getenv("VERCEL") != "1":
        file_handler = logging.FileHandler(LOG_FILE_PATH, encoding="utf-8")
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    logging.basicConfig(
        level=level,
        handlers=handlers,
        force=True,
    )

    # Suppress noisy loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("watchfiles").setLevel(logging.WARNING)
    logging.getLogger("watchfiles.main").setLevel(logging.WARNING)
