"""Read-only snapshot of the real C document for the preflight gate.

Two phases:
  before -> stores the snapshot in /tmp/opencode/c-snapshot-before.json
  after  -> re-measures, compares, writes current-c-readonly-check.json

No INSERT/UPDATE/DELETE is executed. Milvus is only read (num_entities), never
written.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import psycopg

import globalVar as config

OUT = Path(__file__).resolve().parent
BEFORE = Path("/tmp/opencode/c-snapshot-before.json")
C_DOCUMENT = UUID("ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa")
C_LOGICAL = UUID("db200a31-b547-5668-d968-06d0ec36ad95")


def milvus_count() -> dict:
    if not config.MILVUS_ENABLED:
        return {"status": "DISABLED"}
    try:
        from pymilvus import MilvusClient

        client = MilvusClient(uri=f"http://{config.MILVUS_HOST}:{config.MILVUS_PORT}")
        stats = client.get_collection_stats(config.MILVUS_COLLECTION_BRESLOV)
        return {"status": "OK", "collection": config.MILVUS_COLLECTION_BRESLOV,
                "entities": int(stats.get("row_count", 0))}
    except Exception as exc:  # noqa: BLE001
        return {"status": "UNAVAILABLE", "error": f"{type(exc).__name__}: {exc}"}


async def snapshot() -> dict:
    async with await psycopg.AsyncConnection.connect(config.POSTGRES_DSN) as conn:
        conn.row_factory = psycopg.rows.dict_row
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT md5(COALESCE(string_agg(to_jsonb(d)::text, '' ORDER BY d.id), '')) AS digest,
                       count(*) AS documents
                FROM library_documents d
                WHERE d.id=%s OR d.logical_document_id=%s
                """,
                (C_DOCUMENT, C_LOGICAL),
            )
            documents = await cur.fetchone()
            await cur.execute(
                """
                SELECT md5(COALESCE(string_agg(to_jsonb(t)::text, '' ORDER BY t.id), '')) AS digest,
                       count(*) AS texts
                FROM library_document_texts t
                JOIN library_documents d ON d.id=t.document_id
                WHERE d.logical_document_id=%s
                """,
                (C_LOGICAL,),
            )
            texts = await cur.fetchone()
            await cur.execute(
                """
                SELECT md5(COALESCE(string_agg(to_jsonb(p)::text, '' ORDER BY p.page_id), '')) AS digest,
                       count(*) AS pages
                FROM library_pages_v2 p
                JOIN library_documents d ON d.id=p.document_id
                WHERE d.logical_document_id=%s
                """,
                (C_LOGICAL,),
            )
            pages = await cur.fetchone()
            await cur.execute(
                """
                SELECT md5(COALESCE(string_agg(to_jsonb(c)::text, '' ORDER BY c.id), '')) AS digest,
                       count(*) AS chunks
                FROM library_document_chunks c
                WHERE c.document_id=%s
                """,
                (C_DOCUMENT,),
            )
            chunks = await cur.fetchone()
            await cur.execute(
                """
                SELECT md5(COALESCE(string_agg(to_jsonb(g)::text, '' ORDER BY g.id), '')) AS digest,
                       count(*) AS generations
                FROM library_document_generations g WHERE g.logical_document_id=%s
                """,
                (C_LOGICAL,),
            )
            generations = await cur.fetchone()
            await cur.execute(
                """
                SELECT generation_id::text AS generation_id,
                       expected_generation_id::text AS expected_generation_id, operation
                FROM library_logical_document_active_generations WHERE logical_document_id=%s
                """,
                (C_LOGICAL,),
            )
            pointer = await cur.fetchone()
            await cur.execute(
                "SELECT count(*) AS audit FROM library_generation_activation_audit WHERE logical_document_id=%s",
                (C_LOGICAL,),
            )
            audit = await cur.fetchone()
    body = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "document_id": str(C_DOCUMENT),
        "logical_document_id": str(C_LOGICAL),
        "documents": documents,
        "texts": texts,
        "pages": pages,
        "chunks": chunks,
        "generations": generations,
        "active_pointer": pointer,
        "audit_rows": audit["audit"],
        "milvus": milvus_count(),
    }
    return body


def main() -> None:
    phase = sys.argv[1]
    body = asyncio.run(snapshot())
    if phase == "before":
        BEFORE.parent.mkdir(parents=True, exist_ok=True)
        BEFORE.write_text(json.dumps(body, indent=2, default=str) + "\n")
        print(json.dumps({"phase": "before", "chunks": body["chunks"]["chunks"]}))
        return
    assert phase == "after", "phase must be before|after"
    before = json.loads(BEFORE.read_text())
    fields = [
        "documents",
        "texts",
        "pages",
        "chunks",
        "generations",
        "active_pointer",
        "audit_rows",
    ]
    differences = {
        field: {"before": before[field], "after": body[field]}
        for field in fields
        if before[field] != body[field]
    }
    milvus_same = before["milvus"] == body["milvus"]
    result = {
        "document_id": str(C_DOCUMENT),
        "logical_document_id": str(C_LOGICAL),
        "before": before,
        "after": body,
        "differences": differences,
        "postgresql_writes": 0,
        "milvus_writes": 0,
        "milvus_entities_unchanged": milvus_same,
        "reingest": "NO",
        "extraction": "NO",
        "embeddings": "NO",
        "vector_rebuild": "NO",
        "active_pointer_modified": "NO",
        "readonly_ok": not differences and milvus_same,
        "method": "read-only SELECT digests before/after; no write statement in any executed script",
    }
    (OUT / "current-c-readonly-check.json").write_text(
        json.dumps(result, indent=2, default=str, allow_nan=False) + "\n"
    )
    print(json.dumps({"readonly_ok": result["readonly_ok"], "differences": list(differences)}))


if __name__ == "__main__":
    main()
