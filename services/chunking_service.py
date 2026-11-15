"""
Document Chunking and Metadata Service

This service handles document chunking using RecursiveCharacterTextSplitter
and metadata operations for documents and chunks.
Provides a clean, reusable interface for splitting documents and managing metadata.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)


class ChunkingService:
    """Service for chunking documents and managing metadata."""
    
    DEFAULT_CHUNK_SIZE = 1000
    DEFAULT_CHUNK_OVERLAP = 100
    DEFAULT_SEPARATORS: ClassVar[list[str]] = ["\n\n", "\n", " ", ""]
    
    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
        separators: list[str] | None = None
    ):
        """
        Initialize the chunking service.
        
        Args:
            chunk_size: Size of chunks in characters
            chunk_overlap: Overlap between chunks in characters
            separators: List of separators to use for splitting
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or self.DEFAULT_SEPARATORS
        self._splitter = None
    
    def _get_splitter(self) -> RecursiveCharacterTextSplitter:
        """Get or create the text splitter instance."""
        if self._splitter is None:
            # ============================================================================
            # LANGCHAIN: RECURSIVE CHARACTER TEXT SPLITTER INITIALIZATION
            # ============================================================================
            # This initializes the LangChain RecursiveCharacterTextSplitter with:
            # - chunk_size: Maximum size of each text chunk
            # - chunk_overlap: Number of characters to overlap between chunks
            # - length_function: Function to calculate text length (len)
            # - separators: List of separators to use for splitting text
            # ============================================================================
            self._splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                length_function=len,
                separators=self.separators,
            )
            # ============================================================================
        return self._splitter
    
    def chunk_documents(
        self,
        documents: list[Document],
        chunk_size: int | None = None,
        chunk_overlap: int | None = None
    ) -> list[Document]:
        """
        Split documents into chunks using RecursiveCharacterTextSplitter.
        
        Args:
            documents: List of Document objects to chunk
            chunk_size: Override default chunk size
            chunk_overlap: Override default chunk overlap
            
        Returns:
            List of Document objects (chunks)
            
        Raises:
            ValueError: If no documents provided
        """
        if not documents:
            raise ValueError("No documents provided for splitting")
        
        # Use provided parameters or instance defaults
        size = chunk_size or self.chunk_size
        overlap = chunk_overlap or self.chunk_overlap
        
        # Create splitter with specified parameters
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=size,
            chunk_overlap=overlap,
            length_function=len,
            separators=self.separators,
        )
        
        logger.info(
            f"Splitting {len(documents)} document(s) -> chunk_size={size}, chunk_overlap={overlap}"
        )
        
        chunks = splitter.split_documents(documents)
        logger.info(f"Created {len(chunks)} chunks")
        
        return chunks
    
    def chunk_documents_with_stats(
        self,
        documents: list[Document],
        chunk_size: int | None = None,
        chunk_overlap: int | None = None
    ) -> dict[str, Any]:
        """
        Split documents into chunks and return statistics.
        
        Args:
            documents: List of Document objects to chunk
            chunk_size: Override default chunk size
            chunk_overlap: Override default chunk overlap
            
        Returns:
            Dictionary with chunks and statistics
        """
        start_time = datetime.now()
        
        chunks = self.chunk_documents(documents, chunk_size, chunk_overlap)
        
        lengths = []
        for chunk in chunks:
            try:
                if chunk.page_content is not None:
                    lengths.append(len(chunk.page_content))
                else:
                    logger.warning("Found chunk with None page_content, skipping in length calculation")
                    lengths.append(0)
            except (AttributeError, TypeError) as exc:
                logger.warning("Error calculating chunk length: %s, using 0", exc)
                lengths.append(0)

        total_chars = sum(lengths) if lengths else 0
        if chunks and lengths:
            avg = total_chars / len(chunks)
        else:
            avg = 0.0

        elapsed = (datetime.now() - start_time).total_seconds()
        
        result: dict[str, Any] = {
            "chunks": chunks,
            "total_chunks": len(chunks),
            "total_characters": total_chars,
            "average_chunk_length": avg,
            "min_chunk_length": min(lengths) if lengths else 0,
            "max_chunk_length": max(lengths) if lengths else 0,
            "processing_time_seconds": elapsed,
        }
        
        logger.info(f"Processing complete: {len(chunks)} chunks in {elapsed:.2f}s")
        return result
    
    # ============================================================================
    # Metadata Management Methods
    # ============================================================================
    
    def inject_chunk_ids(
        self,
        chunks: list[Document],
        file_path: Path | None = None,
        prefix: str | None = None
    ) -> list[str]:
        """
        Inject stable IDs into chunk metadata.
        
        Args:
            chunks: List of Document objects (chunks)
            file_path: Optional file path to use for ID generation
            prefix: Optional prefix for chunk IDs. If None, uses file stem.
            
        Returns:
            List of generated chunk IDs
        """
        chunk_ids: list[str] = []
        
        # Determine prefix
        if prefix is None:
            prefix = file_path.stem if file_path else "chunk"
        
        for idx, chunk in enumerate(chunks):
            # Ensure metadata is a dictionary
            if not isinstance(chunk.metadata, dict):
                chunk.metadata = {}
            
            # Preserve existing ID or generate new one
            if "id" not in chunk.metadata:
                chunk.metadata["id"] = f"{prefix}-chunk-{idx}"
            
            chunk_ids.append(chunk.metadata["id"])
        
        logger.info(f"Injected {len(chunk_ids)} chunk IDs with prefix '{prefix}'")
        return chunk_ids
    
    def add_metadata(
        self,
        documents: list[Document],
        metadata: dict[str, Any],
        overwrite: bool = False
    ) -> list[Document]:
        """
        Add metadata to documents.
        
        Args:
            documents: List of Document objects
            metadata: Dictionary of metadata to add
            overwrite: If True, overwrite existing keys. If False, skip existing keys.
            
        Returns:
            List of Document objects with updated metadata
        """
        for doc in documents:
            if not isinstance(doc.metadata, dict):
                doc.metadata = {}
            
            for key, value in metadata.items():
                if overwrite or key not in doc.metadata:
                    doc.metadata[key] = value
        
        logger.info(f"Added metadata to {len(documents)} documents")
        return documents
    
    def filter_by_metadata(
        self,
        documents: list[Document],
        metadata_filter: dict[str, Any]
    ) -> list[Document]:
        """
        Filter documents by metadata values.
        
        Args:
            documents: List of Document objects
            metadata_filter: Dictionary of metadata key-value pairs to filter by
            
        Returns:
            Filtered list of Document objects
        """
        filtered = []
        
        for doc in documents:
            match = True
            for key, value in metadata_filter.items():
                if doc.metadata.get(key) != value:
                    match = False
                    break
            
            if match:
                filtered.append(doc)
        
        logger.info(f"Filtered {len(documents)} documents to {len(filtered)} matches")
        return filtered
    
    def get_metadata_summary(self, documents: list[Document]) -> dict[str, Any]:
        """
        Get summary of metadata across documents.
        
        Args:
            documents: List of Document objects
            
        Returns:
            Dictionary with metadata summary statistics
        """
        if not documents:
            return {}
        
        all_keys = set()
        for doc in documents:
            if isinstance(doc.metadata, dict):
                all_keys.update(doc.metadata.keys())
        
        key_counts = {}
        for key in all_keys:
            count = sum(1 for doc in documents if key in doc.metadata)
            key_counts[key] = count
        
        return {
            "total_documents": len(documents),
            "metadata_keys": list(all_keys),
            "key_frequency": key_counts
        }
    
    def chunk_and_inject_ids(
        self,
        documents: list[Document],
        file_path: Path | None = None,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        prefix: str | None = None
    ) -> tuple[list[Document], list[str]]:
        """
        Convenience method: Chunk documents and inject IDs in one step.
        
        Args:
            documents: List of Document objects to chunk
            file_path: Optional file path to use for ID generation
            chunk_size: Override default chunk size
            chunk_overlap: Override default chunk overlap
            prefix: Optional prefix for chunk IDs
            
        Returns:
            Tuple of (chunks, chunk_ids)
        """
        chunks = self.chunk_documents(documents, chunk_size, chunk_overlap)
        chunk_ids = self.inject_chunk_ids(chunks, file_path, prefix)
        return chunks, chunk_ids
