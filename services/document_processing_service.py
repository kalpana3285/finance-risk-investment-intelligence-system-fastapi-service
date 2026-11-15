"""
Document Processing Service
Database-independent utilities for loading and chunking documents.
This module handles multi-source loading (PDF, text, HTML, web) and splitting into chunks.

Uses modular service classes for document loading:
- PDFLoaderService for PDF files
- TextLoaderService for text files
- HTMLLoaderService for HTML files
- WebLoaderService for web pages
"""

import logging
import os
import sys
from pathlib import Path
from typing import Any, ClassVar

from dotenv import load_dotenv
from langchain_community.document_loaders import (
    BSHTMLLoader,
    PyPDFLoader,
    TextLoader,
    WebBaseLoader,
)
from langchain_core.documents import Document

from services.chunking_service import ChunkingService

# -----------------------------------------------------------------------------
# File Type Detection
# -----------------------------------------------------------------------------

class FileTypeDetector:
    """Utility class for detecting file types."""
    
    # File type mappings
    PDF_EXTENSIONS: ClassVar[set[str]] = {".pdf"}
    TEXT_EXTENSIONS: ClassVar[set[str]] = {".txt", ".md", ".markdown"}
    HTML_EXTENSIONS: ClassVar[set[str]] = {".html", ".htm"}
    SUPPORTED_EXTENSIONS: ClassVar[set[str]] = (
        PDF_EXTENSIONS | TEXT_EXTENSIONS | HTML_EXTENSIONS
    )
    
    @classmethod
    def get_file_type(cls, file_path: Path) -> str | None:
        """
        Get the file type category for a given file path.
        
        Args:
            file_path: Path to the file
            
        Returns:
            File type string ('pdf', 'text', 'html') or None if unsupported
        """
        suffix = file_path.suffix.lower()
        
        if suffix in cls.PDF_EXTENSIONS:
            return "pdf"
        elif suffix in cls.TEXT_EXTENSIONS:
            return "text"
        elif suffix in cls.HTML_EXTENSIONS:
            return "html"
        else:
            return None
    
    @classmethod
    def is_supported(cls, file_path: Path) -> bool:
        """
        Check if a file type is supported.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if file type is supported, False otherwise
        """
        suffix = file_path.suffix.lower()
        return suffix in cls.SUPPORTED_EXTENSIONS
    
    @classmethod
    def categorize_files(cls, file_paths: list[Path]) -> dict[str, list[Path]]:
        """
        Categorize multiple files by type.
        
        Args:
            file_paths: List of file paths
            
        Returns:
            Dictionary with file type as key and list of paths as value
        """
        categorized = {
            "pdf": [],
            "text": [],
            "html": [],
            "unsupported": []
        }
        
        for file_path in file_paths:
            file_type = cls.get_file_type(file_path)
            if file_type:
                categorized[file_type].append(file_path)
            else:
                categorized["unsupported"].append(file_path)
        
        return categorized
    
    @classmethod
    def get_supported_extensions(cls) -> list[str]:
        """
        Get list of all supported file extensions.
        
        Returns:
            List of supported file extensions (with dots)
        """
        return sorted(cls.SUPPORTED_EXTENSIONS)


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


# Load environment variables
try:
    load_dotenv()
    logger.info("Environment variables loaded successfully")
except OSError:
    logger.exception("Failed to load .env file")


# Processing configuration
try:
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))

    # Default docs directory: project_root/ Documents
    DEFAULT_DOCS_DIR = Path(__file__).parent.parent.parent / "Documents"
    DOCS_DIR = Path(os.getenv("DOCS_DIR", str(DEFAULT_DOCS_DIR)))

    WEB_URL = os.getenv("WEB_URL", "https://python.langchain.com/docs/introduction/")

    logger.info(
        f"Document processing config: chunk_size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP}, docs_dir={DOCS_DIR}"
    )
except (OSError, TypeError, ValueError):
    logger.exception("Failed to configure document processing")
    sys.exit(1)


# -----------------------------------------------------------------------------
# Helpers: configuration accessors
# -----------------------------------------------------------------------------

def get_chunk_size() -> int:
    return CHUNK_SIZE


def get_chunk_overlap() -> int:
    return CHUNK_OVERLAP




# -----------------------------------------------------------------------------
# Loader Services (Initialized once for reuse)
# -----------------------------------------------------------------------------

# Initialize the chunking service once for reuse.
_chunking_service = ChunkingService(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP
)


# -----------------------------------------------------------------------------
# Loader Functions (Wrapper functions for backward compatibility)
# -----------------------------------------------------------------------------

def load_pdf(file_path: Path) -> list[Document]:
    """
    Load a PDF file using PDFLoaderService.
    
    Args:
        file_path: Path to the PDF file
        
    Returns:
        List of Document objects (one per page)
    """
    return PyPDFLoader(str(file_path)).load()


def load_text_file(file_path: Path) -> list[Document]:
    """
    Load a text file using TextLoaderService.
    
    Args:
        file_path: Path to the text file
        
    Returns:
        List of Document objects
    """
    return TextLoader(str(file_path), encoding="utf-8").load()


def load_html_file(file_path: Path) -> list[Document]:
    """
    Load an HTML file using HTMLLoaderService.
    
    Args:
        file_path: Path to the HTML file
        
    Returns:
        List of Document objects
    """
    return BSHTMLLoader(str(file_path)).load()


def load_web_page(url: str) -> list[Document]:
    """
    Load a web page using WebLoaderService.
    
    Args:
        url: URL of the web page
        
    Returns:
        List of Document objects
    """
    return WebBaseLoader(url).load()




# -----------------------------------------------------------------------------
# Splitting / Processing
# -----------------------------------------------------------------------------

def split_documents(
    documents: list[Document],
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[Document]:
    """
    Split documents into chunks using ChunkingService.
    
    Args:
        documents: List of Document objects to split
        chunk_size: Size of chunks in characters
        chunk_overlap: Overlap between chunks in characters
        
    Returns:
        List of Document objects (chunks)
    """
    return _chunking_service.chunk_documents(documents, chunk_size, chunk_overlap)


def process_documents(
    documents: list[Document],
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> dict[str, Any]:
    """
    Process documents into chunks with statistics using ChunkingService.
    
    Args:
        documents: List of Document objects to process
        chunk_size: Size of chunks in characters
        chunk_overlap: Overlap between chunks in characters
        
    Returns:
        Dictionary with chunks and processing statistics
    """
    return _chunking_service.chunk_documents_with_stats(
        documents,
        chunk_size=chunk_size or get_chunk_size(),
        chunk_overlap=chunk_overlap or get_chunk_overlap()
    )


def load_and_process_multi_source(
    pdf_files: list[Path] | None = None,
    text_files: list[Path] | None = None,
    html_files: list[Path] | None = None,
    web_urls: list[str] | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> dict[str, Any]:
    """
    Load documents from multiple sources and process them into chunks.
    
    Uses service classes for loading:
    - PDFLoaderService for PDF files
    - TextLoaderService for text files
    - HTMLLoaderService for HTML files
    - WebLoaderService for web URLs
    
    Args:
        pdf_files: Optional list of PDF file paths
        text_files: Optional list of text file paths
        html_files: Optional list of HTML file paths
        web_urls: Optional list of web page URLs
        chunk_size: Size of chunks in characters
        chunk_overlap: Overlap between chunks in characters
        
    Returns:
        Dictionary with processing results including chunks and statistics
    """
    all_docs: list[Document] = []

    logger.info("=" * 70)
    logger.info("LOADING DOCUMENTS FROM MULTIPLE SOURCES")
    logger.info("=" * 70)

    # Load PDF files using PDFLoaderService
    if pdf_files:
        for file_path in pdf_files:
            all_docs.extend(load_pdf(file_path))

    # Load text files using TextLoaderService
    if text_files:
        for file_path in text_files:
            all_docs.extend(load_text_file(file_path))

    # Load HTML files using HTMLLoaderService
    if html_files:
        for file_path in html_files:
            all_docs.extend(load_html_file(file_path))

    # Load web pages using WebLoaderService
    if web_urls:
        for url in web_urls:
            all_docs.extend(load_web_page(url))

    if not all_docs:
        raise ValueError("No documents were loaded from any source")

    logger.info(f"\nTotal documents loaded: {len(all_docs)}")
    logger.info(f"  Total characters: {sum(len(d.page_content) for d in all_docs):,}")

    logger.info("\n" + "=" * 70)
    logger.info("PROCESSING DOCUMENTS")
    logger.info("=" * 70)

    result = process_documents(all_docs, chunk_size, chunk_overlap)
    result["source_documents"] = len(all_docs)
    return result
