"""Library repository extensions for chunks, embedding runs, and tracking."""

from __future__ import annotations

import json
from datetime import datetime
from uuid import UUID

from psycopg import AsyncConnection

from infrastructure.postgres.transaction import execute, fetch_all, fetch_one


# ── Chunks ──────────────────────────────────────────────────────────────


async def create_chunks(conn: AsyncConnection, chunks: list[dict]) -> int:
    """Insert multiple chunks. Returns count inserted."""
    if not chunks:
        return 0
    for c in chunks:
        await execute(
            conn,
            """
            INSERT INTO library_document_chunks
                (id, document_id, document_text_id, collection_id, chunk_index, chunk_uid,
                 language, content, content_sha256, content_length, token_count_estimate,
                 char_start, char_end, page_start, page_end, chapter, section, metadata,
                 created_at, updated_at)
            VALUES
                (%(id)s, %(document_id)s, %(document_text_id)s, %(collection_id)s, %(chunk_index)s, %(chunk_uid)s,
                 %(language)s, %(content)s, %(content_sha256)s, %(content_length)s, %(token_count_estimate)s,
                 %(char_start)s, %(char_end)s, %(page_start)s, %(page_end)s, %(chapter)s, %(section)s, %(metadata)s,
                 %(created_at)s, %(updated_at)s)
            ON CONFLICT (chunk_uid) DO NOTHING
            """,
            {
                "id": str(c["id"]),
                "document_id": str(c["document_id"]),
                "document_text_id": str(c["document_text_id"]),
                "collection_id": str(c["collection_id"]),
                "chunk_index": c["chunk_index"],
                "chunk_uid": c["chunk_uid"],
                "language": c["language"],
                "content": c["content"],
                "content_sha256": c["content_sha256"],
                "content_length": c["content_length"],
                "token_count_estimate": c.get("token_count_estimate"),
                "char_start": c.get("char_start"),
                "char_end": c.get("char_end"),
                "page_start": c.get("page_start"),
                "page_end": c.get("page_end"),
                "chapter": c.get("chapter"),
                "section": c.get("section"),
                "metadata": json.dumps(c.get("metadata", {})),
                "created_at": c.get("created_at", datetime.utcnow()),
                "updated_at": c.get("updated_at", datetime.utcnow()),
            },
        )
    return len(chunks)


async def get_chunks_by_document(conn: AsyncConnection, document_id: UUID) -> list[dict]:
    rows = await fetch_all(
        conn,
        "SELECT * FROM library_document_chunks WHERE document_id = %(document_id)s ORDER BY chunk_index",
        {"document_id": str(document_id)},
    )
    return rows


async def get_unindexed_chunks(
    conn: AsyncConnection,
    collection_id: UUID | None = None,
    limit: int = 5000,
) -> list[dict]:
    """Get chunks that don't have an embedding record yet."""
    if collection_id:
        rows = await fetch_all(
            conn,
            """
            SELECT c.*, d.title AS doc_title
            FROM library_document_chunks c
            JOIN library_documents d ON d.id = c.document_id
            LEFT JOIN library_chunk_embeddings e ON e.chunk_id = c.id
            WHERE c.collection_id = %(collection_id)s AND e.id IS NULL
            ORDER BY c.chunk_index
            LIMIT %(limit)s
            """,
            {"collection_id": str(collection_id), "limit": limit},
        )
    else:
        rows = await fetch_all(
            conn,
            """
            SELECT c.*, d.title AS doc_title
            FROM library_document_chunks c
            JOIN library_documents d ON d.id = c.document_id
            LEFT JOIN library_chunk_embeddings e ON e.chunk_id = c.id
            WHERE e.id IS NULL
            ORDER BY c.chunk_index
            LIMIT %(limit)s
            """,
            {"limit": limit},
        )
    return rows


async def count_chunks(conn: AsyncConnection, collection_id: UUID | None = None) -> int:
    if collection_id:
        row = await fetch_one(
            conn,
            "SELECT COUNT(*) AS cnt FROM library_document_chunks WHERE collection_id = %(collection_id)s",
            {"collection_id": str(collection_id)},
        )
    else:
        row = await fetch_one(conn, "SELECT COUNT(*) AS cnt FROM library_document_chunks")
    return row["cnt"] if row else 0


# ── Embedding runs ──────────────────────────────────────────────────────


async def create_embedding_run(
    conn: AsyncConnection,
    run_data: dict,
) -> dict:
    now = datetime.utcnow()
    params = {
        "id": str(run_data["id"]),
        "collection_code": run_data["collection_code"],
        "milvus_collection": run_data["milvus_collection"],
        "embedding_provider": run_data["embedding_provider"],
        "embedding_model": run_data["embedding_model"],
        "embedding_dimension": run_data["embedding_dimension"],
        "status": run_data.get("status", "pending"),
        "chunks_total": run_data.get("chunks_total", 0),
        "metadata": json.dumps(run_data.get("metadata", {})),
        "started_at": now,
    }
    await execute(
        conn,
        """
        INSERT INTO library_embedding_runs
            (id, collection_code, milvus_collection, embedding_provider, embedding_model,
             embedding_dimension, status, chunks_total, metadata, started_at)
        VALUES
            (%(id)s, %(collection_code)s, %(milvus_collection)s, %(embedding_provider)s,
             %(embedding_model)s, %(embedding_dimension)s, %(status)s, %(chunks_total)s,
             %(metadata)s, %(started_at)s)
        """,
        params,
    )
    return params


async def update_embedding_run(
    conn: AsyncConnection,
    run_id: UUID,
    status: str,
    chunks_embedded: int = 0,
    chunks_indexed: int = 0,
    error_message: str | None = None,
) -> None:
    now = datetime.utcnow()
    await execute(
        conn,
        """
        UPDATE library_embedding_runs SET
            status = %(status)s,
            chunks_embedded = %(chunks_embedded)s,
            chunks_indexed = %(chunks_indexed)s,
            error_message = %(error_message)s,
            finished_at = %(finished_at)s
        WHERE id = %(id)s
        """,
        {
            "id": str(run_id),
            "status": status,
            "chunks_embedded": chunks_embedded,
            "chunks_indexed": chunks_indexed,
            "error_message": error_message,
            "finished_at": now,
        },
    )


# ── Chunk embeddings tracking ───────────────────────────────────────────


async def create_chunk_embedding(
    conn: AsyncConnection,
    chunk_id: UUID,
    run_id: UUID,
    provider: str,
    model: str,
    dimension: int,
    milvus_collection: str,
    milvus_pk: str,
    content_sha256: str,
    status: str = "indexed",
) -> None:
    from uuid import uuid4
    await execute(
        conn,
        """
        INSERT INTO library_chunk_embeddings
            (id, chunk_id, embedding_run_id, embedding_provider, embedding_model,
             embedding_dimension, milvus_collection, milvus_primary_key, content_sha256,
             status, created_at)
        VALUES
            (%(id)s, %(chunk_id)s, %(embedding_run_id)s, %(embedding_provider)s,
             %(embedding_model)s, %(embedding_dimension)s, %(milvus_collection)s,
             %(milvus_primary_key)s, %(content_sha256)s, %(status)s, %(created_at)s)
        ON CONFLICT (chunk_id, embedding_provider, embedding_model, milvus_collection)
        DO UPDATE SET status = %(status)s, milvus_primary_key = %(milvus_primary_key)s
        """,
        {
            "id": str(uuid4()),
            "chunk_id": str(chunk_id),
            "embedding_run_id": str(run_id),
            "embedding_provider": provider,
            "embedding_model": model,
            "embedding_dimension": dimension,
            "milvus_collection": milvus_collection,
            "milvus_primary_key": milvus_pk,
            "content_sha256": content_sha256,
            "status": status,
            "created_at": datetime.utcnow(),
        },
    )
