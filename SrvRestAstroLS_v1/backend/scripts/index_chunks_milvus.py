#! /usr/bin/env python3
"""
CLI: Index document chunks to Milvus with embeddings.

Usage:
    uv run python -m scripts.index_chunks_milvus --collection breslov \\
        --milvus-collection tebaai_breslov_chunks_v1 \\
        --embedding-model openai_text_embedding_3_small \\
        --batch-size 16
"""

from __future__ import annotations

import argparse
import asyncio
import sys

import globalVar


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Index document chunks to Milvus.")
    parser.add_argument("--collection", required=True, help="Collection code to index")
    parser.add_argument("--milvus-collection", default=globalVar.MILVUS_COLLECTION_BRESLOV, help="Milvus collection name")
    parser.add_argument("--embedding-model", default=globalVar.EMBEDDINGS_MODEL_ALIAS, help="Embedding model name")
    parser.add_argument("--embedding-dimension", type=int, default=globalVar.EMBEDDINGS_DIMENSION, help="Embedding dimension")
    parser.add_argument("--batch-size", type=int, default=globalVar.EMBEDDINGS_BATCH_SIZE, help="Batch size for embeddings")
    parser.add_argument("--chunk-size-chars", type=int, default=1800, help="Max chars per chunk")
    parser.add_argument("--chunk-overlap-chars", type=int, default=250, help="Overlap between chunks")
    parser.add_argument("--min-chunk-chars", type=int, default=200, help="Min chars per chunk")
    return parser.parse_args(argv)


async def _run(args: argparse.Namespace) -> int:
    from core.config import get_settings
    from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool

    settings = get_settings()
    if not settings.postgres_enabled:
        print("ERROR: TEBAAI_POSTGRES_ENABLED is not true", file=sys.stderr)
        return 1

    pool = create_pool_from_settings()
    await open_pool(pool)

    try:
        async with pool.connection() as conn:
            from psycopg.rows import dict_row
            conn.row_factory = dict_row
            cur = conn.cursor()
            await cur.execute("SELECT current_database()")
            db = (await cur.fetchone())["current_database"]
            if db != "tebaai":
                print(f"ERROR: Expected 'tebaai', got '{db}'", file=sys.stderr)
                return 1

            # Get collection
            await cur.execute("SELECT id, code FROM library_collections WHERE code = %(code)s", {"code": args.collection})
            col = await cur.fetchone()
            if not col:
                print(f"ERROR: Collection '{args.collection}' not found", file=sys.stderr)
                return 1

            print(f"Collection: {col['code']} ({col['id']})")
            print(f"Milvus collection: {args.milvus_collection}")
            print(f"Embedding model: {args.embedding_model}")
            print(f"Dimension: {args.embedding_dimension}")

        # Run indexing in a transaction
        async with pool.connection() as write_conn:
            write_conn.row_factory = dict_row
            from infrastructure.postgres.transaction import transaction
            from modules.library.indexing_service import index_collection

            result = await index_collection(
                write_conn,
                collection_id=col["id"],
                collection_code=col["code"],
                milvus_collection_name=args.milvus_collection,
                chunk_size=args.chunk_size_chars,
                chunk_overlap=args.chunk_overlap_chars,
                min_chunk=args.min_chunk_chars,
                embedding_model=args.embedding_model,
                embedding_dimension=args.embedding_dimension,
                batch_size=args.batch_size,
            )

        print()
        print("── Indexing complete ──")
        print(f"  Run ID:         {result.get('run_id', 'N/A')}")
        print(f"  Collection:     {result.get('collection_code', 'N/A')}")
        print(f"  Chunks created: {result.get('chunks_created', 0)}")
        print(f"  Chunks embedded:{result.get('chunks_embedded', 0)}")
        print(f"  Chunks indexed: {result.get('chunks_indexed', 0)}")
        print(f"  Status:         {result.get('status', 'unknown')}")
        if result.get("error"):
            print(f"  Error:          {result['error']}")
        print()

        if result.get("status") == "failed":
            return 1
        return 0

    finally:
        await close_pool(pool)


def main() -> int:
    args = _parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
