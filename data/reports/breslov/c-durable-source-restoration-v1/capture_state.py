"""Read-only snapshot of document C for the durable source restoration gate.

Usage:
    python capture_state.py <output.json>

No INSERT/UPDATE/DELETE is executed. Milvus is queried read-only (query, never
insert/upsert/delete). The document digest deliberately excludes the source
metadata columns that this gate is authorized to change.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

BACKEND_DIR = Path(__file__).resolve().parents[4] / "SrvRestAstroLS_v1" / "backend"
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

import psycopg

import globalVar as config

C_DOCUMENT = UUID("ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa")
C_LOGICAL = UUID("db200a31-b547-5668-d968-06d0ec36ad95")
MILVUS_URI = f"http://{config.MILVUS_HOST}:{config.MILVUS_PORT}"
MILVUS_COLLECTION = config.MILVUS_COLLECTION_BRESLOV

SOURCE_COLUMNS = (
    "source_path",
    "source_uri",
    "source_filename",
    "source_sha256",
    "source_size_bytes",
    "source_mime_type",
)


def _json_default(value):
    from datetime import date, datetime as dt
    from decimal import Decimal
    from uuid import UUID as _UUID

    if isinstance(value, (_UUID, Path)):
        return str(value)
    if isinstance(value, (dt, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, memoryview):
        return value.tobytes().hex()
    raise TypeError(f"not serializable: {type(value)!r}")


def milvus_snapshot() -> dict:
    """Read-only vector inventory for document C."""
    try:
        from pymilvus import MilvusClient

        client = MilvusClient(uri=MILVUS_URI)
        rows = client.query(
            collection_name=MILVUS_COLLECTION,
            filter=f'document_id == "{C_DOCUMENT}"',
            output_fields=["chunk_id", "content_sha256", "source_sha256"],
            limit=16384,
        )
        chunk_ids = sorted(str(row["chunk_id"]) for row in rows)
        digest = hashlib.md5("".join(chunk_ids).encode()).hexdigest()
        content_digest = hashlib.md5(
            "".join(sorted(str(row.get("content_sha256", "")) for row in rows)).encode()
        ).hexdigest()
        total = client.query(
            collection_name=MILVUS_COLLECTION,
            filter="document_id != \"\"",
            output_fields=["chunk_id"],
            limit=16384,
        )
        return {
            "status": "OK",
            "collection": MILVUS_COLLECTION,
            "entities_for_c": len(rows),
            "chunk_id_digest": digest,
            "content_sha_digest": content_digest,
            "collection_total_entities": len(total),
        }
    except Exception as exc:  # noqa: BLE001 - limitation must be explicit
        return {"status": "UNAVAILABLE", "error": f"{type(exc).__name__}: {exc}"}


async def snapshot() -> dict:
    async with await psycopg.AsyncConnection.connect(config.POSTGRES_DSN) as conn:
        conn.row_factory = psycopg.rows.dict_row
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT to_jsonb(d) AS row,
                       md5(to_jsonb(d)::text) AS full_digest,
                       md5((to_jsonb(d) - 'source_path' - 'source_uri' - 'updated_at')::text)
                           AS content_digest
                FROM library_documents d WHERE d.id=%s
                """,
                (C_DOCUMENT,),
            )
            document = await cur.fetchone()

            await cur.execute(
                "SELECT to_jsonb(l) AS row FROM library_logical_documents l WHERE l.id=%s",
                (C_LOGICAL,),
            )
            logical = await cur.fetchone()

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
                SELECT g.id, g.status, g.run_id, g.document_id, g.logical_document_id,
                       g.metadata, g.created_at
                FROM library_document_generations g
                WHERE g.logical_document_id=%s ORDER BY g.id
                """,
                (C_LOGICAL,),
            )
            generation_rows = await cur.fetchall()

            await cur.execute(
                """
                SELECT logical_document_id, generation_id, expected_generation_id,
                       operation, activated_at, activated_by, metadata
                FROM library_logical_document_active_generations
                WHERE logical_document_id=%s
                """,
                (C_LOGICAL,),
            )
            pointer = await cur.fetchone()

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
                SELECT p.page_id, p.page_number, p.run_id, p.layout_notes
                FROM library_pages_v2 p
                JOIN library_documents d ON d.id=p.document_id
                WHERE d.logical_document_id=%s AND p.page_number IN (1, 187, 284)
                ORDER BY p.page_number
                """,
                (C_LOGICAL,),
            )
            representative_pages = await cur.fetchall()

            await cur.execute(
                """
                SELECT md5(COALESCE(string_agg(to_jsonb(c)::text, '' ORDER BY c.id), '')) AS digest,
                       md5(COALESCE(string_agg(c.content_sha256, '' ORDER BY c.id), '')) AS content_digest,
                       count(*) AS chunks
                FROM library_document_chunks c WHERE c.document_id=%s
                """,
                (C_DOCUMENT,),
            )
            chunks = await cur.fetchone()

            await cur.execute(
                """
                SELECT run_id, document_id, status, started_at, finished_at, metrics_json, warnings_json
                FROM library_ingestion_runs_v2
                WHERE document_id=%s ORDER BY run_id
                """,
                (C_DOCUMENT,),
            )
            ingestion_runs = await cur.fetchall()

            await cur.execute(
                """
                SELECT id, status, chunks_embedded, chunks_indexed, started_at, finished_at, metadata
                FROM library_embedding_runs
                WHERE metadata->>'document_id'=%s ORDER BY id
                """,
                (str(C_DOCUMENT),),
            )
            embedding_runs = await cur.fetchall()

            await cur.execute(
                "SELECT count(*) AS audit FROM library_generation_activation_audit WHERE logical_document_id=%s",
                (C_LOGICAL,),
            )
            audit = await cur.fetchone()

            await cur.execute(
                """
                SELECT d.id, d.status, d.source_path, d.source_uri, d.source_filename,
                       d.source_sha256, d.source_size_bytes, d.source_mime_type
                FROM library_visible_documents d WHERE d.id=%s
                """,
                (C_DOCUMENT,),
            )
            visible = await cur.fetchone()

    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "document_id": str(C_DOCUMENT),
        "logical_document_id": str(C_LOGICAL),
        "document": document,
        "logical_document": logical,
        "generations": generations,
        "generation_rows": generation_rows,
        "active_pointer": pointer,
        "texts": texts,
        "pages": pages,
        "representative_pages": representative_pages,
        "chunks": chunks,
        "ingestion_runs": ingestion_runs,
        "embedding_runs": embedding_runs,
        "audit_rows": audit["audit"],
        "visible_document": visible,
        "milvus": milvus_snapshot(),
    }


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: capture_state.py <output.json>")
    body = asyncio.run(snapshot())
    target = Path(sys.argv[1])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(body, indent=2, default=_json_default, allow_nan=False) + "\n")
    print(json.dumps({
        "written": str(target),
        "chunks": body["chunks"]["chunks"],
        "pages": body["pages"]["pages"],
        "vectors": body["milvus"].get("entities_for_c"),
        "source_path": body["document"]["row"]["source_path"],
    }))


if __name__ == "__main__":
    main()
