"""Keyword ranking and reciprocal-rank fusion for document retrieval."""

from collections.abc import Hashable, Sequence

from llama_index.core.schema import TextNode
from llama_index.retrievers.bm25 import BM25Retriever


def bm25_rank(
    query: str,
    documents: Sequence[tuple[str, str]],
    top_k: int,
) -> list[str]:
    """Return chunk IDs ranked by BM25 score, excluding zero-score matches."""
    if top_k < 1:
        raise ValueError("top_k must be positive")
    if not documents:
        return []

    nodes = [TextNode(id_=chunk_id, text=text) for chunk_id, text in documents]
    retriever = BM25Retriever.from_defaults(
        nodes=nodes,
        similarity_top_k=min(top_k, len(nodes)),
    )
    return [
        node.node_id
        for node in retriever.retrieve(query)
        if node.score is not None and node.score > 0
    ]


def reciprocal_rank_fusion[Item: Hashable](
    rankings: Sequence[Sequence[Item]],
    top_k: int,
    *,
    rank_constant: int = 60,
) -> list[Item]:
    """Merge ranked result lists using reciprocal-rank fusion."""
    if top_k < 1:
        raise ValueError("top_k must be positive")
    if rank_constant < 0:
        raise ValueError("rank_constant cannot be negative")

    scores: dict[Item, float] = {}
    for ranking in rankings:
        seen: set[Item] = set()
        for rank, item in enumerate(ranking, start=1):
            if item in seen:
                continue
            seen.add(item)
            scores[item] = scores.get(item, 0.0) + 1.0 / (
                rank_constant + rank
            )
    return sorted(scores, key=scores.__getitem__, reverse=True)[:top_k]
