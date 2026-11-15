import importlib
from pathlib import Path

from langchain_core.documents import Document


def test_document_processing_service_uses_available_loaders(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CHUNK_SIZE", "1000")
    monkeypatch.setenv("CHUNK_OVERLAP", "100")
    service = importlib.import_module("services.document_processing_service")
    loader_calls: list[tuple[str, object]] = []

    class FakeLoader:
        def __init__(self, source: object, **kwargs: object) -> None:
            loader_calls.append((str(source), kwargs))
            self.source = source

        def load(self) -> list[Document]:
            return [Document(page_content=str(self.source))]

    monkeypatch.setattr(service, "PyPDFLoader", FakeLoader)
    monkeypatch.setattr(service, "TextLoader", FakeLoader)
    monkeypatch.setattr(service, "BSHTMLLoader", FakeLoader)
    monkeypatch.setattr(service, "WebBaseLoader", FakeLoader)

    pdf_path = tmp_path / "source.pdf"
    text_path = tmp_path / "source.txt"
    html_path = tmp_path / "source.html"
    assert service.load_pdf(pdf_path)[0].page_content == str(pdf_path)
    assert service.load_text_file(text_path)[0].page_content == str(text_path)
    assert service.load_html_file(html_path)[0].page_content == str(html_path)
    assert service.load_web_page("https://example.test")[0].page_content == (
        "https://example.test"
    )
    assert [source for source, _ in loader_calls] == [
        str(pdf_path),
        str(text_path),
        str(html_path),
        "https://example.test",
    ]

    monkeypatch.setattr(
        service,
        "process_documents",
        lambda documents, *_args: {"chunks": documents},
    )
    result = service.load_and_process_multi_source(
        [pdf_path],
        [text_path],
        [html_path],
        ["https://example.test"],
    )
    assert result["source_documents"] == 4
    assert [document.page_content for document in result["chunks"]] == [
        str(pdf_path),
        str(text_path),
        str(html_path),
        "https://example.test",
    ]
