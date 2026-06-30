#! /usr/bin/env python3
"""
CLI: Validate hybrid search integrity for breslov_test.

Tests FTS, vector, hybrid, round-trip PG↔Milvus, negative query,
and product isolation. Read-only.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Validate Breslov test hybrid integrity.")
    p.add_argument("--collection", default="breslov_test")
    p.add_argument("--milvus-collection", default="tebaai_breslov_test_chunks_v1")
    p.add_argument("--product-milvus-collection", default="tebaai_breslov_chunks_v1")
    p.add_argument("--embedding-model-alias", default="openai_text_embedding_3_small")
    p.add_argument("--expected-dim", type=int, default=1536)
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--output-json")
    p.add_argument("--output-md")
    return p.parse_args(argv)


async def _run(args: argparse.Namespace) -> int:
    from core.config import get_settings
    from globalVar import POSTGRES_DSN, LITELLM_API_KEY, EMBEDDINGS_DIMENSION
    import psycopg
    from modules.embeddings.client import embed_text
    from modules.library.text_search import search_chunks_text
    from modules.library.hybrid_search import search_chunks_hybrid
    from infrastructure.milvus.client import create_connection, close_connection, search_vectors, ensure_collection, list_collections

    settings = get_settings()
    if not settings.postgres_enabled:
        print("ERROR: PostgreSQL not enabled", file=sys.stderr)
        return 1

    conn = await psycopg.AsyncConnection.connect(POSTGRES_DSN)
    results: dict = {
        "collection": args.collection,
        "milvus_collection": args.milvus_collection,
        "product_milvus_collection": args.product_milvus_collection,
        "embedding_model": args.embedding_model_alias,
        "embedding_dim": args.expected_dim,
        "fts": {},
        "vector": {},
        "hybrid": {},
        "round_trip": {},
        "negative_query": {},
        "product_isolation": {},
    }

    try:
        # ── FTS smoke ──────────────────────────────────────────
        fts_queries = [
            "La maravilla del cerebro",
            "Kokhavey Ohr",
            "Kitzur Likutey",
        ]
        fts_pass = True
        for q in fts_queries:
            r = await search_chunks_text(conn, collection_code=args.collection, query=q, top_k=args.top_k)
            found = len(r) > 0
            top_doc = r[0]["document_title"] if r else None
            results["fts"][q] = {"found": found, "top_result": top_doc, "count": len(r)}
            if not found:
                fts_pass = False
        results["fts_pass"] = fts_pass

        # ── Vector smoke ────────────────────────────────────────
        vector_queries = [
            "Rebbe Nachman",
            "Stars of Light",
            "Lección",
        ]
        vector_pass = True
        create_connection()
        ensure_collection(args.milvus_collection, dimension=args.expected_dim)

        for q in vector_queries:
            vec = embed_text(q)
            hits = search_vectors(
                args.milvus_collection, vec, top_k=args.top_k,
                expr=f'collection_code == "{args.collection}"',
                output_fields=["chunk_id", "title", "chunk_index", "page_start", "page_end", "content_preview"],
            )
            found = len(hits) > 0
            top_hit = hits[0] if hits else None
            results["vector"][q] = {"found": found, "count": len(hits), "top_score": round(top_hit["distance"], 4) if top_hit else None}
            if not found:
                vector_pass = False
        results["vector_pass"] = vector_pass

        # ── Round-trip PG↔Milvus ──────────────────────────────
        round_trip_pass = True
        round_trip_results = []
        for q in ["Kokhavey Ohr", "Kitzur"]:
            vec = embed_text(q)
            hits = search_vectors(
                args.milvus_collection, vec, top_k=3,
                expr=f'collection_code == "{args.collection}"',
                output_fields=["chunk_id", "document_id", "title", "chunk_index", "page_start", "page_end", "content_preview"],
            )
            for hit in hits:
                cid = hit.get("chunk_id", "")
                if not cid:
                    continue
                from psycopg.rows import dict_row
                cur = conn.cursor(row_factory=dict_row)
                await cur.execute(
                    "SELECT ch.id, ch.document_id, d.title, ch.page_start, ch.page_end, ch.reference_label, "
                    "c.code FROM library_document_chunks ch "
                    "JOIN library_documents d ON d.id = ch.document_id "
                    "JOIN library_collections c ON c.id = d.collection_id "
                    "WHERE ch.id = %s", (cid,))
                pg_row = await cur.fetchone()
                await cur.close()
                pg_exists = pg_row is not None
                coll_match = pg_row and pg_row["code"] == args.collection if pg_row else False
                doc_match = pg_row and str(pg_row["document_id"]) == hit.get("document_id", "") if pg_row else False
                item = {"chunk_id": cid, "pg_exists": pg_exists, "collection_match": coll_match, "document_match": doc_match}
                round_trip_results.append(item)
                if not pg_exists or not coll_match or not doc_match:
                    round_trip_pass = False
        results["round_trip"] = {"pass": round_trip_pass, "checks": round_trip_results}
        results["round_trip_pass"] = round_trip_pass

        # ── Hybrid smoke ────────────────────────────────────────
        hybrid_queries = ["La maravilla del cerebro", "Kokhavey Ohr"]
        hybrid_pass = True
        for q in hybrid_queries:
            r = await search_chunks_hybrid(conn, collection_code=args.collection, query=q,
                                           top_k=30, milvus_collection=args.milvus_collection)
            found = len(r) > 0
            has_vector = any(s.get("source_signals") and "vector" in s["source_signals"] for s in r)
            results["hybrid"][q] = {"found": found, "top_k_checked": 30, "count": len(r), "has_vector_branch": has_vector}
            if not found or not has_vector:
                hybrid_pass = False
        results["hybrid_pass"] = hybrid_pass

        # ── Negative query ──────────────────────────────────────
        neg_q = "receta de pollo al horno con papas"
        vec = embed_text(neg_q)
        neg_hits = search_vectors(
            args.milvus_collection, vec, top_k=args.top_k,
            expr=f'collection_code == "{args.collection}"',
            output_fields=["chunk_id", "title", "chunk_index"],
        )
        max_score = round(neg_hits[0]["distance"], 4) if neg_hits else 0.0
        results["negative_query"] = {"query": neg_q, "found": len(neg_hits) > 0, "max_score": max_score,
                                     "count": len(neg_hits)}
        results["negative_query_pass"] = max_score < 0.30

        # ── Product isolation ────────────────────────────────────
        cols = list_collections()
        prod_exists = args.product_milvus_collection in cols
        test_exists = args.milvus_collection in cols
        isolation_pass = prod_exists and test_exists
        results["product_isolation"] = {
            "test_collection_exists": test_exists,
            "product_collection_exists": prod_exists,
            "pass": isolation_pass,
        }
        results["product_isolation_pass"] = isolation_pass

        # Overall
        results["overall_pass"] = all([
            results["fts_pass"], results["vector_pass"],
            results["hybrid_pass"], results["round_trip_pass"],
            results["product_isolation_pass"],
            results["negative_query_pass"],
        ])

    finally:
        await conn.close()
        close_connection()

    print(f"\n── Breslov Test Hybrid Integrity ──")
    for k in ["fts_pass", "vector_pass", "hybrid_pass", "round_trip_pass", "negative_query_pass", "product_isolation_pass"]:
        print(f"  {k}: {results[k]}")
    print(f"  overall_pass: {results['overall_pass']}")

    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)
        print(f"JSON: {args.output_json}")

    return 0 if results["overall_pass"] else 1


def main() -> int:
    args = _parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
