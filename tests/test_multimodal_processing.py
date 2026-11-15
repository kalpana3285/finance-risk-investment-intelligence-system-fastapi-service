from pathlib import Path
from types import SimpleNamespace

import pytest

from services import multimodal_processing


class FakeTable:
    def extract(self) -> list[list[str]]:
        return [["Metric", "Value"], ["Volatility", "12%"]]


class FakePage:
    def find_tables(self) -> SimpleNamespace:
        return SimpleNamespace(tables=[FakeTable()])

    def get_images(self, *, full: bool) -> list[tuple[int]]:
        assert full
        return [(1,)]

    def get_drawings(self) -> list[object]:
        return []

    def get_pixmap(self, *, matrix: object, alpha: bool) -> SimpleNamespace:
        assert matrix is not None
        assert alpha is False
        return SimpleNamespace(tobytes=lambda image_format: b"page-image")


class FakePDF:
    page_count = 1

    def __init__(self) -> None:
        self.page = FakePage()
        self.closed = False

    def load_page(self, page_number: int) -> FakePage:
        assert page_number == 0
        return self.page

    def close(self) -> None:
        self.closed = True


def test_extract_pdf_supplemental_documents_keeps_table_and_visual_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    file_path = tmp_path / "finance.pdf"
    file_path.touch()
    pdf = FakePDF()
    monkeypatch.setattr(multimodal_processing.fitz, "open", lambda _path: pdf)
    image_bytes_seen: list[bytes] = []

    def captioner(image_bytes: bytes) -> str:
        image_bytes_seen.append(image_bytes)
        return "A line chart shows volatility decreasing from 12% to 8%."

    documents = multimodal_processing.extract_pdf_supplemental_documents(
        file_path,
        captioner=captioner,
    )

    assert [document.metadata["content_type"] for document in documents] == [
        "table",
        "image_caption",
    ]
    assert all(document.metadata["page"] == 1 for document in documents)
    assert "Volatility" in documents[0].page_content
    assert "12%" in documents[0].page_content
    assert "decreasing from 12% to 8%" in documents[1].page_content
    assert image_bytes_seen == [b"page-image"]
    assert pdf.closed


def test_format_table_escapes_cells_and_ignores_single_row_tables() -> None:
    assert multimodal_processing._format_table(
        [["Asset", "Exposure"], ["Bonds | Gov", "30%"]]
    ) == "| Asset | Exposure |\n| --- | --- |\n| Bonds \\| Gov | 30% |"
    assert multimodal_processing._format_table([["Header", "Value"]]) == ""
