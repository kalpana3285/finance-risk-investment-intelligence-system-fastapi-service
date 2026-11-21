"""Shared deterministic helpers for document ingestion."""

import math
import re
from collections import defaultdict
from collections.abc import Sequence
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.engine import Engine

from services.database import document_chunks, document_versions


def chunk_text_digest(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def load_reusable_chunk_vectors(
    engine: Engine, document_id: str, chunking_profile: str
) -> dict[str, list[float]]:
    """Load valid prior embeddings keyed by normalized chunk text."""
    statement = (
        select(document_chunks.c.chunk_text, document_chunks.c.embedding)
        .join(
            document_versions,
            document_versions.c.document_version_id
            == document_chunks.c.document_version_id,
        )
        .where(
            document_versions.c.document_id == document_id,
            document_versions.c.validation_status == "valid",
            document_chunks.c.chunking_profile == chunking_profile,
            document_chunks.c.chunk_text.is_not(None),
        )
    )
    with engine.connect() as connection:
        rows = connection.execute(statement).all()
    vectors: dict[str, list[float]] = {}
    for text, embedding in rows:
        vectors.setdefault(
            chunk_text_digest(str(text)),
            [float(value) for value in embedding],
        )
    return vectors


def remove_repeated_page_marginalia(pages: Sequence[str]) -> list[str]:
    """Remove repeated short lines confined to page headers or footers."""
    if len(pages) < 3:
        return list(pages)

    occurrences: dict[str, set[int]] = defaultdict(set)
    page_lines = [page.splitlines() for page in pages]
    for page_index, lines in enumerate(page_lines):
        nonempty = [index for index, line in enumerate(lines) if line.strip()]
        edge_indices = set(nonempty[:2] + nonempty[-2:])
        for line_index in edge_indices:
            normalized = _normalize_line(lines[line_index])
            if (
                5 <= len(normalized) <= 120
                and not _is_page_counter(normalized)
            ):
                occurrences[normalized].add(page_index)

    threshold = max(3, math.ceil(len(pages) * 0.6))
    repeated = {
        line for line, page_indexes in occurrences.items()
        if len(page_indexes) >= threshold
    }
    if not repeated:
        return list(pages)

    cleaned_pages: list[str] = []
    for lines in page_lines:
        nonempty = [index for index, line in enumerate(lines) if line.strip()]
        edge_indices = set(nonempty[:2] + nonempty[-2:])
        cleaned_pages.append(
            "\n".join(
                line
                for index, line in enumerate(lines)
                if index not in edge_indices
                or (
                    _normalize_line(line) not in repeated
                    and not _is_page_counter(_normalize_line(line))
                )
            ).strip()
        )
    return cleaned_pages


def sectioned_pages(
    pages: Sequence[tuple[str, int]],
) -> list[tuple[str, int, str | None]]:
    """Split pages at headings and carry the active section path across pages."""
    blocks: list[tuple[str, int, str | None]] = []
    hierarchy: list[str] = []
    for text, page_number in pages:
        lines: list[str] = []

        def flush() -> None:
            if lines:
                blocks.append(
                    (
                        "\n".join(lines).strip(),
                        page_number,
                        " > ".join(hierarchy) or None,
                    )
                )
                lines.clear()

        for line in text.splitlines():
            heading = _heading(line)
            if heading is None:
                lines.append(line)
                continue
            flush()
            level, title = heading
            hierarchy[:] = hierarchy[: level - 1]
            hierarchy.append(title)
            lines.append(line)
        flush()
    return [block for block in blocks if block[0]]


def section_path_at_offset(text: str, offset: int) -> str | None:
    hierarchy: list[str] = []
    cursor = 0
    for line in text.splitlines(keepends=True):
        if cursor > offset:
            break
        heading = _heading(line)
        if heading is not None:
            level, title = heading
            hierarchy[:] = hierarchy[: level - 1]
            hierarchy.append(title)
        cursor += len(line)
    return " > ".join(hierarchy) or None


def _heading(line: str) -> tuple[int, str] | None:
    markdown = re.match(r"^\s*(#{1,6})\s+(.+?)\s*#*\s*$", line)
    if markdown:
        return len(markdown.group(1)), markdown.group(2).strip()
    numbered = re.match(r"^\s*(\d+(?:\.\d+){0,5})[.)]?\s+(.{3,100})$", line)
    if numbered:
        level = numbered.group(1).count(".") + 1
        return level, numbered.group(2).strip()
    normalized = line.strip()
    if (
        4 <= len(normalized) <= 100
        and normalized.upper() == normalized
        and any(character.isalpha() for character in normalized)
    ):
        return 1, normalized
    return None


def _normalize_line(line: str) -> str:
    return " ".join(line.split()).casefold()


def _is_page_counter(line: str) -> bool:
    return line.isdecimal() or re.fullmatch(
        r"(?:page\s*)?\d+(?:\s+of\s+\d+)?", line
    ) is not None
