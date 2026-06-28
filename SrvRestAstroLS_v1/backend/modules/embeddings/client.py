"""Embeddings client using LiteLLM API-compatible provider."""

from __future__ import annotations

import time
from typing import Any

import httpx

from globalVar import (
    EMBEDDINGS_API_KEY,
    EMBEDDINGS_BASE_URL,
    EMBEDDINGS_BATCH_SIZE,
    EMBEDDINGS_DIMENSION,
    EMBEDDINGS_MODEL_ALIAS,
    EMBEDDINGS_TIMEOUT_SECONDS,
)
from modules.embeddings.errors import EmbeddingsBatchError, EmbeddingsProviderError


def embed_text(text: str, model: str | None = None) -> list[float]:
    """Embed a single text string. Returns embedding vector."""
    results = embed_batch([text], model=model)
    return results[0]


def embed_batch(texts: list[str], model: str | None = None) -> list[list[float]]:
    """Embed a batch of texts. Returns list of embedding vectors."""
    if not texts:
        return []

    model_name = model or EMBEDDINGS_MODEL_ALIAS
    url = f"{EMBEDDINGS_BASE_URL}/v1/embeddings"
    headers: dict[str, str] = {
        "Content-Type": "application/json",
    }
    if EMBEDDINGS_API_KEY:
        headers["Authorization"] = f"Bearer {EMBEDDINGS_API_KEY}"

    all_embeddings: list[list[float]] = []
    batch_size = EMBEDDINGS_BATCH_SIZE

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        payload = {"model": model_name, "input": batch}

        try:
            with httpx.Client(timeout=EMBEDDINGS_TIMEOUT_SECONDS) as client:
                resp = client.post(url, json=payload, headers=headers)
        except Exception as exc:
            raise EmbeddingsProviderError(
                f"Embeddings request failed (batch {i}-{i+len(batch)}): {exc}"
            ) from exc

        if resp.status_code != 200:
            raise EmbeddingsProviderError(
                f"Embeddings API returned {resp.status_code}: {resp.text[:200]}"
            )

        try:
            data = resp.json()
            for item in data.get("data", []):
                all_embeddings.append(item["embedding"])
        except (KeyError, ValueError) as exc:
            raise EmbeddingsProviderError(
                f"Failed to parse embeddings response: {exc}"
            ) from exc

    return all_embeddings


def validate_embedding_dimension(text: str = "test", model: str | None = None) -> int:
    """Validate that the embedding model returns the expected dimension."""
    vec = embed_text(text, model=model)
    actual = len(vec)
    if actual != EMBEDDINGS_DIMENSION:
        raise EmbeddingsProviderError(
            f"Embedding dimension mismatch: expected {EMBEDDINGS_DIMENSION}, got {actual}"
        )
    return actual
