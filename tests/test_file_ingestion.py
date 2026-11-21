import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from langchain_core.documents import Document
from sqlalchemy import create_engine, select
from sqlalchemy.pool import StaticPool

from services import file_ingestion
from services.database import (
    ingestion_run_items,
    ingestion_runs,
    metadata,
    source_documents,
)


def test_process_and_store_file_runs_langchain_pipeline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger=file_ingestion.__name__)
    file_path = tmp_path / "source.txt"
    file_path.write_text("alpha beta gamma delta epsilon zeta", encoding="utf-8")
    loaded_documents = [Document(page_content=file_path.read_text(encoding="utf-8"))]
    captured: dict[str, Any] = {}

    class FakeTextLoader:
        def __init__(self, path: str, *, encoding: str) -> None:
            assert path == str(file_path)
            assert encoding == "utf-8"

        def load(self) -> list[Document]:
            return loaded_documents

    class FakeVectorStore:
        def __init__(self, **kwargs: Any) -> None:
            captured["vectorstore"] = kwargs

        def add_documents(
            self, documents: list[Document], *, ids: list[str]
        ) -> list[str]:
            captured["documents"] = documents
            captured["ids"] = ids
            return ids

    monkeypatch.setattr(file_ingestion, "TextLoader", FakeTextLoader)
    monkeypatch.setattr(
        file_ingestion,
        "RuntimeSettings",
        SimpleNamespace(
            from_environment=lambda: SimpleNamespace(
                azure_openai_endpoint="https://example.openai.azure.com",
                azure_openai_api_key="test-key",
                azure_openai_api_version="2024-02-01",
                azure_openai_embedding_deployment="embeddings",
                database_url="postgresql+psycopg://user:pass@localhost/db",
            )
        ),
    )
    monkeypatch.setattr(
        file_ingestion, "AzureOpenAIEmbeddings", lambda **kwargs: kwargs
    )
    monkeypatch.setattr(file_ingestion, "PGVector", FakeVectorStore)
    monkeypatch.setattr(
        file_ingestion, "make_url", lambda _url: SimpleNamespace(drivername="postgresql")
    )
    monkeypatch.setenv("FRIIS_DOCUMENT_COLLECTION", "test_uploads")

    result = file_ingestion.process_and_store_file(
        file_path,
        chunk_size=16,
        chunk_overlap=4,
        filename="source.txt",
    )

    assert result["status"] == "success"
    assert result["filename"] == "source.txt"
    assert result["file_type"] == "text"
    assert result["total_chunks"] > 1
    assert result["table_nodes"] == 0
    assert result["image_nodes"] == 0
    assert result["chunk_ids"] == captured["ids"]
    assert captured["vectorstore"]["collection_name"] == "test_uploads"
    assert any(
        record.event == "document_ingestion.storage_started"
        and record.storage_table == "langchain_pg_embedding"
        and record.collection_name == "test_uploads"
        for record in caplog.records
    )
    assert all(
        chunk.metadata["source_file"] == "source.txt"
        for chunk in captured["documents"]
    )
    assert all(
        len(chunk.page_content) <= 16 for chunk in captured["documents"]
    )
    assert {
        chunk.metadata["embedding_deployment"] for chunk in captured["documents"]
    } == {"embeddings"}
    assert {
        chunk.metadata["ingestion_pipeline_version"]
        for chunk in captured["documents"]
    } == {"friis-upload-v3"}


def test_uploaded_sources_record_the_uploader_and_shared_internal_policy() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata.create_all(engine)
    try:
        document_id, _ = file_ingestion._register_uploaded_version(
            engine,
            source_key="uploaded-test",
            filename="risk-policy.pdf",
            file_type="pdf",
            content_digest="a" * 64,
            owner_subject="operator-1",
        )
        with engine.connect() as connection:
            row = connection.execute(
                select(source_documents).where(
                    source_documents.c.document_id == document_id
                )
            ).mappings().one()
        assert row["owner"] == "operator-1"
        assert row["access_classification"] == "internal"
        assert row["approved"] is True
        assert row["enabled"] is True
    finally:
        engine.dispose()


def test_direct_upload_run_records_terminal_success_and_counts() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata.create_all(engine)
    try:
        _, version_id = file_ingestion._register_uploaded_version(
            engine,
            source_key="uploaded-run-test",
            filename="risk-policy.txt",
            file_type="text",
            content_digest="b" * 64,
            owner_subject="operator-1",
        )
        file_ingestion._start_upload_run(
            engine,
            "ingestion-run-test",
            "uploaded-run-test",
            version_id,
            "operator-1",
        )
        file_ingestion._finish_upload_run(engine, "ingestion-run-test", 3)

        with engine.connect() as connection:
            run = connection.execute(
                select(ingestion_runs).where(
                    ingestion_runs.c.ingestion_id == "ingestion-run-test"
                )
            ).mappings().one()
            item = connection.execute(
                select(ingestion_run_items).where(
                    ingestion_run_items.c.ingestion_id == "ingestion-run-test"
                )
            ).mappings().one()
        assert run["initiated_by"] == "operator-1"
        assert run["source_ids"] == ["uploaded-run-test"]
        assert run["status"] == "succeeded"
        assert item["status"] == "succeeded"
        assert item["chunks_created"] == 3
        assert item["chunks_indexed"] == 3
    finally:
        engine.dispose()


def test_process_and_store_pdf_indexes_tables_and_visual_captions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    file_path = tmp_path / "source.pdf"
    file_path.write_bytes(b"pdf bytes")
    table_document = Document(
        page_content="Risk measure | Value\nVolatility | 12%",
        metadata={"page": 1, "content_type": "table"},
    )
    image_document = Document(
        page_content="The chart shows rising portfolio exposure.",
        metadata={"page": 2, "content_type": "image_caption"},
    )
    captured: dict[str, Any] = {}

    class FakePDFLoader:
        def __init__(self, path: str) -> None:
            assert path == str(file_path)

        def load(self) -> list[Document]:
            return [Document(page_content="Investment risk overview")]

    class FakeVectorStore:
        def __init__(self, **kwargs: Any) -> None:
            captured["vectorstore"] = kwargs

        def add_documents(
            self, documents: list[Document], *, ids: list[str]
        ) -> list[str]:
            captured["documents"] = documents
            return ids

    monkeypatch.setattr(file_ingestion, "PyPDFLoader", FakePDFLoader)
    monkeypatch.setattr(
        file_ingestion,
        "extract_pdf_supplemental_documents",
        lambda _path: [table_document, image_document],
    )
    monkeypatch.setattr(
        file_ingestion,
        "RuntimeSettings",
        SimpleNamespace(
            from_environment=lambda: SimpleNamespace(
                azure_openai_endpoint="https://example.openai.azure.com",
                azure_openai_api_key="test-key",
                azure_openai_api_version="2024-02-01",
                azure_openai_embedding_deployment="embeddings",
                database_url="******localhost/db",
            )
        ),
    )
    monkeypatch.setattr(
        file_ingestion, "AzureOpenAIEmbeddings", lambda **kwargs: kwargs
    )
    monkeypatch.setattr(file_ingestion, "PGVector", FakeVectorStore)
    monkeypatch.setattr(
        file_ingestion, "make_url", lambda _url: SimpleNamespace(drivername="postgresql")
    )

    result = file_ingestion.process_and_store_file(
        file_path,
        chunk_size=1000,
        chunk_overlap=100,
        filename="source.pdf",
    )

    assert result["table_nodes"] == 1
    assert result["image_nodes"] == 1
    assert result["source_documents"] == 1
    assert {
        chunk.metadata["content_type"] for chunk in captured["documents"]
    } == {"text", "table", "image_caption"}
    assert all(
        chunk.metadata["source_file"] == "source.pdf"
        for chunk in captured["documents"]
    )


def test_process_and_store_file_rejects_invalid_chunk_overlap(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "source.txt"
    file_path.write_text("text", encoding="utf-8")

    with pytest.raises(ValueError, match="smaller than chunk size"):
        file_ingestion.process_and_store_file(
            file_path, chunk_size=10, chunk_overlap=10
        )
