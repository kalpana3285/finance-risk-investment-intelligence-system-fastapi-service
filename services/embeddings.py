"""Embedding providers for storing document vectors in pgvector."""

import math
from typing import Protocol

from openai import APIConnectionError, APIError, APITimeoutError, AsyncAzureOpenAI

from services.database import EMBEDDING_DIMENSIONS
from services.langfuse_tracing import observation


class EmbeddingProviderError(RuntimeError):
    """Raised when an embedding provider fails or returns invalid vectors."""


class EmbeddingProvider(Protocol):
    dimensions: int

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class AzureOpenAIEmbedder:
    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str,
        api_version: str,
        deployment: str,
        dimensions: int = 1536,
        timeout_seconds: float = 30.0,
    ) -> None:
        if not all((endpoint, api_key, api_version, deployment)):
            raise ValueError("Azure OpenAI embedding settings are required")
        if dimensions != EMBEDDING_DIMENSIONS:
            raise ValueError(
                "The current pgvector schema requires "
                f"{EMBEDDING_DIMENSIONS}-dimensional embeddings"
            )
        self.deployment = deployment
        self.api_version = api_version
        self.dimensions = dimensions
        self._client = AsyncAzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
            timeout=timeout_seconds,
            max_retries=2,
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            with observation(
                name="azure-openai-embeddings",
                as_type="embedding",
                input={"text_count": len(texts), "content_captured": False},
                model=self.deployment,
            ) as span:
                response = await self._client.embeddings.create(
                    model=self.deployment,
                    input=texts,
                    dimensions=self.dimensions,
                )
                if span is not None:
                    usage = getattr(response, "usage", None)
                    tokens = getattr(usage, "prompt_tokens", None)
                    update: dict[str, object] = {
                        "output": {"vector_count": len(response.data)}
                    }
                    if isinstance(tokens, int):
                        update["usage_details"] = {"input": tokens}
                    span.update(
                        **update,
                    )
        except (APIConnectionError, APITimeoutError, APIError) as exc:
            raise EmbeddingProviderError(
                "Azure OpenAI embedding request failed"
            ) from exc
        vectors = [
            item.embedding for item in sorted(response.data, key=lambda item: item.index)
        ]
        if len(vectors) != len(texts):
            raise EmbeddingProviderError(
                "Embedding provider returned an unexpected number of vectors"
            )
        for vector in vectors:
            if len(vector) != self.dimensions:
                raise EmbeddingProviderError(
                    "Embedding provider returned a vector with the wrong dimensions"
                )
            if not all(math.isfinite(value) for value in vector):
                raise EmbeddingProviderError(
                    "Embedding provider returned a non-finite vector value"
                )
        return vectors

    async def aclose(self) -> None:
        await self._client.close()
