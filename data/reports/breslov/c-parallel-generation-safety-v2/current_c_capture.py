#!/usr/bin/env python3
"""Read-only snapshot of CURRENT C plus global store fingerprints.

Usage: current_c_capture.py <label>
Writes current-c-<label>.json. Never writes PostgreSQL or Milvus.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path

BACKEND = Path(os.environ.get(
    "AUTHORITATIVE_BACKEND",
    "/tmp/opencode/tebaai-b4a26a9/SrvRestAstroLS_v1/backend",
))
sys.path.insert(0, str(BACKEND))

import psycopg  # noqa: E402
from psycopg.rows import dict_row  # noqa: E402

OUT = Path(__file__).resolve().parent
DOC = "ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa"
LOGICAL = "db200a31-b547-5668-d968-06d0ec36ad95"
SOURCE = Path(
    "/media/issajar/DEVELOP/Projects/iMotorSoft/ai/dev/TebaAI/SrvRestAstroLS_v1/"
    "backend/sources/ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa/original.pdf"
)


def dsn() -> str:
    return (
        f"host={os.environ['DB_PG_IP']} port={os.environ.get('DB_PG_PORT', '5432')} "
        f"user={os.environ['DB_PG_USER']} password={os.environ['DB_PG_PASS']} "
        f"dbname={os.environ.get('TEBAAI_DB_NAME', 'tebaai')}"
    )


def milvus_c_count() -> int | None:
    try:
        from pymilvus import Collection

        col = Collection("tebaai_breslov_chunks_v1")
        col.load()
        rows = col.query(
            expr=f'document_id == "{DOC}"', output_fields=["count(*)"]
        )
        return int(rows[0]["count(*)"]) if rows else 0
    except Exception as exc:  # noqa: BLE001
        return f"UNAVAILABLE:{type(exc).__name__}"


async def main(label: str) -> None:
    async with await psycopg.AsyncConnection.connect(
        dsn(), row_factory=dict_row
    ) as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id,title,status,logical_document_id,source_sha256,source_path "
                "FROM library_documents WHERE id=%s", (DOC,)
            )
            doc = dict(await cur.fetchone())
            await cur.execute(
                "SELECT id,status,document_id,run_id,retention_hold,source_sha256,"
                "activated_at,deactivated_at FROM library_document_generations "
                "WHERE document_id=%s ORDER BY created_at,id", (DOC,)
            )
            generations = [dict(r) for r in await cur.fetchall()]
            await cur.execute(
                "SELECT generation_id,expected_generation_id,operation,activated_at "
                "FROM library_logical_document_active_generations "
                "WHERE logical_document_id=%s", (LOGICAL,)
            )
            pointer_row = await cur.fetchone()
            pointer = dict(pointer_row) if pointer_row else None
            await cur.execute(
                "SELECT count(*) AS c FROM library_pages_v2 WHERE document_id=%s",
                (DOC,)
            )
            pages = (await cur.fetchone())["c"]
            await cur.execute(
                "SELECT count(*) AS c, coalesce(sum(length(content)),0) AS chars, "
                "coalesce(sum(length(content)-length(replace(content, chr(65533), ''))),0) AS fffd, "
                "md5(coalesce(string_agg(content, '' ORDER BY chunk_index, id), '')) AS digest "
                "FROM library_document_chunks WHERE document_id=%s", (DOC,)
            )
            chunks = dict(await cur.fetchone())
            await cur.execute(
                "SELECT count(*) AS c FROM library_chunk_embeddings e "
                "JOIN library_document_chunks ch ON ch.id=e.chunk_id "
                "WHERE ch.document_id=%s", (DOC,)
            )
            embeddings = (await cur.fetchone())["c"]
            await cur.execute(
                "SELECT count(*) AS docs FROM library_documents"
            )
            total_docs = (await cur.fetchone())["docs"]
            await cur.execute(
                "SELECT count(*) AS c FROM library_document_chunks"
            )
            total_chunks = (await cur.fetchone())["c"]
            await cur.execute(
                "SELECT count(*) AS c FROM library_chunk_embeddings"
            )
            total_embeddings = (await cur.fetchone())["c"]
            await cur.execute(
                "SELECT count(*) AS c FROM library_document_generations"
            )
            total_generations = (await cur.fetchone())["c"]
            await cur.execute(
                "SELECT count(*) AS c FROM library_ingestion_runs_v2"
            )
            total_runs = (await cur.fetchone())["c"]

    snapshot = {
        "label": label,
        "document_id": DOC,
        "logical_document_id": LOGICAL,
        "document": {
            "title": doc["title"],
            "status": doc["status"],
            "logical_document_id": str(doc["logical_document_id"]),
            "source_sha256": doc["source_sha256"],
            "source_path": doc["source_path"],
        },
        "generations": [
            {
                "id": str(g["id"]),
                "status": g["status"],
                "document_id": str(g["document_id"]),
                "run_id": str(g["run_id"]) if g["run_id"] else None,
                "retention_hold": g["retention_hold"],
                "source_sha256": g["source_sha256"],
                "activated_at": g["activated_at"].isoformat() if g["activated_at"] else None,
                "deactivated_at": g["deactivated_at"].isoformat() if g["deactivated_at"] else None,
            }
            for g in generations
        ],
        "active_generation_id": next(
            (str(g["id"]) for g in generations if g["status"] == "ACTIVE"), None
        ),
        "active_pointer": {
            "generation_id": str(pointer["generation_id"]) if pointer else None,
            "expected_generation_id": str(pointer["expected_generation_id"]) if pointer else None,
            "operation": pointer["operation"] if pointer else None,
        },
        "run_id": next(
            (str(g["run_id"]) for g in generations if g["status"] == "ACTIVE"), None
        ),
        "pages": pages,
        "chunks": chunks["c"],
        "chunk_chars": chunks["chars"],
        "chunk_content_digest_md5": chunks["digest"],
        "u_fffd": chunks["fffd"],
        "embeddings": embeddings,
        "milvus_vectors": milvus_c_count(),
        "global_store": {
            "documents": total_docs,
            "chunks": total_chunks,
            "embeddings": total_embeddings,
            "generations": total_generations,
            "ingestion_runs": total_runs,
        },
        "source": {
            "path": str(SOURCE),
            "exists": SOURCE.is_file(),
            "size": SOURCE.stat().st_size if SOURCE.is_file() else None,
            "sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest()
            if SOURCE.is_file() else None,
        },
    }
    (OUT / f"current-c-{label}.json").write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False, default=str)
    )
    print(json.dumps(snapshot, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "before"))
