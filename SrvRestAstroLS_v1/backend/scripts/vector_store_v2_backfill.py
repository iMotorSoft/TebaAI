#!/usr/bin/env python3
"""Development-only idempotent V2 page-vector backfill for pgvector and Milvus.

Supports:
  --backend pgvector|milvus|both
  --scope breslov_primary
  --collection-code breslov_primary
  --run-id <uuid>
  --drop-derived
  --dry-run
  --force
  --batch-size 64
  --json-out <path>
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import httpx
import psycopg
from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections, utility

from globalVar import LITELLM_API_KEY, LITELLM_BASE_URL, MILVUS_HOST, MILVUS_PORT, RESEARCH_EMBEDDING_MODEL_ALIAS

TABLE = "library_vector_embeddings_v2_dev"
COLLECTION = "tebaai_breslov_chunks_v2_dev"

PG = {"user": os.environ["DB_PG_USER"], "password": os.environ["DB_PG_PASS"],
      "host": os.environ.get("DB_PG_IP", "localhost"),
      "port": int(os.environ.get("DB_PG_PORT", "5432")), "dbname": "tebaai"}

FIELDS = [
    FieldSchema("pk", DataType.VARCHAR, is_primary=True, max_length=64),
    FieldSchema("chunk_id", DataType.VARCHAR, max_length=64),
    FieldSchema("document_id", DataType.VARCHAR, max_length=64),
    FieldSchema("knowledge_scope_code", DataType.VARCHAR, max_length=64),
    FieldSchema("collection_code", DataType.VARCHAR, max_length=64),
    FieldSchema("run_id", DataType.VARCHAR, max_length=64),
    FieldSchema("language", DataType.VARCHAR, max_length=8),
    FieldSchema("page", DataType.INT64),
    FieldSchema("embedding_model", DataType.VARCHAR, max_length=128),
    FieldSchema("embedding_version", DataType.VARCHAR, max_length=32),
    FieldSchema("text_hash", DataType.VARCHAR, max_length=64),
    FieldSchema("text_preview", DataType.VARCHAR, max_length=1024),
    FieldSchema("embedding", DataType.FLOAT_VECTOR, dim=1536),
]


def preview(text: str) -> str:
    return text.encode("utf-8")[:1024].decode("utf-8", "ignore")


async def embed_batch(texts: list[str]) -> list[list[float]]:
    truncated = [t[:6000] for t in texts]
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            f"{LITELLM_BASE_URL}/v1/embeddings",
            headers={"Authorization": f"Bearer {LITELLM_API_KEY}"},
            json={"model": RESEARCH_EMBEDDING_MODEL_ALIAS, "input": truncated},
        )
        r.raise_for_status()
        return [x["embedding"] for x in r.json()["data"]]


def drop_pg(conn: psycopg.Connection, force: bool = False) -> None:
    if not force:
        print("WARN: --force required to drop pgvector table")
        return
    with conn.cursor() as c:
        c.execute(f"DROP TABLE IF EXISTS {TABLE} CASCADE")
    conn.commit()
    print(f"  [OK] Table {TABLE} dropped")


def drop_milvus(force: bool = False) -> None:
    if not force:
        print("WARN: --force required to drop Milvus collection")
        return
    connections.connect(alias="default", host=MILVUS_HOST, port=MILVUS_PORT, timeout=10)
    if COLLECTION in utility.list_collections():
        utility.drop_collection(COLLECTION)
        print(f"  [OK] Collection {COLLECTION} dropped")
    connections.disconnect("default")


def ensure_pg_table(conn: psycopg.Connection, drop: bool = False, force: bool = False) -> None:
    if drop:
        drop_pg(conn, force)
    with conn.cursor() as c:
        c.execute("CREATE EXTENSION IF NOT EXISTS vector")
        c.execute(f"""
            CREATE TABLE IF NOT EXISTS {TABLE} (
                chunk_id text PRIMARY KEY,
                document_id uuid NOT NULL,
                knowledge_scope_code text NOT NULL,
                collection_code text NOT NULL,
                run_id uuid NOT NULL,
                language text NOT NULL,
                page integer NOT NULL,
                embedding_model text NOT NULL,
                embedding_version text NOT NULL,
                text_hash text NOT NULL,
                text_preview text NOT NULL,
                embedding vector(1536) NOT NULL,
                created_at timestamptz default now(),
                updated_at timestamptz default now()
            )
        """)
        c.execute(f"CREATE INDEX IF NOT EXISTS {TABLE}_scope_idx ON {TABLE}(knowledge_scope_code, run_id, document_id, language)")
        c.execute(f"CREATE INDEX IF NOT EXISTS {TABLE}_hnsw_idx ON {TABLE} USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 200)")
    conn.commit()
    print(f"  [OK] pgvector table {TABLE} ready")


def ensure_milvus_collection(drop: bool = False, force: bool = False) -> None:
    if drop:
        drop_milvus(force)
    connections.connect(alias="default", host=MILVUS_HOST, port=MILVUS_PORT, timeout=10)
    if COLLECTION not in utility.list_collections():
        col = Collection(COLLECTION, CollectionSchema(FIELDS, description="Breslov V2 dev chunks"))
        col.create_index("embedding", {"index_type": "HNSW", "metric_type": "COSINE", "params": {"M": 16, "efConstruction": 200}})
        print(f"  [OK] Milvus collection {COLLECTION} created with HNSW/COSINE")
    else:
        print(f"  [OK] Milvus collection {COLLECTION} already exists")
    connections.disconnect("default")


async def backfill(args: argparse.Namespace) -> dict[str, Any]:
    report: dict[str, Any] = {
        "status": "BACKFILL_STARTED",
        "backend": args.backend,
        "scope": args.scope,
        "collection_code": args.collection_code,
        "run_id": args.run_id,
        "batch_size": args.batch_size,
        "table": TABLE,
        "collection": COLLECTION,
    }

    # Connect to PostgreSQL
    conn = psycopg.connect(**PG)

    # Fetch run info
    try:
        with conn.cursor() as c:
            c.execute(
                "SELECT document_id::text, scope_code FROM library_ingestion_runs_v2 WHERE run_id = %s",
                (args.run_id,),
            )
            run = c.fetchone()
            if not run:
                return {**report, "status": "ERROR", "error": "run_not_found"}
            doc_id = run[0]
            run_scope = run[1]
    except Exception as e:
        return {**report, "status": "ERROR", "error": f"run_query_failed: {e}"}

    report["document_id"] = doc_id
    report["run_scope"] = run_scope

    # Fetch pages with text
    with conn.cursor() as c:
        c.execute(
            "SELECT page_number, text FROM library_pages_v2 WHERE run_id = %s AND char_count > 0 ORDER BY page_number",
            (args.run_id,),
        )
        pages = c.fetchall()

    report["pages_total"] = len(pages)
    print(f"\n  Source pages with text: {len(pages)}")
    print(f"  Document ID: {doc_id}")
    print(f"  Run scope: {run_scope}")
    print(f"  Target scope: {args.scope}")
    print(f"  Collection code: {args.collection_code}")

    if args.dry_run:
        conn.close()
        return {**report, "status": "BACKFILL_DRY_RUN_OK", "pages": len(pages)}

    # Ensure backends
    do_pg = args.backend in ("pgvector", "both")
    do_milvus = args.backend in ("milvus", "both")

    if do_pg:
        ensure_pg_table(conn, drop=args.drop_derived, force=args.force)

    if do_milvus:
        ensure_milvus_collection(drop=args.drop_derived, force=args.force)

    # Prepare Milvus collection
    milvus_col = None
    if do_milvus:
        connections.connect(alias="default", host=MILVUS_HOST, port=MILVUS_PORT, timeout=10)
        milvus_col = Collection(COLLECTION)
        milvus_col.load()

    # Process in batches
    inserted_pg = 0
    inserted_milvus = 0
    errors: list[str] = []
    total_batches = (len(pages) + args.batch_size - 1) // args.batch_size

    for batch_idx in range(0, len(pages), args.batch_size):
        batch = pages[batch_idx:batch_idx + args.batch_size]
        batch_num = batch_idx // args.batch_size + 1
        print(f"  Batch {batch_num}/{total_batches} ({len(batch)} pages)...", end=" ")

        try:
            texts = [t for _, t in batch]
            vecs = await embed_batch(texts)
        except Exception as e:
            msg = f"batch_{batch_num}_embed_error: {type(e).__name__}: {e}"
            errors.append(msg)
            print(f"ERROR: {e}")
            continue

        pg_rows: list[tuple] = []
        milvus_rows: list[dict[str, Any]] = []

        for (page, text), vec in zip(batch, vecs):
            pk = hashlib.sha256(f"{args.run_id}:{page}".encode()).hexdigest()[:64]
            h = hashlib.sha256(text.encode()).hexdigest()
            text_preview = preview(text)
            vec_str = "[" + ",".join(map(str, vec)) + "]"

            pg_rows.append((pk, doc_id, args.scope, args.collection_code,
                           args.run_id, "es", page,
                           RESEARCH_EMBEDDING_MODEL_ALIAS, "v2", h, text_preview, vec_str))

            milvus_rows.append({
                "pk": pk, "chunk_id": pk, "document_id": doc_id,
                "knowledge_scope_code": args.scope, "collection_code": args.collection_code,
                "run_id": args.run_id, "language": "es", "page": page,
                "embedding_model": RESEARCH_EMBEDDING_MODEL_ALIAS,
                "embedding_version": "v2", "text_hash": h,
                "text_preview": text_preview, "embedding": vec,
            })

        # Insert to pgvector
        if do_pg and pg_rows:
            try:
                with conn.cursor() as c:
                    for row in pg_rows:
                        c.execute(f"""
                            INSERT INTO {TABLE}
                                (chunk_id, document_id, knowledge_scope_code, collection_code,
                                 run_id, language, page, embedding_model, embedding_version,
                                 text_hash, text_preview, embedding, updated_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector, now())
                            ON CONFLICT (chunk_id)
                            DO UPDATE SET
                                embedding = excluded.embedding,
                                text_hash = excluded.text_hash,
                                text_preview = excluded.text_preview,
                                updated_at = now()
                        """, row)
                conn.commit()
                inserted_pg += len(pg_rows)
            except Exception as e:
                conn.rollback()
                errors.append(f"batch_{batch_num}_pg_error: {e}")

        # Insert to Milvus
        if do_milvus and milvus_rows and milvus_col is not None:
            try:
                milvus_col.upsert(milvus_rows)
                inserted_milvus += len(milvus_rows)
            except Exception as e:
                errors.append(f"batch_{batch_num}_milvus_error: {e}")

        print(f"OK ({len(pg_rows)} pg, {len(milvus_rows)} milvus)")

    # Flush Milvus
    if milvus_col is not None:
        milvus_col.flush()
        connections.disconnect("default")

    conn.close()

    report["status"] = "BACKFILL_BOTH_OK" if (do_pg and do_milvus) else \
                       "BACKFILL_PGVECTOR_OK" if do_pg else \
                       "BACKFILL_MILVUS_OK" if do_milvus else "BACKFILL_NOOP"
    report["inserted_pg"] = inserted_pg
    report["inserted_milvus"] = inserted_milvus
    report["expected"] = len(pages)
    report["errors"] = errors
    report["error_count"] = len(errors)

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="V2 vector backfill for pgvector and Milvus")
    parser.add_argument("--run-id", required=True, help="Ingestion V2 run UUID")
    parser.add_argument("--scope", default="breslov_primary", help="Knowledge scope code")
    parser.add_argument("--collection-code", default="breslov_primary", help="Collection code for metadata")
    parser.add_argument("--backend", choices=("pgvector", "milvus", "both"), default="both")
    parser.add_argument("--batch-size", type=int, default=64, help="Embedding batch size")
    parser.add_argument("--drop-derived", action="store_true", help="Drop existing pgvector table and Milvus collection before backfill")
    parser.add_argument("--dry-run", action="store_true", help="Only count pages, no inserts")
    parser.add_argument("--force", action="store_true", help="Required for destructive operations")
    parser.add_argument("--json-out", type=Path, required=True, help="Output JSON path")
    args = parser.parse_args()

    report = asyncio.run(backfill(args))
    report["args"] = {
        "run_id": args.run_id, "scope": args.scope,
        "collection_code": args.collection_code, "backend": args.backend,
        "batch_size": args.batch_size, "drop_derived": args.drop_derived,
        "dry_run": args.dry_run, "force": args.force,
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps({"status": report["status"], "inserted_pg": report.get("inserted_pg", 0),
                      "inserted_milvus": report.get("inserted_milvus", 0),
                      "expected": report.get("expected", 0),
                      "errors": report.get("error_count", 0)}))
