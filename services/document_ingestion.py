"""PDF-to-pgvector ingestion worker for the approved FRIIS source set."""

import asyncio
import logging
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any
import re
import unicodedata
from uuid import NAMESPACE_URL, uuid5

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.engine import Engine

from schemas import IngestionStatus
from services.database import (
    EMBEDDING_DIMENSIONS,
    document_chunks,
    document_versions,
    ingestion_run_items,
    ingestion_runs,
    source_documents,
)
from services.embeddings import EmbeddingProvider, EmbeddingProviderError
from services.multimodal_processing import (
    MultimodalProcessingError,
    extract_pdf_supplemental_documents,
)
from services.langfuse_tracing import observation

logger = logging.getLogger(__name__)

PROJECT_PDF_NAMES = (
    "01_Investment_Strategy_Portfolio_Allocation_Guide.pdf",
    "02_Risk_Management_Exposure_Policy.pdf",
    "03_Regulatory_Compliance_Financial_Governance_Policy.pdf",
    "04_Market_Analysis_Investment_Research_Guide.pdf",
    "05_Portfolio_Monitoring_Performance_Evaluation_Guide.pdf",
    "06_Basel_III_Risk_Management_Summary.pdf",
    "07_Investment_Risk_Assessment_Framework.pdf",
)
PROJECT_PDF_SOURCE_KEYS = frozenset(
    f"project-pdf-{index:02d}" for index in range(1, len(PROJECT_PDF_NAMES) + 1)
)
class DocumentIngestionError(RuntimeError):
    """Raised for a source-level validation, extraction, or embedding failure."""

    def __init__(self, source_id: str, message: str, code: str) -> None:
        super().__init__(message)
        self.source_id = source_id
        self.code = code


@dataclass(frozen=True)
class IngestionSummary:
    ingestion_id: str
    status: IngestionStatus
    succeeded: int
    failed: int


def register_project_pdf_sources(engine: Engine, documents_root: Path) -> list[str]:
    """Register only the seven known project PDFs as approved ingestible sources."""
    root = documents_root.resolve()
    registered: list[str] = []
    with engine.begin() as connection:
        for index, filename in enumerate(PROJECT_PDF_NAMES, start=1):
            path = (root / filename).resolve()
            if not path.is_relative_to(root) or not path.is_file():
                raise FileNotFoundError(
                    f"Expected project PDF is missing or outside the documents root: {filename}"
                )
            source_id = f"project-pdf-{index:02d}"
            existing = connection.execute(
                select(source_documents.c.document_id).where(
                    source_documents.c.source_key == source_id
                )
            ).scalar_one_or_none()
            now = _utcnow()
            if existing is None:
                connection.execute(
                    insert(source_documents).values(
                        document_id=str(uuid5(NAMESPACE_URL, f"friis-source:{source_id}")),
                        source_key=source_id,
                        title=path.stem.replace("_", " "),
                        source_type="policy",
                        source_uri=path.relative_to(root.parent).as_posix(),
                        owner="FRIIS project source set",
                        access_classification="internal",
                        approved=True,
                        enabled=True,
                        created_at=now,
                        updated_at=now,
                    )
                )
            else:
                connection.execute(
                    update(source_documents)
                    .where(source_documents.c.source_key == source_id)
                    .values(
                        title=path.stem.replace("_", " "),
                        source_uri=path.relative_to(root.parent).as_posix(),
                        approved=True,
                        enabled=True,
                        updated_at=now,
                    )
                )
            registered.append(source_id)
    return registered


class DocumentIngestionWorker:
    def __init__(
        self,
        engine: Engine,
        embedder: EmbeddingProvider,
        documents_root: Path,
        *,
        poll_seconds: float = 2.0,
        chunk_size: int = 1200,
        chunk_overlap: int = 200,
        embedding_batch_size: int = 32,
    ) -> None:
        if poll_seconds <= 0 or chunk_size <= 0 or embedding_batch_size <= 0:
            raise ValueError("Worker polling, chunk, and batch sizes must be positive")
        if chunk_overlap < 0 or chunk_overlap >= chunk_size:
            raise ValueError("Chunk overlap must be non-negative and smaller than chunk size")
        self.engine = engine
        self.embedder = embedder
        self.documents_root = documents_root.resolve()
        self.poll_seconds = poll_seconds
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.embedding_batch_size = embedding_batch_size
        self.chunking_profile = f"friis-pdf-v2-{chunk_size}-overlap-{chunk_overlap}"
        self._stop = asyncio.Event()
        if embedder.dimensions != EMBEDDING_DIMENSIONS:
            raise ValueError("The pgvector schema requires 1536-dimensional embeddings")

    async def run_forever(self) -> None:
        while not self._stop.is_set():
            processed = await self.run_once()
            if not processed:
                try:
                    await asyncio.wait_for(
                        self._stop.wait(), timeout=self.poll_seconds
                    )
                except TimeoutError:
                    continue

    def stop(self) -> None:
        self._stop.set()

    async def run_once(self) -> IngestionSummary | None:
        run = await asyncio.to_thread(self._claim_next_run)
        if run is None:
            return None

        logger.info(
            "Approved document ingestion run started",
            extra={
                "event": "document_ingestion.run_started",
                "ingestion_id": run["ingestion_id"],
                "source_count": len(run["source_ids"]),
            },
        )

        errors: list[str] = []
        succeeded = 0
        failed = 0
        for source_id in run["source_ids"]:
            try:
                with observation(
                    name="approved-document-ingestion",
                    as_type="chain",
                    input={"content_captured": False},
                    metadata={
                        "ingestion_id": run["ingestion_id"],
                        "source_id": source_id,
                    },
                ) as trace:
                    await self._process_source(run["ingestion_id"], source_id)
                    if trace is not None:
                        trace.update(output={"status": "succeeded"})
            except DocumentIngestionError as exc:
                failed += 1
                errors.append(f"{exc.source_id}: {exc}")
                logger.warning(
                    "Document ingestion source failed",
                    extra={
                        "ingestion_id": run["ingestion_id"],
                        "source_id": exc.source_id,
                        "error_code": exc.code,
                    },
                )
                await asyncio.to_thread(
                    self._mark_source_failed,
                    run["ingestion_id"],
                    exc.source_id,
                    exc.code,
                    str(exc),
                )
            else:
                succeeded += 1

        final_status = (
            IngestionStatus.SUCCEEDED
            if failed == 0
            else IngestionStatus.PARTIAL
            if succeeded > 0
            else IngestionStatus.FAILED
        )
        await asyncio.to_thread(
            self._finish_run,
            run["ingestion_id"],
            final_status,
            errors,
        )
        logger.info(
            "Approved document ingestion run completed",
            extra={
                "event": "document_ingestion.run_completed",
                "ingestion_id": run["ingestion_id"],
                "query_status": final_status.value,
                "source_count": len(run["source_ids"]),
                "succeeded_count": succeeded,
                "failed_count": failed,
            },
        )
        return IngestionSummary(
            ingestion_id=run["ingestion_id"],
            status=final_status,
            succeeded=succeeded,
            failed=failed,
        )

    def _claim_next_run(self) -> dict[str, Any] | None:
        now = _utcnow()
        with self.engine.begin() as connection:
            statement = (
                select(ingestion_runs)
                .where(
                    ingestion_runs.c.status == IngestionStatus.QUEUED.value,
                    ingestion_runs.c.source_type == "documents",
                )
                .order_by(ingestion_runs.c.created_at)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            row = connection.execute(statement).mappings().first()
            if row is None:
                return None
            connection.execute(
                update(ingestion_runs)
                .where(ingestion_runs.c.ingestion_id == row["ingestion_id"])
                .values(status=IngestionStatus.RUNNING.value, started_at=now)
            )
            return dict(row)

    async def _process_source(self, ingestion_id: str, source_id: str) -> None:
        source = await asyncio.to_thread(self._get_approved_source, source_id)
        if source is None or source["source_key"] not in PROJECT_PDF_SOURCE_KEYS:
            raise DocumentIngestionError(
                source_id,
                "Source is not in the approved project PDF registry.",
                "source_not_approved",
            )
        path = self._resolve_source_path(source["source_uri"], source_id)
        try:
            content = await asyncio.to_thread(path.read_bytes)
        except OSError as exc:
            raise DocumentIngestionError(
                source_id,
                "Source file could not be read.",
                "source_read_error",
            ) from exc
        digest = sha256(content).hexdigest()
        pages = await asyncio.to_thread(_extract_pdf_pages, path, source_id)
        try:
            supplemental_documents = await asyncio.to_thread(
                extract_pdf_supplemental_documents, path
            )
        except MultimodalProcessingError as exc:
            raise DocumentIngestionError(
                source_id,
                str(exc),
                "multimodal_processing_failed",
            ) from exc
        chunks = _chunk_multimodal_content(
            pages,
            supplemental_documents,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )
        if not chunks:
            raise DocumentIngestionError(
                source_id, "PDF contains no extractable text.", "empty_document"
            )

        version_id = await asyncio.to_thread(
            self._get_or_create_version,
            source,
            digest,
        )
        await asyncio.to_thread(
            self._start_run_item,
            ingestion_id,
            source_id,
            version_id,
        )
        existing_count = await asyncio.to_thread(
            self._existing_chunk_count, version_id
        )
        if existing_count == len(chunks):
            await asyncio.to_thread(
                self._mark_existing_chunks_indexed,
                ingestion_id,
                version_id,
                existing_count,
            )
            logger.info(
                "Approved document version already indexed; skipping embeddings",
                extra={
                    "event": "document_ingestion.unchanged_skipped",
                    "ingestion_id": ingestion_id,
                    "source_id": source_id,
                    "document_version_id": version_id,
                    "chunk_count": existing_count,
                },
            )
            return
        texts = [text for text, _, _ in chunks]
        vectors: list[list[float]] = []
        try:
            for start in range(0, len(texts), self.embedding_batch_size):
                vectors.extend(
                    await self.embedder.embed(
                        texts[start : start + self.embedding_batch_size]
                    )
                )
        except EmbeddingProviderError as exc:
            raise DocumentIngestionError(
                source_id,
                "Embedding provider failed to process the source.",
                "embedding_failed",
            ) from exc
        if len(vectors) != len(chunks):
            raise DocumentIngestionError(
                source_id,
                "Embedding provider returned an incomplete batch.",
                "embedding_count_mismatch",
            )
        if any(
            len(vector) != EMBEDDING_DIMENSIONS
            or not all(math.isfinite(value) for value in vector)
            for vector in vectors
        ):
            raise DocumentIngestionError(
                source_id,
                "Embedding provider returned an invalid vector.",
                "invalid_embedding",
            )
        await asyncio.to_thread(
            self._store_chunks,
            ingestion_id,
            source_id,
            version_id,
            chunks,
            vectors,
        )

    def _get_approved_source(self, source_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(source_documents).where(
                    source_documents.c.approved.is_(True),
                    source_documents.c.enabled.is_(True),
                    (
                        (source_documents.c.source_key == source_id)
                        | (source_documents.c.document_id == source_id)
                    ),
                )
            ).mappings().first()
            return dict(row) if row is not None else None

    def _resolve_source_path(self, source_uri: str, source_id: str) -> Path:
        relative = Path(source_uri)
        if relative.is_absolute() or relative.suffix.lower() != ".pdf":
            raise DocumentIngestionError(
                source_id,
                "Registered source must be a relative PDF path.",
                "invalid_source_uri",
            )
        path = (self.documents_root.parent / relative).resolve()
        if not path.is_relative_to(self.documents_root) or not path.is_file():
            raise DocumentIngestionError(
                source_id,
                "Registered PDF is missing or outside the approved documents root.",
                "source_path_not_allowed",
            )
        return path

    def _get_or_create_version(
        self,
        source: dict[str, Any],
        digest: str,
    ) -> str:
        with self.engine.begin() as connection:
            existing = connection.execute(
                select(document_versions.c.document_version_id).where(
                    document_versions.c.document_id == source["document_id"],
                    document_versions.c.content_sha256 == digest,
                )
            ).scalar_one_or_none()
            if existing is not None:
                return existing
            version_id = str(
                uuid5(
                    NAMESPACE_URL,
                    f"friis-version:{source['document_id']}:{digest}",
                )
            )
            connection.execute(
                insert(document_versions).values(
                    document_version_id=version_id,
                    document_id=source["document_id"],
                    version_label=f"sha256-{digest[:16]}",
                    content_sha256=digest,
                    content_type="application/pdf",
                    storage_uri=source["source_uri"],
                    published_at=None,
                    effective_from=None,
                    effective_to=None,
                    validation_status="pending",
                    created_at=_utcnow(),
                )
            )
            return version_id

    def _existing_chunk_count(self, version_id: str) -> int:
        with self.engine.connect() as connection:
            return int(
                connection.execute(
                select(func.count()).select_from(document_chunks).where(
                        document_chunks.c.document_version_id == version_id,
                        document_chunks.c.chunking_profile == self.chunking_profile,
                    )
                ).scalar_one()
            )

    def _mark_existing_chunks_indexed(
        self, ingestion_id: str, version_id: str, chunk_count: int
    ) -> None:
        now = _utcnow()
        with self.engine.begin() as connection:
            connection.execute(
                update(ingestion_run_items)
                .where(
                    ingestion_run_items.c.ingestion_id == ingestion_id,
                    ingestion_run_items.c.document_version_id == version_id,
                )
                .values(
                    status="succeeded",
                    records_processed=1,
                    chunks_created=chunk_count,
                    chunks_indexed=chunk_count,
                    error_code=None,
                    error_message=None,
                    completed_at=now,
                )
            )
            document_id = connection.execute(
                select(document_versions.c.document_id).where(
                    document_versions.c.document_version_id == version_id
                )
            ).scalar_one()
            connection.execute(
                update(document_versions)
                .where(document_versions.c.document_id == document_id)
                .where(document_versions.c.document_version_id != version_id)
                .values(validation_status="superseded")
            )
            connection.execute(
                update(document_versions)
                .where(document_versions.c.document_version_id == version_id)
                .values(validation_status="valid")
            )

    def _start_run_item(
        self, ingestion_id: str, source_id: str, version_id: str
    ) -> None:
        now = _utcnow()
        with self.engine.begin() as connection:
            existing = connection.execute(
                select(ingestion_run_items.c.ingestion_id).where(
                    ingestion_run_items.c.ingestion_id == ingestion_id,
                    ingestion_run_items.c.document_version_id == version_id,
                )
            ).first()
            if existing is None:
                connection.execute(
                    insert(ingestion_run_items).values(
                        ingestion_id=ingestion_id,
                        document_version_id=version_id,
                        status="embedding",
                        records_processed=0,
                        chunks_created=0,
                        chunks_indexed=0,
                        started_at=now,
                    )
                )
            else:
                connection.execute(
                    update(ingestion_run_items)
                    .where(
                        ingestion_run_items.c.ingestion_id == ingestion_id,
                        ingestion_run_items.c.document_version_id == version_id,
                    )
                    .values(
                        status="embedding",
                        error_code=None,
                        error_message=None,
                        started_at=now,
                        completed_at=None,
                    )
                )

    def _store_chunks(
        self,
        ingestion_id: str,
        source_id: str,
        version_id: str,
        chunks: list[tuple[str, int, str]],
        vectors: list[list[float]],
    ) -> None:
        now = _utcnow()
        with self.engine.connect() as connection:
            content_digest = connection.execute(
                select(document_versions.c.content_sha256).where(
                    document_versions.c.document_version_id == version_id
                )
            ).scalar_one()
        rows = [
            {
                "chunk_id": str(
                    uuid5(
                        NAMESPACE_URL,
                        f"friis:{version_id}:{self.chunking_profile}:{index}:{sha256(text.encode('utf-8')).hexdigest()}",
                    )
                ),
                "document_version_id": version_id,
                "chunking_profile": self.chunking_profile,
                "chunk_index": index,
                "chunk_text": text,
                "text_storage_uri": None,
                "page_start": page_number,
                "page_end": page_number,
                "section_path": _infer_section_path(text),
                "metadata": {
                    "source_id": source_id,
                    "chunk_index": index,
                    "chunking_profile": self.chunking_profile,
                    "document_version_id": version_id,
                    "content_sha256": content_digest,
                    "page_number": page_number,
                    "section_path": _infer_section_path(text),
                    "ingestion_pipeline_version": "friis-approved-pdf-v2",
                },
                "vector_record_id": None,
                "embedding": vector,
                "created_at": now,
            }
            for index, ((text, page_number, content_type), vector) in enumerate(
                zip(chunks, vectors, strict=True)
            )
        ]
        for row, (_, _, content_type) in zip(rows, chunks, strict=True):
            row["metadata"]["content_type"] = content_type
        with self.engine.begin() as connection:
            connection.execute(
                delete(document_chunks).where(
                    document_chunks.c.document_version_id == version_id,
                    document_chunks.c.chunking_profile == self.chunking_profile,
                )
            )
            connection.execute(
                delete(document_chunks).where(
                    document_chunks.c.document_version_id == version_id,
                    document_chunks.c.chunking_profile != self.chunking_profile,
                )
            )
            connection.execute(insert(document_chunks), rows)
            document_id = connection.execute(
                select(document_versions.c.document_id).where(
                    document_versions.c.document_version_id == version_id
                )
            ).scalar_one()
            connection.execute(
                update(document_versions)
                .where(document_versions.c.document_id == document_id)
                .where(document_versions.c.document_version_id != version_id)
                .values(validation_status="superseded")
            )
            connection.execute(
                update(document_versions)
                .where(document_versions.c.document_version_id == version_id)
                .values(validation_status="valid")
            )
            connection.execute(
                update(ingestion_run_items)
                .where(
                    ingestion_run_items.c.ingestion_id == ingestion_id,
                    ingestion_run_items.c.document_version_id == version_id,
                )
                .values(
                    status="succeeded",
                    records_processed=1,
                    chunks_created=len(rows),
                    chunks_indexed=len(rows),
                    error_code=None,
                    error_message=None,
                    completed_at=now,
                )
            )

    def _mark_source_failed(
        self, ingestion_id: str, source_id: str, code: str, message: str
    ) -> None:
        now = _utcnow()
        with self.engine.begin() as connection:
            version_ids = select(document_versions.c.document_version_id).join(
                source_documents,
                source_documents.c.document_id
                == document_versions.c.document_id,
            ).where(
                (source_documents.c.source_key == source_id)
                | (source_documents.c.document_id == source_id)
            )
            connection.execute(
                update(ingestion_run_items)
                .where(
                    ingestion_run_items.c.ingestion_id == ingestion_id,
                    ingestion_run_items.c.document_version_id.in_(version_ids),
                )
                .values(
                    status="failed",
                    error_code=code,
                    error_message=message,
                    completed_at=now,
                )
            )
            run = connection.execute(
                select(ingestion_runs.c.validation_errors).where(
                    ingestion_runs.c.ingestion_id == ingestion_id
                )
            ).scalar_one()
            errors = list(run or [])
            errors.append(f"{source_id}: {message}")
            connection.execute(
                update(ingestion_runs)
                .where(ingestion_runs.c.ingestion_id == ingestion_id)
                .values(validation_errors=errors)
            )

    def _finish_run(
        self,
        ingestion_id: str,
        final_status: IngestionStatus,
        errors: list[str],
    ) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                update(ingestion_runs)
                .where(ingestion_runs.c.ingestion_id == ingestion_id)
                .values(
                    status=final_status.value,
                    completed_at=_utcnow(),
                    validation_errors=errors,
                )
            )

def _extract_pdf_pages(file_path: Path, source_id: str) -> list[tuple[str, int]]:
    try:
        reader = PdfReader(str(file_path))
        if reader.is_encrypted:
            raise DocumentIngestionError(
                source_id, "Encrypted PDFs are not supported.", "encrypted_pdf"
            )
        documents = PyPDFLoader(str(file_path)).load()
        pages: list[tuple[str, int]] = []
        for document in documents:
            text = _normalize_extracted_text(document.page_content)
            if text:
                page_number = int(document.metadata.get("page", 0)) + 1
                pages.append((text, page_number))
    except DocumentIngestionError:
        raise
    except OSError as exc:
        raise DocumentIngestionError(
            source_id, "Source file could not be read.", "source_read_error"
        ) from exc
    except (PdfReadError, ValueError) as exc:
        raise DocumentIngestionError(
            source_id, "PDF could not be parsed or extracted.", "invalid_pdf"
        ) from exc
    return pages


def _chunk_pages(
    pages: list[tuple[str, int]],
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> list[tuple[str, int]]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n### ", "\n## ", "\n# ", "\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )
    documents = [
        Document(page_content=text, metadata={"page": page_number})
        for text, page_number in pages
    ]
    return [
        (chunk.page_content, int(chunk.metadata["page"]))
        for chunk in splitter.split_documents(documents)
    ]


def _chunk_multimodal_content(
    pages: list[tuple[str, int]],
    supplemental_documents: list[Document],
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> list[tuple[str, int, str]]:
    chunks = [
        (text, page_number, "text")
        for text, page_number in _chunk_pages(
            pages,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
    ]
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n### ", "\n## ", "\n# ", "\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )
    for document in supplemental_documents:
        page_number = int(document.metadata["page"])
        content_type = str(document.metadata["content_type"])
        chunks.extend(
            (chunk.page_content, page_number, content_type)
            for chunk in splitter.split_documents([document])
        )
    return chunks


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _normalize_extracted_text(text: str) -> str:
    """Strip extraction artifacts without flattening paragraph boundaries."""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\x00", "").replace("\u200b", "").replace("\ufeff", "")
    text = text.replace("\u00a0", " ").replace("\u00ad", "")
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _infer_section_path(text: str) -> str | None:
    for line in text.splitlines():
        heading = re.match(r"^\s*#{1,6}\s+(.+?)\s*#*\s*$", line)
        if heading:
            return heading.group(1).strip()
        normalized = line.strip()
        if 4 <= len(normalized) <= 100 and normalized.upper() == normalized:
            if any(character.isalpha() for character in normalized):
                return normalized
    return None
