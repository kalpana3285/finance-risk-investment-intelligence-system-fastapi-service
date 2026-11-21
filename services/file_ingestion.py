"""Synchronous LangChain document ingestion for uploaded files."""

import logging
import math
import mimetypes
import os
import re
import time
import unicodedata
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

from langchain_community.document_loaders import BSHTMLLoader, PyPDFLoader, TextLoader
from langchain_openai import AzureOpenAIEmbeddings
from langchain_postgres import PGVector
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy import delete, insert, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.engine import make_url

from config.runtime import RuntimeSettings
from schemas.api import IngestionStatus
from services.database import (
    EMBEDDING_DIMENSIONS,
    document_chunks,
    document_versions,
    ingestion_run_items,
    ingestion_runs,
    source_documents,
)
from services.multimodal_processing import (
    extract_pdf_supplemental_documents,
    visual_processing_profile,
)
from services.langfuse_tracing import observation
from services.ingestion_utils import (
    chunk_text_digest,
    load_reusable_chunk_vectors,
    remove_repeated_page_marginalia,
    section_path_at_offset,
)

SUPPORTED_FILE_TYPES = {
    ".pdf": "pdf",
    ".txt": "text",
    ".md": "text",
    ".markdown": "text",
    ".html": "html",
    ".htm": "html",
}
DOCUMENT_CHUNKS_TABLE = "document_chunks"
INGESTION_PIPELINE_VERSION = "friis-upload-v3"

logger = logging.getLogger(__name__)


def process_and_store_file(
    file_path: Path,
    chunk_size: int = 1000,
    chunk_overlap: int = 100,
    *,
    filename: str | None = None,
    engine: Engine | None = None,
    owner_subject: str | None = None,
    ingestion_id: str | None = None,
) -> dict[str, object]:
    """Load, split, embed, and store an upload in FRIIS's searchable tables."""
    started_at = time.perf_counter()
    file_type = SUPPORTED_FILE_TYPES.get(file_path.suffix.lower())
    if file_type is None:
        raise ValueError(f"Unsupported file type: {file_path.suffix}")
    if not file_path.is_file():
        raise FileNotFoundError(f"Input file does not exist: {file_path}")
    if chunk_size < 1 or chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("Chunk overlap must be non-negative and smaller than chunk size.")

    original_filename = filename or file_path.name
    run_id = ingestion_id or str(uuid4())
    with observation(
        name="load-document",
        as_type="span",
        input={"file_type": file_type, "content_captured": False},
        metadata={"file_type": file_type},
    ) as load_trace:
        if file_type == "pdf":
            documents = PyPDFLoader(str(file_path)).load()
            cleaned_pages = remove_repeated_page_marginalia(
                [document.page_content for document in documents]
            )
            for document, page_text in zip(
                documents, cleaned_pages, strict=True
            ):
                document.page_content = page_text
        elif file_type == "html":
            documents = BSHTMLLoader(str(file_path)).load()
        else:
            documents = TextLoader(str(file_path), encoding="utf-8").load()
        if load_trace is not None:
            load_trace.update(output={"page_or_document_count": len(documents)})

    original_document_count = len(documents)
    cleaned_documents = []
    for document in documents:
        document.page_content = _clean_text(document.page_content)
        if document.page_content:
            cleaned_documents.append(document)
    documents = cleaned_documents
    source_document_count = len(documents)
    supplemental_documents = (
        extract_pdf_supplemental_documents(file_path)
        if file_type == "pdf"
        else []
    )
    for document in supplemental_documents:
        document.page_content = _clean_text(document.page_content)
    documents.extend(
        document for document in supplemental_documents if document.page_content
    )
    if not documents:
        raise ValueError(
            "The uploaded document contains no extractable text, tables, or visuals."
        )

    for document in documents:
        document.metadata.update(
            {
                "source_file": original_filename,
                "file_type": file_type,
                "content_type": document.metadata.get("content_type", "text"),
            }
        )
    for document_index, document in enumerate(documents):
        document.metadata["_ingestion_document_index"] = document_index

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n### ", "\n## ", "\n# ", "\n\n", "\n", ". ", " ", ""],
        length_function=len,
        add_start_index=True,
    )
    with observation(
        name="chunk-document",
        as_type="span",
        input={"document_count": len(documents), "content_captured": False},
        metadata={"chunk_size": chunk_size, "chunk_overlap": chunk_overlap},
    ) as chunk_trace:
        chunks = splitter.split_documents(documents)
        if chunk_trace is not None:
            chunk_trace.update(
                output={
                    "chunk_count": len(chunks),
                    "filtered_document_count": original_document_count - source_document_count,
                }
            )
    if not chunks:
        raise ValueError("The uploaded document produced no text chunks.")

    settings = RuntimeSettings.from_environment()
    if not all(
        (
            settings.azure_openai_endpoint,
            settings.azure_openai_api_key,
            settings.azure_openai_api_version,
            settings.azure_openai_embedding_deployment,
        )
    ):
        raise RuntimeError("Azure OpenAI embedding settings are required.")
    if make_url(settings.database_url).drivername not in {
        "postgres",
        "postgresql",
        "postgresql+psycopg",
        "postgresql+psycopg2",
    }:
        raise RuntimeError("Document ingestion requires a PostgreSQL database URL.")

    content_digest = sha256(file_path.read_bytes()).hexdigest()
    normalized_name = unicodedata.normalize(
        "NFKC", Path(original_filename).name
    ).strip().casefold()
    source_key = f"uploaded-{sha256(normalized_name.encode('utf-8')).hexdigest()[:32]}"
    version_namespace = f"friis-upload:{source_key}:{content_digest}"
    vision_profile = (
        visual_processing_profile() if file_type == "pdf" else "not_applicable"
    )
    profile_config = (
        f"{INGESTION_PIPELINE_VERSION}|{chunk_size}|{chunk_overlap}|"
        f"{settings.azure_openai_embedding_deployment}|"
        f"{settings.azure_openai_api_version}|{vision_profile}"
    )
    profile_digest = sha256(profile_config.encode("utf-8")).hexdigest()[:16]
    profile = (
        f"{INGESTION_PIPELINE_VERSION}-{chunk_size}-{chunk_overlap}-{profile_digest}"
    )
    chunk_ids = [
        str(
            uuid5(
                NAMESPACE_URL,
                f"{version_namespace}:{profile}:{index}:{chunk_text_digest(chunk.page_content)}",
            )
        )
        for index, chunk in enumerate(chunks)
    ]
    for index, (chunk, chunk_id) in enumerate(zip(chunks, chunk_ids, strict=True)):
        document_index = chunk.metadata.pop("_ingestion_document_index", None)
        start_index = chunk.metadata.get("start_index")
        source_text = (
            documents[document_index].page_content
            if isinstance(document_index, int)
            and 0 <= document_index < len(documents)
            else ""
        )
        section_path = (
            section_path_at_offset(source_text, start_index)
            if source_text and isinstance(start_index, int)
            else _find_section_path(chunk.page_content, chunk.metadata)
        )
        chunk.metadata.update(
            {
                "chunk_id": chunk_id,
                "chunk_index": index,
                "section_path": section_path,
                "chunking_profile": profile,
                "content_sha256": content_digest,
                "embedding_deployment": settings.azure_openai_embedding_deployment,
                "embedding_api_version": settings.azure_openai_api_version,
                "vision_profile": vision_profile,
                "ingestion_pipeline_version": INGESTION_PIPELINE_VERSION,
            }
        )

    embeddings = AzureOpenAIEmbeddings(
        azure_endpoint=settings.azure_openai_endpoint,
        azure_deployment=settings.azure_openai_embedding_deployment,
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
    )
    collection_name = (
        os.getenv("FRIIS_DOCUMENT_COLLECTION", "friis_uploaded_documents")
        if engine is None
        else None
    )
    storage_table = (
        "langchain_pg_embedding" if engine is None else DOCUMENT_CHUNKS_TABLE
    )
    storage_started_at = time.perf_counter()
    document_id: str | None = None
    version_id: str | None = None
    embedded_chunk_count = len(chunks)
    reused_embedding_count = 0
    if engine is not None:
        document_id, version_id = _register_uploaded_version(
            engine,
            source_key=source_key,
            filename=original_filename,
            file_type=file_type,
            content_digest=content_digest,
            owner_subject=owner_subject,
        )
        existing_ids = _existing_chunk_ids(engine, version_id, profile)
        if existing_ids == chunk_ids:
            logger.info(
                "Document version already indexed; skipping unchanged upload",
                extra={
                    "event": "document_ingestion.unchanged_skipped",
                    "source_id": source_key,
                    "document_version_id": version_id,
                    "chunking_profile": profile,
                    "stored_chunk_count": len(existing_ids),
                },
            )
            _activate_version(engine, document_id, version_id)
            _start_upload_run(
                engine, run_id, source_key, version_id, owner_subject
            )
            _finish_upload_run(engine, run_id, len(existing_ids))
            result = _ingestion_result(
                original_filename,
                file_type,
                chunks,
                supplemental_documents,
                source_document_count,
                existing_ids,
                time.perf_counter() - started_at,
            )
            result["ingestion_id"] = run_id
            return result
        _start_upload_run(engine, run_id, source_key, version_id, owner_subject)
    logger.info(
        "Starting document chunk storage",
        extra={
            "event": "document_ingestion.storage_started",
            "storage_table": storage_table,
            "total_chunks": len(chunks),
            **({"collection_name": collection_name} if collection_name else {}),
        },
    )
    try:
        with observation(
            name="embed-document-chunks",
            as_type="span",
            input={"chunk_count": len(chunks), "content_captured": False},
            metadata={
                "embedding_dimensions": EMBEDDING_DIMENSIONS,
                "embedding_deployment": settings.azure_openai_embedding_deployment,
                "embedding_api_version": settings.azure_openai_api_version,
                "vision_profile": vision_profile,
                "chunking_profile": profile,
            },
        ) as embedding_trace:
            if engine is None:
                # Legacy helper mode; the Knowledge Operations API supplies the
                # shared engine and stores in the normalized document tables.
                vectorstore = PGVector(
                    embeddings=embeddings,
                    collection_name=collection_name,
                    connection=settings.database_url,
                )
                stored_ids = vectorstore.add_documents(chunks, ids=chunk_ids)
                vectors = None
            else:
                assert document_id is not None
                reusable_vectors = load_reusable_chunk_vectors(
                    engine, document_id, profile
                )
                vector_slots: list[list[float] | None] = [None] * len(chunks)
                missing_by_digest: dict[str, tuple[str, list[int]]] = {}
                reused_embedding_count = 0
                for index, chunk in enumerate(chunks):
                    digest = chunk_text_digest(chunk.page_content)
                    existing_vector = reusable_vectors.get(digest)
                    if existing_vector is not None:
                        vector_slots[index] = existing_vector
                        reused_embedding_count += 1
                    else:
                        if digest not in missing_by_digest:
                            missing_by_digest[digest] = (chunk.page_content, [])
                        missing_by_digest[digest][1].append(index)
                missing_digests = list(missing_by_digest)
                fresh_vectors = (
                    embeddings.embed_documents(
                        [missing_by_digest[digest][0] for digest in missing_digests]
                    )
                    if missing_digests
                    else []
                )
                if len(fresh_vectors) != len(missing_digests) or any(
                    len(vector) != EMBEDDING_DIMENSIONS
                    or not all(math.isfinite(value) for value in vector)
                    for vector in fresh_vectors
                ):
                    raise RuntimeError("Embedding provider returned invalid vectors.")
                for digest, vector in zip(
                    missing_digests, fresh_vectors, strict=True
                ):
                    for index in missing_by_digest[digest][1]:
                        vector_slots[index] = vector
                vectors = [vector for vector in vector_slots if vector is not None]
                if len(vectors) != len(chunks):
                    raise RuntimeError("Embedding reuse returned an incomplete vector set.")
                embedded_chunk_count = len(missing_digests)
                logger.info(
                    "Document embeddings prepared",
                    extra={
                        "event": "document_ingestion.embeddings_prepared",
                        "source_id": source_key,
                        "chunk_count": len(chunks),
                        "reused_embedding_count": reused_embedding_count,
                        "new_embedding_count": len(missing_digests),
                        "embedding_deployment": settings.azure_openai_embedding_deployment,
                        "chunking_profile": profile,
                    },
                )
                stored_ids = chunk_ids
            if embedding_trace is not None:
                embedding_trace.update(
                    output={
                        "embedded_chunk_count": embedded_chunk_count,
                        "reused_embedding_count": reused_embedding_count,
                        "content_captured": False,
                    }
                )

        if engine is not None:
            assert (
                document_id is not None
                and version_id is not None
                and vectors is not None
            )
            now = datetime.now(UTC)
            rows = []
            for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
                content_kind = chunk.metadata.get("content_type", "text")
                raw_page = chunk.metadata.get("page")
                page_number = None
                if isinstance(raw_page, int):
                    page_number = (
                        raw_page
                        if content_kind in {"table", "image_caption"}
                        else raw_page + 1
                    )
                rows.append(
                    {
                        "chunk_id": chunk_ids[index],
                        "document_version_id": version_id,
                        "chunking_profile": profile,
                        "chunk_index": index,
                        "chunk_text": chunk.page_content,
                        "text_storage_uri": None,
                        "page_start": page_number,
                        "page_end": page_number,
                        "section_path": chunk.metadata.get("section_path"),
                        "metadata": {
                            "source_id": source_key,
                            "source_file": original_filename,
                            "content_type": content_kind,
                            "file_type": file_type,
                            "chunk_index": index,
                            "chunking_profile": profile,
                            "content_sha256": content_digest,
                            "page_number": page_number,
                            "section_path": chunk.metadata.get("section_path"),
                            "start_index": chunk.metadata.get("start_index"),
                            "ingestion_pipeline_version": INGESTION_PIPELINE_VERSION,
                        },
                        "vector_record_id": None,
                        "embedding": vector,
                        "created_at": now,
                    }
                )
            with engine.begin() as connection:
                connection.execute(
                    delete(document_chunks).where(
                        document_chunks.c.document_version_id == version_id,
                        document_chunks.c.chunking_profile == profile,
                    )
                )
                connection.execute(
                    delete(document_chunks).where(
                        document_chunks.c.document_version_id == version_id,
                        document_chunks.c.chunking_profile != profile,
                    )
                )
                connection.execute(insert(document_chunks), rows)
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
            _finish_upload_run(engine, run_id, len(rows))
    except Exception:
        if engine is not None:
            try:
                _fail_upload_run(engine, run_id)
            except Exception:
                logger.exception(
                    "Failed to persist the terminal upload-run status",
                    extra={
                        "event": "document_ingestion.run_status_failed",
                        "ingestion_id": run_id,
                    },
                )
        logger.exception(
            "Document chunk storage failed",
            extra={
                "event": "document_ingestion.storage_failed",
                "storage_table": storage_table,
                "total_chunks": len(chunks),
                "duration_seconds": round(
                    time.perf_counter() - storage_started_at, 3
                ),
                **({"collection_name": collection_name} if collection_name else {}),
            },
        )
        raise
    logger.info(
        "Document chunk storage completed",
        extra={
            "event": "document_ingestion.storage_completed",
            "storage_table": storage_table,
            "total_chunks": len(chunks),
            "stored_chunk_count": len(stored_ids),
            "duration_seconds": round(
                time.perf_counter() - storage_started_at, 3
            ),
            **({"collection_name": collection_name} if collection_name else {}),
        },
    )
    result = _ingestion_result(
        original_filename,
        file_type,
        chunks,
        supplemental_documents,
        source_document_count,
        stored_ids,
        time.perf_counter() - started_at,
    )
    result["ingestion_id"] = run_id
    return result


def _register_uploaded_version(
    engine: Engine,
    *,
    source_key: str,
    filename: str,
    file_type: str,
    content_digest: str,
    owner_subject: str | None,
) -> tuple[str, str]:
    """Create stable source/version identities so retries use the same rows."""
    document_id = str(uuid5(NAMESPACE_URL, f"friis:{source_key}"))
    version_id = str(uuid5(NAMESPACE_URL, f"friis:{source_key}:{content_digest}"))
    source_uri = f"uploaded://{source_key}"
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    now = datetime.now(UTC)
    with engine.begin() as connection:
        existing_source = connection.execute(
            select(source_documents.c.document_id).where(
                source_documents.c.source_key == source_key
            )
        ).scalar_one_or_none()
        if existing_source is None:
            connection.execute(
                insert(source_documents).values(
                    document_id=document_id,
                    source_key=source_key,
                    title=filename,
                    source_type="uploaded_document",
                    source_uri=source_uri,
                    owner=owner_subject or "FRIIS operator upload",
                    access_classification="internal",
                    approved=True,
                    enabled=True,
                    created_at=now,
                    updated_at=now,
                )
            )
        else:
            document_id = str(existing_source)
            connection.execute(
                update(source_documents)
                .where(source_documents.c.document_id == document_id)
                .values(title=filename, enabled=True, updated_at=now)
            )
        existing_version = connection.execute(
            select(document_versions.c.document_version_id).where(
                document_versions.c.document_id == document_id,
                document_versions.c.content_sha256 == content_digest,
            )
        ).scalar_one_or_none()
        if existing_version is not None:
            version_id = str(existing_version)
        else:
            connection.execute(
                insert(document_versions).values(
                    document_version_id=version_id,
                    document_id=document_id,
                    version_label=f"sha256-{content_digest[:16]}",
                    content_sha256=content_digest,
                    content_type=content_type,
                    storage_uri=source_uri,
                    published_at=None,
                    effective_from=None,
                    effective_to=None,
                    validation_status="pending",
                    created_at=now,
                )
            )
    logger.info(
        "Resolved deterministic uploaded document identity",
        extra={
            "event": "document_ingestion.identity_resolved",
            "source_id": source_key,
            "document_version_id": version_id,
            "file_type": file_type,
            "content_sha256": content_digest,
        },
    )
    return document_id, version_id


def _existing_chunk_ids(engine: Engine, version_id: str, profile: str) -> list[str]:
    with engine.connect() as connection:
        return list(
            connection.execute(
                select(document_chunks.c.chunk_id)
                .where(
                    document_chunks.c.document_version_id == version_id,
                    document_chunks.c.chunking_profile == profile,
                )
                .order_by(document_chunks.c.chunk_index)
            ).scalars()
        )


def _start_upload_run(
    engine: Engine,
    ingestion_id: str,
    source_key: str,
    version_id: str,
    owner_subject: str | None,
) -> None:
    now = datetime.now(UTC)
    with engine.begin() as connection:
        connection.execute(
            insert(ingestion_runs).values(
                ingestion_id=ingestion_id,
                run_type="incremental",
                status=IngestionStatus.RUNNING.value,
                initiated_by=owner_subject or "FRIIS operator upload",
                pipeline_version=INGESTION_PIPELINE_VERSION,
                source_type="documents",
                source_ids=[source_key],
                validation_errors=[],
                started_at=now,
                completed_at=None,
                created_at=now,
            )
        )
        connection.execute(
            insert(ingestion_run_items).values(
                ingestion_id=ingestion_id,
                document_version_id=version_id,
                status=IngestionStatus.RUNNING.value,
                records_processed=0,
                chunks_created=0,
                chunks_indexed=0,
                error_code=None,
                error_message=None,
                started_at=now,
                completed_at=None,
            )
        )


def _finish_upload_run(
    engine: Engine, ingestion_id: str, chunk_count: int
) -> None:
    now = datetime.now(UTC)
    with engine.begin() as connection:
        connection.execute(
            update(ingestion_run_items)
            .where(ingestion_run_items.c.ingestion_id == ingestion_id)
            .values(
                status=IngestionStatus.SUCCEEDED.value,
                records_processed=1,
                chunks_created=chunk_count,
                chunks_indexed=chunk_count,
                completed_at=now,
            )
        )
        connection.execute(
            update(ingestion_runs)
            .where(ingestion_runs.c.ingestion_id == ingestion_id)
            .values(
                status=IngestionStatus.SUCCEEDED.value,
                completed_at=now,
            )
        )


def _fail_upload_run(engine: Engine, ingestion_id: str) -> None:
    now = datetime.now(UTC)
    with engine.begin() as connection:
        connection.execute(
            update(ingestion_run_items)
            .where(ingestion_run_items.c.ingestion_id == ingestion_id)
            .values(
                status=IngestionStatus.FAILED.value,
                error_code="upload_processing_failed",
                error_message="Document processing failed.",
                completed_at=now,
            )
        )
        connection.execute(
            update(ingestion_runs)
            .where(ingestion_runs.c.ingestion_id == ingestion_id)
            .values(
                status=IngestionStatus.FAILED.value,
                validation_errors=["Document processing failed."],
                completed_at=now,
            )
        )


def _activate_version(engine: Engine, document_id: str, version_id: str) -> None:
    with engine.begin() as connection:
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


def _clean_text(value: str) -> str:
    """Remove extraction control noise while preserving layout and tables."""
    value = value.replace("\x00", "").replace("\u200b", "").replace("\ufeff", "")
    value = value.replace("\u00a0", " ").replace("\u00ad", "")
    lines = [line.rstrip() for line in value.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _find_section_path(text: str, metadata: dict[str, object]) -> str | None:
    existing_path = metadata.get("section_path")
    if isinstance(existing_path, str) and existing_path.strip():
        return existing_path.strip()
    for line in text.splitlines():
        heading = re.match(r"^\s*#{1,6}\s+(.+?)\s*#*\s*$", line)
        if heading:
            return heading.group(1).strip()
        normalized = line.strip()
        if 4 <= len(normalized) <= 100 and normalized.upper() == normalized:
            if any(character.isalpha() for character in normalized):
                return normalized
    return None


def _ingestion_result(
    filename: str,
    file_type: str,
    chunks: list,
    supplemental_documents: list,
    source_document_count: int,
    chunk_ids: list[str],
    elapsed: float,
) -> dict[str, object]:
    lengths = [len(chunk.page_content) for chunk in chunks]
    return {
        "status": "success",
        "filename": filename,
        "file_type": file_type,
        "total_chunks": len(chunks),
        "average_chunk_length": sum(lengths) / len(lengths),
        "min_chunk_length": min(lengths),
        "max_chunk_length": max(lengths),
        "table_nodes": sum(
            document.metadata.get("content_type") == "table"
            for document in supplemental_documents
        ),
        "image_nodes": sum(
            document.metadata.get("content_type") == "image_caption"
            for document in supplemental_documents
        ),
        "processing_time_seconds": elapsed,
        "collection_name": DOCUMENT_CHUNKS_TABLE,
        "chunk_ids": chunk_ids,
        "source_documents": source_document_count,
    }
