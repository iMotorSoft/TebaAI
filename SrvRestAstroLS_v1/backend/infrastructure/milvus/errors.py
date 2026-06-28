"""Milvus infrastructure errors."""

from __future__ import annotations


class MilvusError(Exception):
    """Base Milvus error."""


class MilvusConnectionError(MilvusError):
    """Failed to connect to Milvus."""


class MilvusCollectionError(MilvusError):
    """Collection operation failed."""


class MilvusDimensionMismatchError(MilvusError):
    """Embedding dimension does not match collection schema."""


class MilvusInsertError(MilvusError):
    """Failed to insert vectors into Milvus."""


class MilvusSearchError(MilvusError):
    """Search query failed."""
