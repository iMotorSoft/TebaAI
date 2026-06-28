"""Indexing service — orchestrates chunking, embeddings, and Milvus insertion."""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID, uuid4

from psycopg import AsyncConnection

from globalVar import (
    EMBEDDINGS_BATCH_SIZE,
    EMBEDDINGS_DIMENSION,
    EMBEDDINGS_MODEL_ALIAS,
)
from modules.embeddings.client import embed_batch
from infrastructure.milvus.client import (
    ensure_collection,
    insert_vectors,
)
from modules.library.chunking import chunk_text as chunk_document_text
from modules.library.vector_repository import (
    count_chunks,
    create_chunk_embedding,
    create_chunks,
    create_embedding_run,
    get_unindexed_chunks,
    update_embedding_run,
)

logger = logging.getLogger(__name__)


# @lat: [[library-retrieval-models-policy#Semantic / Vector Search]]
async def index_collection(
    conn: AsyncConnection,
    collection_id: UUID,
    collection_code: str,
    milvus_collection_name: str,
    chunk_size: int = 1800,
    chunk_overlap: int = 250,
    min_chunk: int = 200,
    embedding_model: str | None = None,
    embedding_dimension: int | None = None,
    batch_size: int | None = None,
) -> dict:
    """Full pipeline: chunk un-chunked docs → embed → insert to Milvus."""
    model = embedding_model or EMBEDDINGS_MODEL_ALIAS
    dim = embedding_dimension or EMBEDDINGS_DIMENSION
    bs = batch_size or EMBEDDINGS_BATCH_SIZE

    # Ensure Milvus collection exists
    ensure_collection(milvus_collection_name, dimension=dim)

    # Create embedding run record
    run_id = uuid4()
    run_data = {
        "id": run_id,
        "collection_code": collection_code,
        "milvus_collection": milvus_collection_name,
        "embedding_provider": "litellm",
        "embedding_model": model,
        "embedding_dimension": dim,
        "status": "running",
        "chunks_total": 0,
    }
    await create_embedding_run(conn, run_data)

    # 1. Get documents without chunks
    from infrastructure.postgres.transaction import fetch_all as fa
    docs = await fa(
        conn,
        """
        SELECT d.id AS doc_id, t.id AS text_id, d.title, d.language,
               d.collection_id, t.content, c.code AS collection_code
        FROM library_documents d
        JOIN library_document_texts t ON t.document_id = d.id
        JOIN library_collections c ON c.id = d.collection_id
        WHERE d.collection_id = %(collection_id)s
          AND d.status = 'ready'
          AND NOT EXISTS (
              SELECT 1 FROM library_document_chunks ch
              WHERE ch.document_id = d.id
          )
        """,
        {"collection_id": str(collection_id)},
    )

    total_chunks = 0
    for doc in docs:
        chunks = chunk_document_text(
            doc["content"],
            doc["doc_id"],
            doc["text_id"],
            language=doc["language"],
            chunk_size=chunk_size,
            overlap=chunk_overlap,
            min_chunk=min_chunk,
        )
        for c in chunks:
            c["collection_id"] = doc["collection_id"]
            c["page_start"] = None
            c["page_end"] = None
            c["chapter"] = None
            c["section"] = None
            c["metadata"] = {}
            c["created_at"] = datetime.utcnow()
            c["updated_at"] = datetime.utcnow()
        if chunks:
            await create_chunks(conn, chunks)
            total_chunks += len(chunks)

    # 2. Get unindexed chunks
    unindexed = await get_unindexed_chunks(conn, collection_id=collection_id)
    if not unindexed:
        await update_embedding_run(conn, run_id, "completed")
        return {
            "run_id": str(run_id),
            "collection_code": collection_code,
            "chunks_created": total_chunks,
            "chunks_embedded": 0,
            "chunks_indexed": 0,
            "status": "completed",
            "message": "No unindexed chunks found",
        }

    # 3. Embed in batches and insert to Milvus
    chunks_embedded = 0
    chunks_indexed = 0
    milvus_vectors: list[dict] = []

    for i in range(0, len(unindexed), bs):
        batch = unindexed[i : i + bs]
        texts = [c["content"] for c in batch]

        try:
            embeddings = embed_batch(texts, model=model)
        except Exception as exc:
            logger.error("Embedding batch failed at chunk %d: %s", i, exc)
            await update_embedding_run(conn, run_id, "failed", error_message=str(exc))
            return {"status": "failed", "error": str(exc)}

        for j, chunk in enumerate(batch):
            vec = embeddings[j]
            milvus_vectors.append({
                "pk": chunk["chunk_uid"],
                "chunk_id": str(chunk["id"]),
                "document_id": str(chunk["document_id"]),
                "collection_code": collection_code,
                "language": chunk["language"],
                "title": chunk.get("doc_title", ""),
                "source_type": "",
                "source_sha256": "",
                "content_sha256": chunk["content_sha256"],
                "chunk_index": chunk["chunk_index"],
                "page_start": 0,
                "page_end": 0,
                "content_preview": chunk["content"][:200],
                "embedding": vec,
            })

        chunks_embedded += len(batch)

        # Insert to Milvus
        if milvus_vectors:
            try:
                inserted = insert_vectors(milvus_collection_name, milvus_vectors)
                chunks_indexed += inserted

                # Track in PG
                for vec_item in milvus_vectors:
                    await create_chunk_embedding(
                        conn=conn,
                        chunk_id=UUID(vec_item["chunk_id"]),
                        run_id=run_id,
                        provider="litellm",
                        model=model,
                        dimension=dim,
                        milvus_collection=milvus_collection_name,
                        milvus_pk=vec_item["pk"],
                        content_sha256=vec_item["content_sha256"],
                    )
                milvus_vectors = []
            except Exception as exc:
                logger.error("Milvus insert failed: %s", exc)
                await update_embedding_run(conn, run_id, "failed", error_message=str(exc))
                return {"status": "failed", "error": str(exc)}

    # Flush remaining
    if milvus_vectors:
        try:
            inserted = insert_vectors(milvus_collection_name, milvus_vectors)
            chunks_indexed += inserted
            for vec_item in milvus_vectors:
                await create_chunk_embedding(
                    conn=conn,
                    chunk_id=UUID(vec_item["chunk_id"]),
                    run_id=run_id,
                    provider="litellm",
                    model=model,
                    dimension=dim,
                    milvus_collection=milvus_collection_name,
                    milvus_pk=vec_item["pk"],
                    content_sha256=vec_item["content_sha256"],
                )
        except Exception as exc:
            logger.error("Milvus final flush failed: %s", exc)
            await update_embedding_run(conn, run_id, "failed", error_message=str(exc))
            return {"status": "failed", "error": str(exc)}

    await update_embedding_run(
        conn, run_id, "completed",
        chunks_embedded=chunks_embedded,
        chunks_indexed=chunks_indexed,
    )

    return {
        "run_id": str(run_id),
        "collection_code": collection_code,
        "chunks_created": total_chunks,
        "chunks_embedded": chunks_embedded,
        "chunks_indexed": chunks_indexed,
        "status": "completed",
    }
