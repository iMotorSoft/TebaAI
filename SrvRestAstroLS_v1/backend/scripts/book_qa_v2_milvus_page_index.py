#!/usr/bin/env python3
"""Index KITZUR V2 pages into a Milvus test collection, one vector per page."""

from __future__ import annotations

import argparse, asyncio, hashlib, json, os, re, sys, time
from pathlib import Path
from typing import Any

import psycopg
from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections, utility

PG_CONF = {
    "user": os.environ["DB_PG_USER"], "password": os.environ["DB_PG_PASS"],
    "host": os.environ.get("DB_PG_IP", "localhost"),
    "port": int(os.environ.get("DB_PG_PORT", "5432")), "dbname": "tebaai",
}
EMBEDDING_VERSION = "openai_text_embedding_3_small"
EMBEDDING_DIM = 1536
MAX_EMBED_TEXT = 3000
PROHIBITED_COLLECTIONS = {"tebaai_breslov_chunks_v1", "tebaai_breslov_test_chunks_v1"}

SCHEMA = CollectionSchema([
    FieldSchema("pk", DataType.VARCHAR, is_primary=True, max_length=128),
    FieldSchema("run_id", DataType.VARCHAR, max_length=64),
    FieldSchema("document_id", DataType.VARCHAR, max_length=64),
    FieldSchema("scope_code", DataType.VARCHAR, max_length=64),
    FieldSchema("page_number", DataType.INT64),
    FieldSchema("content_sha256", DataType.VARCHAR, max_length=64),
    FieldSchema("char_count", DataType.INT64),
    FieldSchema("text_preview", DataType.VARCHAR, max_length=1024),
    FieldSchema("embedding_version", DataType.VARCHAR, max_length=64),
    FieldSchema("embedding", DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM),
], description="KITZUR V2 pages for Book QA hybrid test")


async def embed_text(text: str) -> list[float]:
    import httpx
    from globalVar import LITELLM_BASE_URL, LITELLM_API_KEY
    r = await httpx.AsyncClient(timeout=60).post(
        f"{LITELLM_BASE_URL}/v1/embeddings",
        headers={"Authorization": f"Bearer {LITELLM_API_KEY}", "Content-Type": "application/json"},
        json={"input": text[:MAX_EMBED_TEXT], "model": EMBEDDING_VERSION},
    )
    r.raise_for_status()
    return r.json()["data"][0]["embedding"]


async def main() -> int:
    parser = argparse.ArgumentParser(description="KITZUR V2 Milvus page index")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--collection", default="tebaai_breslov_bookqa_v2_kitzur_test_pages_v1")
    parser.add_argument("--scope-code", default="breslov_test")
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--limit", type=int, help="Pages to index (omit for all)")
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--report-dir", type=Path, default=Path("data/reports/breslov/2026-07-09-book-qa-v2-hybrid-kitzur"))
    args = parser.parse_args()

    is_dry = not args.execute
    mode = "DRY-RUN" if is_dry else "EXECUTE"
    collection_name = args.collection
    report_dir = args.report_dir
    report_dir.mkdir(parents=True, exist_ok=True)

    if collection_name in PROHIBITED_COLLECTIONS:
        print(f"ERROR: Collection '{collection_name}' is a production collection. Aborting.")
        return 1

    print(f"\n{'='*70}")
    print(f"  KITZUR V2 MILVUS PAGE INDEX ({mode})")
    print(f"{'='*70}")
    print(f"  Collection: {collection_name}")
    print(f"  Run ID: {args.run_id}")
    print(f"  Limit: {args.limit or 'all'}")
    print(f"  Batch: {args.batch_size}")

    # ── Load pages ──
    conn = await psycopg.AsyncConnection.connect(**PG_CONF)
    pages = []
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT run_id, document_id, page_number, text, char_count "
            "FROM library_pages_v2 WHERE run_id = %s AND char_count > 0 ORDER BY page_number",
            (args.run_id,),
        )
        async for r in cur:
            pages.append({"run_id": str(r[0]), "document_id": str(r[1]), "page_number": r[2], "text": r[3], "char_count": r[4]})
    await conn.close()

    if args.limit:
        pages = pages[:args.limit]

    print(f"\n  Pages loaded: {len(pages)}")
    if not pages:
        print("  ERROR: No pages found. Aborting."); return 1

    doc_id = pages[0]["document_id"][:12]

    # ── Dry-run report ──
    if is_dry:
        print(f"\n  Document ID: {doc_id}...")
        print(f"  Embedding model: {EMBEDDING_VERSION} (dim={EMBEDDING_DIM})")
        print(f"  Schema fields: {len(SCHEMA.fields)}")
        print(f"\n  {'─'*50}")
        print(f"  DRY-RUN: No collection created or data inserted.")
        print(f"  To execute, re-run with --execute")
        return 0

    # ── Connect Milvus ──
    print(f"\n  Connecting to Milvus...")
    connections.connect(alias="default", host="127.0.0.1", port=19530, timeout=30)

    # Drop if exists (test collection, safe)
    if utility.has_collection(collection_name):
        utility.drop_collection(collection_name)
        print(f"  Dropped existing collection: {collection_name}")

    col = Collection(name=collection_name, schema=SCHEMA)
    print(f"  Created collection: {collection_name}")

    # ── Batch insert ──
    total = len(pages)
    batches = (total + args.batch_size - 1) // args.batch_size
    inserted = 0
    failed = 0
    errors: list[str] = []
    start = time.time()

    print(f"\n  Embedding {total} pages in {batches} batches...")

    for b in range(batches):
        batch = pages[b * args.batch_size: (b + 1) * args.batch_size]
        entities = []
        for p in batch:
            embed_text_content = f"KITZUR CreateSpace\nPage {p['page_number']}\n\n{p['text']}"
            sha256 = hashlib.sha256(p["text"].encode()).hexdigest()
            preview = p["text"][:500].replace("\n", " ").strip()
            pk = f"kitzur_v2_{args.run_id[:8]}_{p['page_number']}"

            try:
                vec = await embed_text(embed_text_content)
            except Exception as exc:
                errors.append(f"Page {p['page_number']}: embed failed: {exc}")
                failed += 1
                continue

            entities.append({
                "pk": pk, "run_id": args.run_id, "document_id": p["document_id"],
                "scope_code": args.scope_code, "page_number": p["page_number"],
                "content_sha256": sha256, "char_count": p["char_count"],
                "text_preview": preview, "embedding_version": EMBEDDING_VERSION,
                "embedding": vec,
            })
            inserted += 1

        if entities:
            col.insert(entities)
            print(f"  Batch {b+1}/{batches}: {len(entities)} entities ({inserted}/{total})")

    col.flush()
    col.create_index("embedding", {"index_type": "HNSW", "metric_type": "COSINE", "params": {"M": 16, "efConstruction": 200}})
    col.load()
    elapsed = round(time.time() - start, 1)

    print(f"\n  {'─'*50}")
    print(f"  Inserted: {inserted}")
    print(f"  Failed: {failed}")
    print(f"  Time: {elapsed}s")
    if failed:
        print(f"  Errors: {errors[:5]}")

    # ── Validate ──
    col = Collection(collection_name)
    col.load()
    count = col.num_entities
    print(f"  Collection count: {count}")
    connections.disconnect("default")

    # ── Report ──
    summary = {
        "collection": collection_name, "run_id": args.run_id,
        "document_id": doc_id, "scope_code": args.scope_code,
        "embedding_model": EMBEDDING_VERSION, "embedding_dim": EMBEDDING_DIM,
        "pages_loaded": total, "pages_inserted": inserted, "pages_failed": failed,
        "batches": batches, "batch_size": args.batch_size,
        "elapsed_seconds": elapsed, "collection_count": count,
        "errors": errors[:10],
    }
    (report_dir / "milvus_index_summary.json").write_text(json.dumps(summary, indent=2))
    print(f"  Report: {report_dir / 'milvus_index_summary.json'}")
    print(f"{'='*70}\n")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
