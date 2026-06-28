"""Milvus client — connection, collection management, insert, search."""

from __future__ import annotations

from typing import Any

from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, MilvusClient as RawClient, connections, utility

from globalVar import MILVUS_HOST, MILVUS_PORT, MILVUS_CONNECT_TIMEOUT_SECONDS
from infrastructure.milvus.errors import (
    MilvusCollectionError,
    MilvusConnectionError,
    MilvusDimensionMismatchError,
    MilvusInsertError,
    MilvusSearchError,
)

# ── Collection schema builder ────────────────────────────────────────────

BRESLOV_FIELDS: list[FieldSchema] = [
    FieldSchema(name="pk", dtype=DataType.VARCHAR, is_primary=True, max_length=128),
    FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=64),
    FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=64),
    FieldSchema(name="collection_code", dtype=DataType.VARCHAR, max_length=64),
    FieldSchema(name="language", dtype=DataType.VARCHAR, max_length=8),
    FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=512),
    FieldSchema(name="source_type", dtype=DataType.VARCHAR, max_length=32),
    FieldSchema(name="source_sha256", dtype=DataType.VARCHAR, max_length=64),
    FieldSchema(name="content_sha256", dtype=DataType.VARCHAR, max_length=64),
    FieldSchema(name="chunk_index", dtype=DataType.INT64),
    FieldSchema(name="page_start", dtype=DataType.INT64),
    FieldSchema(name="page_end", dtype=DataType.INT64),
    FieldSchema(name="content_preview", dtype=DataType.VARCHAR, max_length=1024),
    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=1536),
]

BRESLOV_SCHEMA = CollectionSchema(
    BRESLOV_FIELDS,
    description="TebaAI Breslov document chunks with embeddings",
)

BRESLOV_INDEX_PARAMS: dict[str, Any] = {
    "index_type": "HNSW",
    "metric_type": "COSINE",
    "params": {"M": 16, "efConstruction": 200},
}

BRESLOV_SEARCH_PARAMS: dict[str, Any] = {
    "metric_type": "COSINE",
    "params": {"ef": 64},
}


# ── Connection ──────────────────────────────────────────────────────────

def create_connection() -> None:
    try:
        connections.connect(
            alias="default",
            host=MILVUS_HOST,
            port=MILVUS_PORT,
            timeout=MILVUS_CONNECT_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        raise MilvusConnectionError(f"Failed to connect to Milvus at {MILVUS_HOST}:{MILVUS_PORT}: {exc}") from exc


def close_connection() -> None:
    try:
        connections.disconnect("default")
    except Exception:
        pass


# ── Collection management ───────────────────────────────────────────────

def list_collections() -> list[str]:
    try:
        return utility.list_collections()
    except Exception as exc:
        raise MilvusCollectionError(f"Failed to list collections: {exc}") from exc


def collection_exists(name: str) -> bool:
    return name in utility.list_collections()


def ensure_collection(
    name: str,
    schema: CollectionSchema | None = None,
    index_params: dict[str, Any] | None = None,
    dimension: int = 1536,
) -> Collection:
    """Create collection if not exists; validate dimension if exists."""
    if schema is None:
        fields = list(BRESLOV_FIELDS)
        for i, f in enumerate(fields):
            if f.name == "embedding":
                fields[i] = FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dimension)
                break
        schema = CollectionSchema(fields, description=f"TebaAI vector collection (dim={dimension})")

    create_connection()
    try:
        if not collection_exists(name):
            col = Collection(name=name, schema=schema)
            col.create_index(field_name="embedding", index_params=index_params or BRESLOV_INDEX_PARAMS)
            col.load()
            return col
        else:
            col = Collection(name=name)
            col.load()
            # Validate dimension
            desc = col.describe()
            for f in desc.get("fields", []):
                if f["name"] == "embedding":
                    existing_dim = f["params"]["dim"]
                    if existing_dim != dimension:
                        raise MilvusDimensionMismatchError(
                            f"Collection '{name}' has dimension {existing_dim}, "
                            f"requested {dimension}. Recreate or use correct dimension."
                        )
                    break
            return col
    except MilvusDimensionMismatchError:
        raise
    except Exception as exc:
        raise MilvusCollectionError(f"Failed to ensure collection '{name}': {exc}") from exc


# ── Insert ──────────────────────────────────────────────────────────────

def insert_vectors(
    collection_name: str,
    vectors: list[dict[str, Any]],
    batch_size: int = 100,
) -> int:
    """Insert vectors into Milvus collection. Returns count inserted."""
    if not vectors:
        return 0
    try:
        col = Collection(name=collection_name)
        total = 0
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i : i + batch_size]
            col.insert(batch)
            total += len(batch)
        col.flush()
        return total
    except Exception as exc:
        raise MilvusInsertError(f"Failed to insert {len(vectors)} vectors: {exc}") from exc


# ── Search ──────────────────────────────────────────────────────────────

def search_vectors(
    collection_name: str,
    query_embedding: list[float],
    top_k: int = 10,
    output_fields: list[str] | None = None,
    search_params: dict[str, Any] | None = None,
    expr: str | None = None,
) -> list[dict[str, Any]]:
    """Search Milvus. Returns list of {id, distance, fields...}."""
    try:
        col = Collection(name=collection_name)
        col.load()

        params = search_params or BRESLOV_SEARCH_PARAMS
        fields = output_fields or ["chunk_id", "title", "content_preview", "chunk_index", "document_id", "collection_code"]

        results = col.search(
            data=[query_embedding],
            anns_field="embedding",
            param=params,
            limit=top_k,
            expr=expr,
            output_fields=output_fields or fields,
        )

        hits: list[dict[str, Any]] = []
        for hits_group in results:
            for hit in hits_group:
                entry = {
                    "id": hit.id,
                    "distance": hit.distance,
                }
                if hit.entity:
                    for f in (output_fields or fields):
                        val = hit.entity.get(f)
                        if val is not None:
                            entry[f] = val
                hits.append(entry)
        return hits
    except Exception as exc:
        raise MilvusSearchError(f"Search failed: {exc}") from exc
