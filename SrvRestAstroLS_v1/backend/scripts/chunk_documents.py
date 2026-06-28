#! /usr/bin/env python3
"""
CLI: Chunk documents in the library.

Usage:
    uv run python -m scripts.chunk_documents --collection breslov --chunk-size-chars 1800 --chunk-overlap-chars 250

Requirements:
    - PostgreSQL must be running and accessible
    - Database must be 'tebaai' with migrations 003 and 004 applied
"""

from __future__ import annotations

import argparse
import asyncio
import sys


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Chunk documents in a library collection.")
    parser.add_argument("--collection", required=True, help="Collection code to chunk")
    parser.add_argument("--chunk-size-chars", type=int, default=1800, help="Max chars per chunk")
    parser.add_argument("--chunk-overlap-chars", type=int, default=250, help="Overlap between chunks")
    parser.add_argument("--min-chunk-chars", type=int, default=200, help="Min chars per chunk")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be chunked without inserting")
    return parser.parse_args(argv)


async def _run(args: argparse.Namespace) -> int:
    from core.config import get_settings
    from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
    from infrastructure.postgres.transaction import fetch_one as fo
    from modules.library.chunking import chunk_text
    from modules.library.vector_repository import create_chunks, get_chunks_by_document, count_chunks

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

            coll_id = col["id"]
            print(f"Collection: {col['code']} ({coll_id})")

            # Get documents without chunks
            await cur.execute("""
                SELECT d.id AS doc_id, t.id AS text_id, d.title, d.language, d.collection_id, t.content
                FROM library_documents d
                JOIN library_document_texts t ON t.document_id = d.id
                WHERE d.collection_id = %(coll_id)s
                  AND d.status = 'ready'
                  AND NOT EXISTS (
                      SELECT 1 FROM library_document_chunks ch WHERE ch.document_id = d.id
                  )
            """, {"coll_id": str(coll_id)})
            docs = await cur.fetchall()

            if not docs:
                print("No unchunked documents found.")
                existing = await count_chunks(conn, collection_id=coll_id)
                print(f"Existing chunks in collection: {existing}")
                return 0

            print(f"Documents to chunk: {len(docs)}")

            if args.dry_run:
                total_chunks = 0
                for doc in docs:
                    result = chunk_text(
                        doc["content"], doc["doc_id"], doc["text_id"],
                        language=doc["language"],
                        chunk_size=args.chunk_size_chars,
                        overlap=args.chunk_overlap_chars,
                        min_chunk=args.min_chunk_chars,
                    )
                    total_chunks += len(result)
                    print(f"  {doc['title']}: {len(result)} chunks")
                print(f"\nDry-run total: {total_chunks} chunks would be created")
                return 0

            async with pool.connection() as write_conn:
                from psycopg.rows import dict_row
                write_conn.row_factory = dict_row
                total = 0
                for doc in docs:
                    result = chunk_text(
                        doc["content"], doc["doc_id"], doc["text_id"],
                        language=doc["language"],
                        chunk_size=args.chunk_size_chars,
                        overlap=args.chunk_overlap_chars,
                        min_chunk=args.min_chunk_chars,
                    )
                    for c in result:
                        c["collection_id"] = doc["collection_id"]
                        c["page_start"] = None
                        c["page_end"] = None
                        c["chapter"] = None
                        c["section"] = None
                        c["metadata"] = {}
                        import datetime
                        c["created_at"] = datetime.datetime.utcnow()
                        c["updated_at"] = datetime.datetime.utcnow()

                    if result:
                        inserted = await create_chunks(write_conn, result)
                        total += inserted
                    print(f"  {doc['title']}: {len(result)} chunks")

                final = await count_chunks(write_conn, collection_id=coll_id)
                print(f"\nChunks created: {total}")
                print(f"Total chunks in collection: {final}")
            return 0

    finally:
        await close_pool(pool)


def main() -> int:
    args = _parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
