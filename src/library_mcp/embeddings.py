"""Embedding generation with pluggable providers (local sentence-transformers or OpenAI)."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from .models import EmbeddingsConfig, EmbeddingProvider

logger = logging.getLogger(__name__)


class EmbeddingFunc(ABC):
    """Abstract base for embedding providers."""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts."""

    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding dimension."""


class LocalEmbeddings(EmbeddingFunc):
    """Sentence-transformers running locally."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer

        logger.info(f"Loading local embedding model: {model_name}")
        self._model = SentenceTransformer(model_name)
        self._dimension = self._model.get_sentence_embedding_dimension()

    def embed(self, texts: list[str]) -> list[list[float]]:
        embeddings = self._model.encode(texts, show_progress_bar=False)
        return embeddings.tolist()

    def dimension(self) -> int:
        return self._dimension


class OpenAIEmbeddings(EmbeddingFunc):
    """OpenAI API embeddings."""

    def __init__(self, model_name: str = "text-embedding-3-small"):
        import openai

        self._client = openai.OpenAI()
        self._model = model_name
        # Known dimensions for OpenAI models
        self._dimensions = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
        }

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self._client.embeddings.create(input=texts, model=self._model)
        return [item.embedding for item in response.data]

    def dimension(self) -> int:
        return self._dimensions.get(self._model, 1536)


def create_embedder(config: EmbeddingsConfig | None = None) -> EmbeddingFunc:
    """Factory: create the appropriate embedding provider from config."""
    if config is None:
        config = EmbeddingsConfig()

    if config.provider == EmbeddingProvider.OPENAI:
        return OpenAIEmbeddings(model_name=config.model)
    return LocalEmbeddings(model_name=config.model)


def embed_in_batches(
    embedder: EmbeddingFunc,
    texts: list[str],
    batch_size: int = 64,
) -> list[list[float]]:
    """Embed texts in batches to manage memory."""
    all_embeddings: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        all_embeddings.extend(embedder.embed(batch))
    return all_embeddings
