"""Embeddings module errors."""

from __future__ import annotations


class EmbeddingsError(Exception):
    """Base embeddings error."""


class EmbeddingsProviderError(EmbeddingsError):
    """Embeddings provider returned an error."""


class EmbeddingsDimensionMismatchError(EmbeddingsError):
    """Embedding dimension does not match expected dimension."""


class EmbeddingsBatchError(EmbeddingsError):
    """Batch embedding failed partially."""
