from typing import Self

import pytest

from agents.control_plane import DocumentRetrievalAgent, QueryContext
from services.fusion_retrieval import bm25_rank, reciprocal_rank_fusion


class FakeEmbedder:
    dimensions = 1536

    def __init__(self) -> None:
        self.queries: list[list[str]] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.queries.append(texts)
        return [[0.0] * self.dimensions]


class FakeMappings:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows

    def mappings(self) -> "FakeMappings":
        return self

    def all(self) -> list[dict[str, object]]:
        return self.rows


class FakeConnection:
    def __init__(
        self,
        vector_rows: list[dict[str, object]],
        keyword_rows: list[dict[str, object]],
    ) -> None:
        self.results = [vector_rows, keyword_rows]
        self.statements: list[object] = []

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, exception_type: object, exception: object, traceback: object
    ) -> None:
        del exception_type, exception, traceback

    def execute(self, statement: object) -> FakeMappings:
        self.statements.append(statement)
        return FakeMappings(self.results.pop(0))


class FakeEngine:
    def __init__(
        self,
        vector_rows: list[dict[str, object]],
        keyword_rows: list[dict[str, object]],
    ) -> None:
        self.connection = FakeConnection(vector_rows, keyword_rows)

    def connect(self) -> FakeConnection:
        return self.connection


def _chunk(chunk_id: str, chunk_text: str) -> dict[str, object]:
    return {
        "chunk_id": chunk_id,
        "chunk_text": chunk_text,
        "page_start": 1,
        "section_path": "Risk policy",
        "document_version_id": f"version-{chunk_id}",
        "version_label": "current",
        "source_key": f"source-{chunk_id}",
        "title": f"Policy {chunk_id}",
        "source_type": "policy",
    }


def test_bm25_retrieves_exact_finance_terms() -> None:
    ranked = bm25_rank(
        "Basel liquidity stress",
        [
            ("policy-1", "Basel III liquidity stress requirements."),
            ("policy-2", "Portfolio market exposure policy."),
        ],
        top_k=2,
    )

    assert ranked[0] == "policy-1"
    assert "policy-2" not in ranked


@pytest.mark.asyncio
async def test_document_agent_fuses_vector_and_bm25_rankings() -> None:
    vector_rows = [
        _chunk("portfolio", "Portfolio allocation and target exposures."),
        _chunk("basel", "Basel liquidity stress requirements."),
    ]
    keyword_rows = [
        _chunk("portfolio", "Portfolio allocation and target exposures."),
        _chunk("basel", "Basel liquidity stress requirements."),
    ]
    engine = FakeEngine(vector_rows, keyword_rows)
    embedder = FakeEmbedder()
    agent = DocumentRetrievalAgent(engine, embedder, top_k=2)  # type: ignore[arg-type]

    result = await agent.run(
        QueryContext(
            query_id="query-1",
            question="Basel liquidity stress",
            portfolio_id=None,
        )
    )

    assert [item.citation.source_id for item in result.evidence] == [
        "source-basel",
        "source-portfolio",
    ]
    assert result.evidence[0].content == "Basel liquidity stress requirements."
    assert embedder.queries == [["Basel liquidity stress"]]
    assert len(engine.connection.statements) == 2
    compiled = engine.connection.statements[0].compile()
    assert "source_documents.access_classification" in str(
        engine.connection.statements[0]
    )
    assert "internal" in compiled.params.values()


def test_reciprocal_rank_fusion_promotes_shared_relevant_results() -> None:
    ranked = reciprocal_rank_fusion(
        (["vector-a", "shared", "vector-b"], ["shared", "keyword-a"]),
        top_k=3,
    )

    assert ranked == ["shared", "vector-a", "keyword-a"]


@pytest.mark.parametrize("top_k", [0, -1])
def test_retrievers_reject_nonpositive_limits(top_k: int) -> None:
    with pytest.raises(ValueError, match="top_k must be positive"):
        reciprocal_rank_fusion((["item"],), top_k=top_k)

    with pytest.raises(ValueError, match="top_k must be positive"):
        bm25_rank("query", [("item", "text")], top_k=top_k)
