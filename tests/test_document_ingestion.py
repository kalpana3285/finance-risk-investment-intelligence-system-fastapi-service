from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langchain_core.documents import Document
from sqlalchemy import create_engine, insert, select
from sqlalchemy.pool import StaticPool

from schemas import IngestionStatus
from services.database import (
    document_chunks,
    document_versions,
    ingestion_run_items,
    ingestion_runs,
    metadata,
    source_documents,
)
from services.document_ingestion import (
    PROJECT_PDF_NAMES,
    DocumentIngestionError,
    DocumentIngestionWorker,
    _chunk_pages,
    _extract_pdf_pages,
    register_project_pdf_sources,
)
from services.ingestion_utils import remove_repeated_page_marginalia


class FakeEmbedder:
    dimensions = 1536
    deployment = "test-embedding-deployment"
    api_version = "2024-02-01"

    def __init__(self) -> None:
        self.requests: list[list[str]] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.requests.append(texts)
        return [[0.25] * self.dimensions for _ in texts]


@pytest.fixture
def engine():
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata.create_all(test_engine)
    yield test_engine
    test_engine.dispose()


def test_chunk_pages_keeps_page_metadata_and_overlap() -> None:
    chunks = _chunk_pages(
        [("alpha beta gamma delta epsilon", 3), ("zeta eta theta", 4)],
        chunk_size=12,
        chunk_overlap=4,
    )

    assert chunks
    assert all(len(text) <= 12 for text, _, _ in chunks)
    assert {page for _, page, _ in chunks} == {3, 4}
    assert any("delta" in text for text, _, _ in chunks)


def test_chunk_pages_propagates_section_hierarchy_to_each_chunk() -> None:
    chunks = _chunk_pages(
        [
            ("# Risk Policy\nOverview content.", 1),
            ("## Exposure Limits\nLimit content.", 2),
        ],
        chunk_size=20,
        chunk_overlap=0,
    )

    assert {section for _, _, section in chunks} == {
        "Risk Policy",
        "Risk Policy > Exposure Limits",
    }


def test_repeated_page_headers_and_footers_are_removed_without_losing_body_text():
    pages = [
        "Investment Policy\nFirst page body\nPage 1\nConfidential footer",
        "Investment Policy\nSecond page body\nPage 2\nConfidential footer",
        "Investment Policy\nThird page body\nPage 3\nConfidential footer",
    ]

    cleaned = remove_repeated_page_marginalia(pages)

    assert cleaned == [
        "First page body",
        "Second page body",
        "Third page body",
    ]


def test_extract_pdf_pages_uses_langchain_pdf_loader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    file_path = tmp_path / "source.pdf"
    file_path.touch()

    class FakeReader:
        is_encrypted = False

    class FakeLoader:
        def __init__(self, path: str) -> None:
            assert path == str(file_path)

        def load(self) -> list[SimpleNamespace]:
            return [
                SimpleNamespace(
                    page_content="  Loaded   page text  ",
                    metadata={"page": 2},
                )
            ]

    monkeypatch.setattr(
        "services.document_ingestion.PdfReader", lambda _path: FakeReader()
    )
    monkeypatch.setattr("services.document_ingestion.PyPDFLoader", FakeLoader)

    assert _extract_pdf_pages(file_path, "source-1") == [("Loaded page text", 3)]


def test_register_project_pdf_sources_is_approved_and_idempotent(
    engine, tmp_path: Path
) -> None:
    documents_root = tmp_path / "Documents"
    documents_root.mkdir()
    for filename in PROJECT_PDF_NAMES:
        (documents_root / filename).write_bytes(b"placeholder")

    first = register_project_pdf_sources(engine, documents_root)
    second = register_project_pdf_sources(engine, documents_root)

    assert first == second == [f"project-pdf-{index:02d}" for index in range(1, 8)]
    with engine.connect() as connection:
        rows = connection.execute(select(source_documents)).mappings().all()
    assert len(rows) == 7
    assert all(row["approved"] and row["enabled"] for row in rows)


@pytest.mark.asyncio
async def test_worker_stores_versioned_chunks_and_is_idempotent(
    engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    documents_root = tmp_path / "Documents"
    documents_root.mkdir()
    (documents_root / "approved.pdf").write_bytes(b"pdf bytes")
    now = datetime.now(UTC)
    with engine.begin() as connection:
        connection.execute(
            insert(source_documents).values(
                document_id="document-1",
                source_key="project-pdf-01",
                title="Approved source",
                source_type="policy",
                source_uri="Documents/approved.pdf",
                access_classification="internal",
                approved=True,
                enabled=True,
                created_at=now,
                updated_at=now,
            )
        )

    worker = DocumentIngestionWorker(
        engine,
        FakeEmbedder(),
        documents_root,
        chunk_size=16,
        chunk_overlap=4,
        embedding_batch_size=2,
    )
    monkeypatch.setattr(
        "services.document_ingestion._extract_pdf_pages",
        lambda _content, _source_id: [("A sufficiently long test document.", 1)],
    )
    monkeypatch.setattr(
        "services.document_ingestion.extract_pdf_supplemental_documents",
        lambda _path: [
            Document(
                page_content="Metric | Value\nSharpe ratio | 1.2",
                metadata={"page": 2, "content_type": "table"},
            ),
            Document(
                page_content="The chart shows declining volatility.",
                metadata={"page": 3, "content_type": "image_caption"},
            ),
        ],
    )

    run_ids = [str(uuid4()), str(uuid4())]
    for ingestion_id in run_ids:
        with engine.begin() as connection:
            connection.execute(
                insert(ingestion_runs).values(
                    ingestion_id=ingestion_id,
                    run_type="incremental",
                    status="queued",
                    initiated_by="operator-1",
                    pipeline_version="test",
                    source_type="documents",
                    source_ids=["project-pdf-01"],
                    validation_errors=[],
                    created_at=now,
                )
            )
        summary = await worker.run_once()
        assert summary is not None
        assert summary.status == IngestionStatus.SUCCEEDED
        assert summary.succeeded == 1
        assert summary.failed == 0

    with engine.connect() as connection:
        versions = connection.execute(select(document_versions)).mappings().all()
        chunks = connection.execute(select(document_chunks)).mappings().all()
        items = connection.execute(select(ingestion_run_items)).mappings().all()
        runs = connection.execute(select(ingestion_runs)).mappings().all()

    assert len(versions) == 1
    assert len(chunks) > 0
    assert all(len(chunk["embedding"]) == 1536 for chunk in chunks)
    assert {chunk["metadata"]["content_type"] for chunk in chunks} == {
        "text",
        "table",
        "image_caption",
    }
    assert any(chunk["page_start"] == 2 for chunk in chunks)
    assert any(chunk["page_start"] == 3 for chunk in chunks)
    assert len(items) == 2
    assert all(item["status"] == "succeeded" for item in items)
    assert all(run["status"] == IngestionStatus.SUCCEEDED.value for run in runs)


@pytest.mark.asyncio
async def test_worker_reuses_embeddings_for_unchanged_chunks_on_new_version(
    engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    documents_root = tmp_path / "Documents"
    documents_root.mkdir()
    source_path = documents_root / "approved.pdf"
    source_path.write_bytes(b"version one")
    now = datetime.now(UTC)
    with engine.begin() as connection:
        connection.execute(
            insert(source_documents).values(
                document_id="document-incremental",
                source_key="project-pdf-01",
                title="Incremental source",
                source_type="policy",
                source_uri="Documents/approved.pdf",
                access_classification="internal",
                approved=True,
                enabled=True,
                created_at=now,
                updated_at=now,
            )
        )

    extracted_page = ["# Shared\nStable content."]
    monkeypatch.setattr(
        "services.document_ingestion._extract_pdf_pages",
        lambda _path, _source_id: [(extracted_page[0], 1)],
    )
    monkeypatch.setattr(
        "services.document_ingestion.extract_pdf_supplemental_documents",
        lambda _path: [],
    )
    embedder = FakeEmbedder()
    worker = DocumentIngestionWorker(
        engine,
        embedder,
        documents_root,
        chunk_size=1000,
        chunk_overlap=0,
    )

    for source_version in ("first", "second"):
        with engine.begin() as connection:
            connection.execute(
                insert(ingestion_runs).values(
                    ingestion_id=str(uuid4()),
                    run_type="incremental",
                    status="queued",
                    initiated_by="operator-1",
                    pipeline_version="test",
                    source_type="documents",
                    source_ids=["project-pdf-01"],
                    validation_errors=[],
                    created_at=now,
                )
            )
        if source_version == "second":
            source_path.write_bytes(b"version two")
            extracted_page[0] = (
                "# Shared\nStable content.\n# New Section\nAdded content."
            )
        summary = await worker.run_once()
        assert summary is not None
        assert summary.status == IngestionStatus.SUCCEEDED

    assert embedder.requests == [
        ["# Shared\nStable content."],
        ["# New Section\nAdded content."],
    ]
    with engine.connect() as connection:
        versions = connection.execute(select(document_versions)).mappings().all()
        chunks = connection.execute(select(document_chunks)).mappings().all()
    assert len(versions) == 2
    assert len(chunks) == 3
    assert {chunk["metadata"]["embedding_deployment"] for chunk in chunks} == {
        "test-embedding-deployment"
    }
    assert {chunk["metadata"]["section_path"] for chunk in chunks} == {
        "Shared",
        "New Section",
    }


def test_worker_rejects_source_paths_outside_documents_root(
    engine, tmp_path: Path
) -> None:
    worker = DocumentIngestionWorker(engine, FakeEmbedder(), tmp_path / "Documents")

    with pytest.raises(DocumentIngestionError, match="outside the approved documents root"):
        worker._resolve_source_path("../outside.pdf", "untrusted-source")
