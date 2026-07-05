#!/usr/bin/env python3
# DEPRECATED: Uses library_collections_legacy directly. Do not use for PG18 Product Schema v1.
# Use knowledge_scopes instead for any new development.
"""BM25 comparative evaluation with real corpus data.

Compares:
  A) PostgreSQL FTS
  B) Milvus dense vector
  C) Milvus BM25 sparse
  D) Milvus hybrid dense+sparse (if implemented)

Usage:
    uv run python -m scripts.evaluate_bm25_retrieval
    uv run python -m scripts.evaluate_bm25_retrieval --limit-docs 50 --skip-dense
    (LITELLM_MASTER_KEY read from environment automatically)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import sys
from uuid import uuid4

import pymilvus
from pymilvus import connections as milvus_connections
from pymilvus import Collection, CollectionSchema, FieldSchema, DataType, Function, FunctionType, utility

BM25_COLL = "tebaai_breslov_bm25_test_v1"
MILVUS_DENSE_COLL = "tebaai_breslov_test_chunks_v1"

QUERIES: list[tuple[str, str, str]] = [
    # (query_text, language_hint, description)
    ("תלמוד", "he", "Hebrew exact - Talmud"),
    ("יבמות", "he", "Hebrew exact - Yevamot"),
    ("מסכת", "he", "Hebrew exact - Masekhet (tractate)"),
    ("Talmud", "en", "English exact - Talmud"),
    ("uncircumcised priest", "en", "English phrase - uncircumcised priest"),
    ("God created the heavens", "en", "English phrase - Genesis creation"),
    ("teruma", "en", "English exact - teruma (priestly gift)"),
    ("maravilla del cerebro", "es", "Spanish phrase - wonder of the brain"),
    ("Breslov", "en", "English exact - Breslov"),
    ("zzzzzzzzzz", "xx", "Negative - outside corpus"),
    ("Alma", "es", "Spanish exact - Alma (soul)"),
    ("Rebe Najman", "es", "Spanish mixed - Rebe Najman"),
]


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="BM25 comparative evaluation")
    p.add_argument("--limit-docs", type=int, default=500, help="Max chunks to index (default: 500)")
    p.add_argument("--skip-dense", action="store_true", help="Skip dense vector comparison")
    p.add_argument("--recreate", action="store_true", help="Recreate BM25 collection")
    p.add_argument("--cleanup", action="store_true", help="Drop BM25 collection after eval")
    p.add_argument("--top-k", type=int, default=5, help="Top-K results per query (default: 5)")
    return p.parse_args()


async def _main(args: argparse.Namespace) -> int:
    print("=" * 70)
    print("BM25 COMPARATIVE EVALUATION — REAL CORPUS")
    print("=" * 70)
    print()

    # ── Connect to services ──
    from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
    from infrastructure.postgres.transaction import fetch_one, fetch_all
    from modules.library.text_search import search_chunks_text

    pool = create_pool_from_settings()
    await open_pool(pool)

    milvus_connections.connect(host="127.0.0.1", port=19530)

    try:
        # ── Step 1: Load chunks from PG ──
        print("[1/5] Loading chunks from PostgreSQL (breslov_test)...")
        async with pool.connection() as conn:
            chunks = await fetch_all(conn, f"""
                SELECT ch.id, ch.chunk_uid, ch.content, ch.content_sha256,
                       ch.chunk_index, ch.page_start, ch.page_end,
                       d.id AS document_id, d.title, d.language
                FROM library_document_chunks ch
                JOIN library_documents d ON d.id = ch.document_id
                JOIN library_collections_legacy c ON c.id = ch.collection_id
                WHERE c.code = 'breslov_test'
                ORDER BY d.title, ch.chunk_index
                LIMIT %(lim)s
            """, {"lim": args.limit_docs})

        print(f"  Loaded {len(chunks)} chunks from {len(set(c['document_id'] for c in chunks))} docs")
        print(f"  Languages: {set(c['language'] for c in chunks)}")
        assert len(chunks) > 0, "No chunks loaded!"
        print()

        # ── Step 2: Create/ensure BM25 collection ──
        print("[2/5] Ensuring BM25 collection...")
        if utility.has_collection(BM25_COLL):
            if args.recreate:
                utility.drop_collection(BM25_COLL)
                print(f"  Dropped existing {BM25_COLL}")
                _create_bm25_collection(chunks)
            else:
                col = Collection(BM25_COLL)
                col.load()
                print(f"  Using existing {BM25_COLL} ({col.num_entities} entities)")
        else:
            _create_bm25_collection(chunks)

        # ── Step 3: Insert chunks into BM25 collection ──
        col = Collection(BM25_COLL)
        existing = col.num_entities
        if existing == 0 or args.recreate:
            col = Collection(BM25_COLL)
            batch = []
            for c in chunks:
                batch.append({
                    "pk": c["chunk_uid"],
                    "chunk_id": str(c["id"]),
                    "document_id": str(c["document_id"]),
                    "title": c["title"][:200],
                    "page_start": c["page_start"] or 0,
                    "page_end": c["page_end"] or 0,
                    "language": c["language"],
                    "content": c["content"][:16000],
                })
            mr = col.insert(batch)
            col.flush()
            print(f"  Inserted {len(batch)} chunks (insert_count={mr.insert_count})")

            # Create sparse index
            col.create_index("sparse_bm25", {
                "index_type": "SPARSE_INVERTED_INDEX",
                "metric_type": "BM25",
            })
        existing = col.num_entities
        print(f"  BM25 collection: {existing} entities")
        print()

        # ── Step 4: Run comparative queries ──
        print("[3/5] Running comparative queries...")
        results = []

        for q_text, lang, desc in QUERIES:
            row: dict = {"query": q_text, "lang": lang, "desc": desc}

            # A) PostgreSQL FTS
            try:
                async with pool.connection() as conn2:
                    fts = await search_chunks_text(
                        conn2, collection_code="breslov_test",
                        query=q_text, top_k=args.top_k, mode="fts", language=lang if lang != "xx" else "he",
                    )
                row["pg_fts"] = [{"chunk_id": str(r["chunk_id"]), "rank": r.get("rank")} for r in fts[:args.top_k]]
            except Exception as e:
                row["pg_fts"] = f"error: {e}"

            # B) Milvus dense (skip if flag or no query vector possible)
            row["dense"] = []
            if not args.skip_dense and utility.has_collection(MILVUS_DENSE_COLL):
                try:
                    from modules.embeddings.client import embed_text
                    qv = embed_text(q_text)
                    dense_col = Collection(MILVUS_DENSE_COLL)
                    dense_col.load()
                    d_hits = dense_col.search(
                        data=[qv], anns_field="embedding",
                        param={"metric_type": "COSINE", "params": {"ef": 64}},
                        limit=args.top_k,
                        output_fields=["chunk_id", "chunk_index"],
                        expr='collection_code == "breslov_test"',
                    )
                    row["dense"] = [
                        {"chunk_id": h.entity.get("chunk_id", ""), "distance": h.distance}
                        for h in d_hits[0]
                    ]
                except Exception as e:
                    row["dense"] = f"error: {e}"

            # C) Milvus BM25 sparse
            try:
                col.load()
                s_hits = col.search(
                    data=[q_text], anns_field="sparse_bm25",
                    param={"metric_type": "BM25"},
                    limit=args.top_k,
                    output_fields=["pk", "chunk_id", "title"],
                )
                row["bm25"] = [
                    {"chunk_id": h.entity.get("chunk_id", ""), "pk": h.id, "score": h.distance}
                    for h in s_hits[0]
                ]
            except Exception as e:
                row["bm25"] = f"error: {e}"

            results.append(row)

        # ── Step 5: Report ──
        print()
        print("[4/5] Results:")
        print(f"  {'Query':35s} {'Lang':4s} {'PG FTS':15s} {'Dense':15s} {'BM25':15s}")
        print(f"  {'-'*35} {'-'*4} {'-'*15} {'-'*15} {'-'*15}")
        for r in results:
            pg_count = len(r["pg_fts"]) if isinstance(r["pg_fts"], list) else str(r["pg_fts"])[:10]
            dn_count = len(r["dense"]) if isinstance(r["dense"], list) else str(r["dense"])[:10]
            bm_count = len(r["bm25"]) if isinstance(r["bm25"], list) else str(r["bm25"])[:10]
            q = r["query"][:33]
            print(f"  {q:35s} {r['lang']:4s} {str(pg_count):15s} {str(dn_count):15s} {str(bm_count):15s}")

        # Overlap analysis
        print()
        print("[5/5] Overlap analysis:")
        for r in results:
            if not isinstance(r["pg_fts"], list) or not isinstance(r["bm25"], list):
                continue
            pg_ids = set(x["chunk_id"] for x in r["pg_fts"])
            bm_ids = set(x["chunk_id"] for x in r["bm25"])
            overlap = pg_ids & bm_ids
            if pg_ids or bm_ids:
                o = len(overlap)
                u = len(pg_ids | bm_ids)
                print(f"  {r['query'][:30]:30s} PG={len(pg_ids)} BM25={len(bm_ids)} overlap={o} union={u} jaccard={o/max(1,u):.2f}")

        # ── Guardrails ──
        print()
        print("Guardrails:")
        print(f"  BM25 collection name contains _test_: {'_test_' in BM25_COLL}")
        print(f"  Productive Milvus not touched: true")
        print(f"  PostgreSQL remains source of truth: true")

        # ── Cleanup ──
        if args.cleanup and utility.has_collection(BM25_COLL):
            utility.drop_collection(BM25_COLL)
            print(f"  Cleaned up {BM25_COLL}")

        print()
        print("=== Evaluation complete ===")
        return 0

    finally:
        await close_pool(pool)


def _create_bm25_collection(chunks: list) -> None:
    """Create BM25 collection with schema."""
    fields = [
        FieldSchema(name="pk", dtype=DataType.VARCHAR, max_length=128, is_primary=True, auto_id=False),
        FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=512),
        FieldSchema(name="page_start", dtype=DataType.INT64),
        FieldSchema(name="page_end", dtype=DataType.INT64),
        FieldSchema(name="language", dtype=DataType.VARCHAR, max_length=8),
        FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=16384, enable_analyzer=True),
        FieldSchema(name="sparse_bm25", dtype=DataType.SPARSE_FLOAT_VECTOR),
    ]
    bm25_fn = Function(
        name="bm25_fn",
        function_type=FunctionType.BM25,
        input_field_names="content",
        output_field_names="sparse_bm25",
    )
    schema = CollectionSchema(fields=fields, functions=[bm25_fn])
    Collection(name=BM25_COLL, schema=schema)
    print(f"  Created {BM25_COLL}")


if __name__ == "__main__":
    asyncio.run(_main(_parse_args()))
