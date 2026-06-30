#! /usr/bin/env python3
"""
CLI: Index document chunks to Milvus with embeddings.

Supports production (breslov → tebaai_breslov_chunks_v1) and
test (breslov_test → tebaai_breslov_test_chunks_v1) collections
with explicit safety guards to prevent cross-contamination.

Usage:
    # Production (chunks + embed + index)
    uv run python -m scripts.index_chunks_milvus --collection breslov

    # Test dry-run
    uv run python -m scripts.index_chunks_milvus \\
        --collection breslov_test \\
        --document-title "El Alma del Rebe Najmán" \\
        --milvus-collection tebaai_breslov_test_chunks_v1 \\
        --dry-run

    # Test apply
    uv run python -m scripts.index_chunks_milvus \\
        --collection breslov_test \\
        --document-title "El Alma del Rebe Najmán" \\
        --milvus-collection tebaai_breslov_test_chunks_v1 \\
        --apply
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from uuid import UUID

import globalVar


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Index document chunks to Milvus.")
    parser.add_argument("--collection", required=True, help="PostgreSQL collection code")
    parser.add_argument("--document-title", help="Only process this document title")
    parser.add_argument("--milvus-collection", default=globalVar.MILVUS_COLLECTION_BRESLOV,
                        help="Milvus collection name")
    parser.add_argument("--embedding-model", default=globalVar.EMBEDDINGS_MODEL_ALIAS,
                        help="Embedding model name")
    parser.add_argument("--embedding-dimension", type=int, default=globalVar.EMBEDDINGS_DIMENSION,
                        help="Embedding dimension")
    parser.add_argument("--batch-size", type=int, default=globalVar.EMBEDDINGS_BATCH_SIZE,
                        help="Batch size for embeddings")
    parser.add_argument("--chunk-size-chars", type=int, default=1800, help="Max chars per chunk")
    parser.add_argument("--chunk-overlap-chars", type=int, default=250, help="Overlap between chunks")
    parser.add_argument("--min-chunk-chars", type=int, default=200, help="Min chars per chunk")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--apply", action="store_true", help="Actually index to Milvus")
    parser.add_argument("--output-json", help="Path to write JSON report")
    parser.add_argument("--output-md", help="Path to write Markdown report")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args(argv)


async def _run(args: argparse.Namespace) -> int:
    from core.config import get_settings
    from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
    from infrastructure.postgres.transaction import fetch_one

    settings = get_settings()
    if not settings.postgres_enabled:
        print("ERROR: PostgreSQL not enabled via globalVar.py", file=sys.stderr)
        return 1

    pool = create_pool_from_settings()
    await open_pool(pool)

    is_test_collection = args.collection.strip().lower().endswith("_test")
    is_test_milvus = "_test_" in args.milvus_collection

    # ── Safety guards ────────────────────────────────────────────────
    if is_test_collection and not is_test_milvus:
        print(f"ERROR: Collection '{args.collection}' is test but Milvus "
              f"collection '{args.milvus_collection}' is not test. "
              f"Would contaminate production index.", file=sys.stderr)
        return 1

    if not is_test_collection and is_test_milvus:
        print(f"ERROR: Collection '{args.collection}' is production but Milvus "
              f"collection '{args.milvus_collection}' is test. "
              f"Would lose test isolation.", file=sys.stderr)
        return 1

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
            await cur.execute(
                "SELECT id, code FROM library_collections WHERE code = %(code)s",
                {"code": args.collection},
            )
            col = await cur.fetchone()
            if not col:
                print(f"ERROR: Collection '{args.collection}' not found", file=sys.stderr)
                return 1

            coll_id = col["id"]
            print(f"Collection: {col['code']} ({coll_id})")
            print(f"Milvus:     {args.milvus_collection}")
            print(f"Model:      {args.embedding_model} (dim={args.embedding_dimension})")
            print(f"Batch:      {args.batch_size}")
            print(f"Mode:       {'DRY-RUN' if args.dry_run else 'APPLY' if args.apply else 'FULL'}")

            # If test collection, use index_existing_chunks (skip chunking)
            if is_test_collection:
                from modules.library.indexing_service import index_existing_chunks

                # Validate dimension
                if args.embedding_dimension != 1536:
                    print(f"ERROR: Expected embedding dimension 1536, got {args.embedding_dimension}",
                          file=sys.stderr)
                    return 1

                # Count chunks in collection
                await cur.execute(
                    "SELECT COUNT(*) AS cnt FROM library_document_chunks WHERE collection_id = %(id)s"
                    " AND document_id IN (SELECT id FROM library_documents WHERE status = 'test_candidate')",
                    {"id": str(coll_id)},
                )
                total = (await cur.fetchone())["cnt"]
                print(f"Chunks in collection: {total}")
                if total == 0:
                    print("ERROR: No chunks found in test collection", file=sys.stderr)
                    return 1

                result = await index_existing_chunks(
                    conn, coll_id, col["code"],
                    milvus_collection_name=args.milvus_collection,
                    document_title=args.document_title,
                    embedding_model=args.embedding_model,
                    embedding_dimension=args.embedding_dimension,
                    batch_size=args.batch_size,
                    dry_run=args.dry_run or not args.apply,
                )
            else:
                # Production path (original flow)
                if args.dry_run:
                    print("Dry-run: would index production collection")
                    print(f"  Production Milvus: {args.milvus_collection}")
                    print(f"  Would not be modified in dry-run mode")
                    return 0

                from modules.library.indexing_service import index_collection
                result = await index_collection(
                    conn, coll_id, col["code"],
                    milvus_collection_name=args.milvus_collection,
                    chunk_size=args.chunk_size_chars,
                    chunk_overlap=args.chunk_overlap_chars,
                    min_chunk=args.min_chunk_chars,
                    embedding_model=args.embedding_model,
                    embedding_dimension=args.embedding_dimension,
                    batch_size=args.batch_size,
                )

        # Output
        if args.output_json:
            with open(args.output_json, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False, default=str)
            print(f"JSON: {args.output_json}")

        if args.output_md:
            with open(args.output_md, "w", encoding="utf-8") as f:
                f.write(f"# Milvus indexing report\n\n"
                        f"Collection: {col['code']} → {args.milvus_collection}\n"
                        f"Status: {result.get('status', 'unknown')}\n"
                        f"Embedded: {result.get('chunks_embedded', 0)}\n"
                        f"Indexed: {result.get('chunks_indexed', 0)}\n")
            print(f"MD: {args.output_md}")

        print()
        print("── Indexing complete ──")
        for k, v in result.items():
            if k != "samples":
                print(f"  {k}: {v}")

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
