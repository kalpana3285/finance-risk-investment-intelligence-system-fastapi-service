"""Extract searchable tables and visual descriptions from finance PDFs."""

import base64
import logging
import os
from collections.abc import Callable
from pathlib import Path

import fitz
from dotenv import load_dotenv
from langchain_core.documents import Document
from openai import APIError, AzureOpenAI
from prompts.catalog import get_prompt

logger = logging.getLogger(__name__)

VECTOR_DRAWING_THRESHOLD = 8
VISUAL_CAPTION_PROMPT_CONFIG = get_prompt("pdf-visual-caption")
VISUAL_CAPTION_PROMPT = VISUAL_CAPTION_PROMPT_CONFIG["template"]


def visual_processing_profile() -> str:
    load_dotenv(
        dotenv_path=Path(__file__).resolve().parents[1] / ".env",
        override=False,
    )
    deployment = (
        os.getenv("FRIIS_VISION_DEPLOYMENT")
        or os.getenv("AZURE_OPENAI_LLM_DEPLOYMENT")
        or "unconfigured"
    )
    api_version = os.getenv("AZURE_OPENAI_API_VERSION") or "unconfigured"
    return (
        f"{deployment}:{api_version}:"
        f"{VISUAL_CAPTION_PROMPT_CONFIG['name']}-v"
        f"{VISUAL_CAPTION_PROMPT_CONFIG['version']}"
    )


class MultimodalProcessingError(RuntimeError):
    """Raised when a PDF's tables or visual content cannot be processed."""


def extract_pdf_supplemental_documents(
    file_path: Path,
    *,
    captioner: Callable[[bytes], str] | None = None,
) -> list[Document]:
    """Return table text and visual captions not reliably emitted by PDF text loaders."""
    try:
        pdf = fitz.open(str(file_path))
    except (fitz.FileDataError, RuntimeError) as exc:
        raise MultimodalProcessingError(
            "PDF could not be opened for multimodal extraction."
        ) from exc

    client: AzureOpenAI | None = None
    try:
        try:
            visual_pages = [
                page_number
                for page_number in range(pdf.page_count)
                if _has_visual_content(pdf.load_page(page_number))
            ]
        except RuntimeError as exc:
            raise MultimodalProcessingError(
                "Visual content could not be inspected in the PDF."
            ) from exc
        if visual_pages and captioner is None:
            vision_client, deployment = _create_vision_client()
            client = vision_client

            def caption_page(image_bytes: bytes) -> str:
                return _caption_page_image(
                    vision_client, deployment, image_bytes
                )

            captioner = caption_page

        supplemental_documents: list[Document] = []
        for page_number in range(pdf.page_count):
            page = pdf.load_page(page_number)
            page_label = page_number + 1
            try:
                finder = page.find_tables()
                if not finder.tables:
                    finder = page.find_tables(strategy="text")
                tables = [table.extract() for table in finder.tables]
            except RuntimeError as exc:
                raise MultimodalProcessingError(
                    f"Tables could not be extracted from PDF page {page_label}."
                ) from exc
            for table_index, table_rows in enumerate(tables):
                table_text = _format_table(table_rows)
                if table_text:
                    supplemental_documents.append(
                        Document(
                            page_content=(
                                f"Financial table from PDF page {page_label}:\n"
                                f"{table_text}"
                            ),
                            metadata={
                                "page": page_label,
                                "content_type": "table",
                                "table_index": table_index,
                            },
                        )
                    )

            if page_number not in visual_pages:
                continue
            if captioner is None:
                raise MultimodalProcessingError(
                    "A vision captioner is required for visual PDF content."
                )
            try:
                image_bytes = page.get_pixmap(
                    matrix=fitz.Matrix(1.5, 1.5),
                    alpha=False,
                ).tobytes("png")
            except RuntimeError as exc:
                raise MultimodalProcessingError(
                    f"Visual content could not be rendered from PDF page {page_label}."
                ) from exc
            caption = captioner(image_bytes).strip()
            if not caption:
                raise MultimodalProcessingError(
                    f"No visual description was returned for PDF page {page_label}."
                )
            supplemental_documents.append(
                Document(
                    page_content=(
                        f"Visual content on PDF page {page_label}: {caption}"
                    ),
                    metadata={
                        "page": page_label,
                        "content_type": "image_caption",
                        "visual_index": 0,
                    },
                )
            )
        return supplemental_documents
    finally:
        pdf.close()
        if client is not None:
            client.close()


def _has_visual_content(page: fitz.Page) -> bool:
    return bool(page.get_images(full=True)) or (
        len(page.get_drawings()) >= VECTOR_DRAWING_THRESHOLD
    )


def _format_table(rows: list[list[str | None]]) -> str:
    normalized_rows = [
        [" ".join((cell or "").split()).replace("|", r"\|") for cell in row]
        for row in rows
    ]
    normalized_rows = [row for row in normalized_rows if any(row)]
    if len(normalized_rows) < 2:
        return ""
    column_count = max(map(len, normalized_rows))
    padded_rows = [
        row + [""] * (column_count - len(row)) for row in normalized_rows
    ]
    header = "| " + " | ".join(padded_rows[0]) + " |"
    separator = "| " + " | ".join("---" for _ in range(column_count)) + " |"
    body = [
        "| " + " | ".join(row) + " |" for row in padded_rows[1:]
    ]
    return "\n".join((header, separator, *body))


def _create_vision_client() -> tuple[AzureOpenAI, str]:
    load_dotenv(
        dotenv_path=Path(__file__).resolve().parents[1] / ".env",
        override=False,
    )
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION")
    deployment = (
        os.getenv("FRIIS_VISION_DEPLOYMENT")
        or os.getenv("AZURE_OPENAI_LLM_DEPLOYMENT")
    )
    missing = [
        name
        for name, value in (
            ("AZURE_OPENAI_ENDPOINT", endpoint),
            ("AZURE_OPENAI_API_KEY", api_key),
            ("AZURE_OPENAI_API_VERSION", api_version),
            ("FRIIS_VISION_DEPLOYMENT or AZURE_OPENAI_LLM_DEPLOYMENT", deployment),
        )
        if not value
    ]
    if missing:
        raise MultimodalProcessingError(
            "Visual PDF content requires Azure OpenAI settings: "
            + ", ".join(missing)
        )
    return (
        AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
            timeout=45.0,
            max_retries=2,
        ),
        deployment,
    )


def _caption_page_image(
    client: AzureOpenAI,
    deployment: str,
    image_bytes: bytes,
) -> str:
    image_data = base64.b64encode(image_bytes).decode("ascii")
    try:
        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": VISUAL_CAPTION_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_data}"
                            },
                        },
                    ],
                }
            ],
        )
    except APIError as exc:
        logger.exception("Azure OpenAI visual caption request failed")
        raise MultimodalProcessingError(
            "Azure OpenAI could not describe visual PDF content."
        ) from exc
    if not response.choices:
        raise MultimodalProcessingError(
            "Azure OpenAI returned no visual description for the PDF page."
        )
    content = response.choices[0].message.content
    if not isinstance(content, str):
        raise MultimodalProcessingError(
            "Azure OpenAI returned no visual description for the PDF page."
        )
    return content
