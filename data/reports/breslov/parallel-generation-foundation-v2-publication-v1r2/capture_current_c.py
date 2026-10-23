#!/usr/bin/env python3
"""Read-only capture of the certified CURRENT C state.

No INSERT/UPDATE/DELETE, no Milvus mutation, no extraction/embedding.
Usage: capture_current_c.py <output.json>
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

BACKEND = Path(__file__).resolve().parents[4] / "SrvRestAstroLS_v1" / "backend"
sys.path.insert(0, str(BACKEND))

import globalVar as g  # noqa: E402
from modules.library.source_repository import get_page_publication  # noqa: E402

DOCUMENT_ID = "ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa"
LOGICAL_ID = "db200a31-b547-5668-d968-06d0ec36ad95"
EXPECTED_GENERATION = "1a8af56b-fc17-d9f9-ffc2-9efde54aa95b"
EXPECTED_RUN = "6c1a19b8-b60b-52de-b709-5496f4c6e937"
APPROVED_SHA = "440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a"


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def digest_rows(rows: list[dict]) -> str:
    payload = json.dumps(rows, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def milvus_count() -> dict:
    try:
        from pymilvus import Collection, connections

        connections.connect(alias="v1r2cap", host=g.MILVUS_HOST,
                            port=g.MILVUS_PORT, timeout=5)
        collection = Collection(g.MILVUS_COLLECTION_BRESLOV, using="v1r2cap")
        rows = collection.query(
            expr=f'document_id == "{DOCUMENT_ID}"',
            output_fields=["count(*)"],
            using="v1r2cap",
        )
        count = int(rows[0]["count(*)"]) if rows else 0
        connections.disconnect("v1r2cap")
        return {"reachable": True, "collection": g.MILVUS_COLLECTION_BRESLOV,
                "document_vector_count": count}
    except Exception as exc:  # noqa: BLE001
        return {"reachable": False, "error": f"{type(exc).__name__}: {exc}",
                "document_vector_count": None}


async def main(out: Path) -> None:
    async with await psycopg.AsyncConnection.connect(
        g.POSTGRES_DSN, row_factory=dict_row
    ) as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT * FROM library_documents WHERE id=%s", (DOCUMENT_ID,))
            document = await cur.fetchone()
            await cur.execute("SELECT * FROM library_logical_documents WHERE id=%s", (LOGICAL_ID,))
            logical = await cur.fetchone()
            await cur.execute(
                "SELECT * FROM library_document_generations WHERE logical_document_id=%s ORDER BY created_at",
                (LOGICAL_ID,),
            )
            generations = [dict(row) for row in await cur.fetchall()]
            await cur.execute(
                "SELECT * FROM library_logical_document_active_generations WHERE logical_document_id=%s",
                (LOGICAL_ID,),
            )
            pointer = await cur.fetchone()
            await cur.execute(
                """
                SELECT id, document_id, chunk_index, content_sha256, content_length,
                       page_start, page_end, citable
                FROM library_document_chunks WHERE document_id=%s
                ORDER BY chunk_index, id
                """,
                (DOCUMENT_ID,),
            )
            chunks = [dict(row) for row in await cur.fetchall()]
            await cur.execute(
                """
                SELECT e.chunk_id, e.embedding_provider, e.embedding_model,
                       e.embedding_dimension, e.content_sha256
                FROM library_chunk_embeddings e
                JOIN library_document_chunks ch ON ch.id = e.chunk_id
                WHERE ch.document_id=%s ORDER BY e.chunk_id
                """,
                (DOCUMENT_ID,),
            )
            embeddings = [dict(row) for row in await cur.fetchall()]
            await cur.execute(
                """
                SELECT page_id, run_id, page_number, char_count, extraction_method, confidence
                FROM library_pages_v2 WHERE document_id=%s ORDER BY page_number
                """,
                (DOCUMENT_ID,),
            )
            pages = [dict(row) for row in await cur.fetchall()]
            await cur.execute(
                "SELECT run_id, status, pipeline_version, finished_at FROM library_ingestion_runs_v2 WHERE document_id=%s ORDER BY run_id",
                (DOCUMENT_ID,),
            )
            runs = [dict(row) for row in await cur.fetchall()]
            await cur.execute(
                "SELECT count(*) AS n FROM library_visible_documents WHERE id=%s",
                (DOCUMENT_ID,),
            )
            visible = (await cur.fetchone())["n"]
            page_number = pages[0]["page_number"] if pages else 1
            publication = await get_page_publication(conn, __import__("uuid").UUID(DOCUMENT_ID), page_number)
            await cur.execute(
                """
                SELECT id, content, chunk_index FROM library_document_chunks
                WHERE document_id=%s AND citable=true ORDER BY chunk_index LIMIT 3
                """,
                (DOCUMENT_ID,),
            )
            representative_chunks = [dict(row) for row in await cur.fetchall()]

    durable_path = Path(document["source_path"]) if document and document["source_path"] else None
    durable_sha = sha256_file(durable_path) if durable_path else None
    chunk_digest_rows = [
        {k: row[k] for k in ("id", "document_id", "chunk_index", "content_sha256",
                             "content_length", "page_start", "page_end", "citable")}
        for row in chunks
    ]
    vector = milvus_count()

    report = {
        "captured_at_utc": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat(),
        "read_only": True,
        "document_id": DOCUMENT_ID,
        "logical_document_id": LOGICAL_ID,
        "document": {k: document[k] for k in (
            "id", "logical_document_id", "status", "source_path", "source_sha256",
            "source_filename", "source_size_bytes", "title", "collection_id",
            "knowledge_scope_id", "created_at", "updated_at")},
        "logical": {k: logical[k] for k in (
            "id", "collection_id", "knowledge_scope_id", "title", "source_sha256",
            "source_filename", "source_size_bytes", "created_at", "updated_at")},
        "generations": [
            {k: row[k] for k in (
                "id", "logical_document_id", "document_id", "run_id", "job_id",
                "attempt_number", "pipeline_version", "status", "source_sha256",
                "retention_hold", "activated_at", "deactivated_at", "created_at")}
            for row in generations
        ],
        "active_pointer": {k: pointer[k] for k in (
            "logical_document_id", "generation_id", "expected_generation_id",
            "operation", "activated_at", "activated_by")} if pointer else None,
        "chunks": {
            "count": len(chunks),
            "digest": digest_rows(chunk_digest_rows),
            "citable_count": sum(1 for row in chunks if row["citable"]),
            "page_span": [chunks[0]["page_start"], chunks[-1]["page_end"]] if chunks else None,
        },
        "embeddings": {
            "count": len(embeddings),
            "digest": digest_rows(embeddings),
            "models": sorted({f"{row['embedding_provider']}/{row['embedding_model']}" for row in embeddings}),
            "dimensions": sorted({row["embedding_dimension"] for row in embeddings}),
        },
        "pages": {
            "count": len(pages),
            "digest": digest_rows([{k: row[k] for k in (
                "page_id", "run_id", "page_number", "char_count",
                "extraction_method", "confidence")} for row in pages]),
        },
        "runs": [
            {k: row[k] for k in ("run_id", "status", "pipeline_version", "finished_at")}
            for row in runs
        ],
        "visible_in_library_visible_documents": visible,
        "viewer_publication": {
            "page_number": page_number,
            "resolved": publication is not None,
            "value": publication,
        },
        "representative_chunks": representative_chunks,
        "source": {
            "source_path": document["source_path"],
            "source_sha256": document["source_sha256"],
            "approved_sha256": APPROVED_SHA,
            "source_sha_matches_approved": document["source_sha256"] == APPROVED_SHA,
            "managed_source_exists": bool(durable_path and durable_path.is_file()),
            "managed_source_sha256": durable_sha,
            "managed_sha_matches_approved": durable_sha == APPROVED_SHA,
        },
        "milvus": vector,
        "expected": {
            "active_generation": EXPECTED_GENERATION,
            "run_id": EXPECTED_RUN,
            "chunks": 942,
            "vectors": 942,
        },
        "matches_expected": {
            "active_generation": bool(pointer) and str(pointer["generation_id"]) == EXPECTED_GENERATION,
            "single_generation_active": sum(1 for row in generations if row["status"] == "ACTIVE") == 1,
            "run_id": any(str(row["run_id"]) == EXPECTED_RUN for row in generations),
            "chunks_942": len(chunks) == 942,
            "vectors_942": vector.get("document_vector_count") == 942,
            "embeddings_942": len(embeddings) == 942,
        },
    }
    out.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(report["matches_expected"], indent=2))
    print("chunk_digest", report["chunks"]["digest"])
    print("pages_digest", report["pages"]["digest"])
    print("embeddings_digest", report["embeddings"]["digest"])


if __name__ == "__main__":
    import asyncio

    asyncio.run(main(Path(sys.argv[1])))
