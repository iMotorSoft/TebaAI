"""Read-only snapshot of document C and every row family that must not move.

Usage: capture_state.py <label> <output.json>

The PostgreSQL session is opened with ``default_transaction_read_only=on``.
Milvus is only queried (``query``/``get_collection_stats``); never inserted,
upserted or deleted.
"""
from __future__ import annotations

import hashlib
import json
import sys

import certlib as c


MILVUS_FILTER = f'document_id == "{c.DOCUMENT_ID}"'


def milvus_snapshot() -> dict:
    try:
        from pymilvus import MilvusClient

        import globalVar as config

        client = MilvusClient(uri=f"http://{config.MILVUS_HOST}:{config.MILVUS_PORT}")
        collection = config.MILVUS_COLLECTION_BRESLOV
        rows = client.query(
            collection_name=collection,
            filter=MILVUS_FILTER,
            output_fields=["chunk_id", "content_sha256", "source_sha256"],
            limit=16384,
        )
        entities = sorted(
            (
                str(row.get("chunk_id", "")),
                str(row.get("content_sha256", "")),
                str(row.get("source_sha256", "")),
            )
            for row in rows
        )
        stats = client.get_collection_stats(collection_name=collection)
        return {
            "status": "OK",
            "collection": collection,
            "entities_for_c": len(rows),
            "chunk_id_digest": hashlib.md5(
                "".join(row[0] for row in entities).encode()
            ).hexdigest(),
            "content_sha_digest": hashlib.md5(
                "".join(sorted(row[1] for row in entities)).encode()
            ).hexdigest(),
            "chunk_identity_digest": hashlib.md5(
                json.dumps(entities, separators=(",", ":")).encode()
            ).hexdigest(),
            "collection_num_entities": int(stats.get("row_count", -1)),
        }
    except Exception as exc:  # noqa: BLE001 - limitation must stay explicit
        return {"status": "UNAVAILABLE", "error": f"{type(exc).__name__}: {exc}"}


async def snapshot(label: str) -> dict:
    async with await c.connect_readonly() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT to_jsonb(d) AS row,
                       md5(to_jsonb(d)::text) AS full_digest,
                       md5((to_jsonb(d) - 'source_path' - 'source_uri' - 'updated_at')::text)
                           AS content_digest
                FROM library_documents d WHERE d.id=%s
                """,
                (c.DOCUMENT_ID,),
            )
            document = await cur.fetchone()

            await cur.execute(
                """
                SELECT to_jsonb(l) AS row, md5(to_jsonb(l)::text) AS digest
                FROM library_logical_documents l WHERE l.id=%s
                """,
                (c.LOGICAL_DOCUMENT_ID,),
            )
            logical = await cur.fetchone()

            await cur.execute(
                """
                SELECT md5(COALESCE(string_agg(to_jsonb(g)::text, '' ORDER BY g.id), '')) AS digest,
                       count(*) AS generations
                FROM library_document_generations g
                WHERE g.logical_document_id=%s
                """,
                (c.LOGICAL_DOCUMENT_ID,),
            )
            generations = await cur.fetchone()

            await cur.execute(
                """
                SELECT g.id, g.status, g.document_id, g.logical_document_id, g.run_id,
                       g.attempt_number, g.pipeline_version, g.created_at, g.activated_at,
                       g.deactivated_at
                FROM library_document_generations g
                WHERE g.logical_document_id=%s ORDER BY g.id
                """,
                (c.LOGICAL_DOCUMENT_ID,),
            )
            generation_rows = await cur.fetchall()

            await cur.execute(
                """
                SELECT to_jsonb(ap) AS row, md5(to_jsonb(ap)::text) AS digest
                FROM library_logical_document_active_generations ap
                WHERE ap.logical_document_id=%s
                """,
                (c.LOGICAL_DOCUMENT_ID,),
            )
            pointer = await cur.fetchone()

            await cur.execute(
                """
                SELECT md5(COALESCE(string_agg(to_jsonb(a)::text, '' ORDER BY a.id), '')) AS digest,
                       count(*) AS audit_rows
                FROM library_generation_activation_audit a
                WHERE a.logical_document_id=%s
                """,
                (c.LOGICAL_DOCUMENT_ID,),
            )
            audit = await cur.fetchone()

            await cur.execute(
                """
                SELECT md5(COALESCE(string_agg(to_jsonb(t)::text, '' ORDER BY t.id), '')) AS digest,
                       count(*) AS texts
                FROM library_document_texts t WHERE t.document_id=%s
                """,
                (c.DOCUMENT_ID,),
            )
            texts = await cur.fetchone()

            await cur.execute(
                """
                SELECT md5(COALESCE(string_agg(to_jsonb(p)::text, '' ORDER BY p.page_id), '')) AS digest,
                       count(*) AS pages
                FROM library_pages_v2 p WHERE p.document_id=%s
                """,
                (c.DOCUMENT_ID,),
            )
            pages = await cur.fetchone()

            await cur.execute(
                """
                SELECT p.page_id, p.page_number, p.run_id,
                       md5(COALESCE(p.layout_notes::text, '')) AS layout_digest
                FROM library_pages_v2 p
                WHERE p.document_id=%s AND p.page_number IN (1, 187, 284)
                ORDER BY p.page_number
                """,
                (c.DOCUMENT_ID,),
            )
            representative_pages = await cur.fetchall()

            await cur.execute(
                """
                SELECT count(*) AS chunks,
                       md5(COALESCE(string_agg(c.content_sha256, '' ORDER BY c.id), ''))
                           AS content_digest,
                       md5(COALESCE(string_agg(to_jsonb(c)::text, '' ORDER BY c.id), ''))
                           AS row_digest,
                       max(c.updated_at) AS max_updated_at
                FROM library_document_chunks c WHERE c.document_id=%s
                """,
                (c.DOCUMENT_ID,),
            )
            chunks = await cur.fetchone()

            await cur.execute(
                """
                SELECT count(*) AS runs,
                       md5(COALESCE(string_agg(to_jsonb(r)::text, '' ORDER BY r.run_id), ''))
                           AS digest
                FROM library_ingestion_runs_v2 r WHERE r.document_id=%s
                """,
                (c.DOCUMENT_ID,),
            )
            ingestion_runs = await cur.fetchone()

            await cur.execute(
                """
                SELECT count(*) AS runs,
                       md5(COALESCE(string_agg(to_jsonb(e)::text, '' ORDER BY e.id), ''))
                           AS digest
                FROM library_embedding_runs e
                WHERE e.metadata->>'document_id'=%s
                """,
                (str(c.DOCUMENT_ID),),
            )
            embedding_runs = await cur.fetchone()

            await cur.execute(
                """
                SELECT to_jsonb(v) AS row, md5(to_jsonb(v)::text) AS digest
                FROM library_visible_documents v WHERE v.id=%s
                """,
                (c.DOCUMENT_ID,),
            )
            visible = await cur.fetchone()

            await cur.execute(
                """
                SELECT count(*) AS sessions,
                       md5(COALESCE(string_agg(s.id::text, '' ORDER BY s.id), '')) AS digest,
                       max(s.created_at) AS max_created_at
                FROM auth_sessions s
                """,
            )
            auth_sessions = await cur.fetchone()

    return {
        "label": label,
        "captured_at": c.now(),
        "document_id": str(c.DOCUMENT_ID),
        "logical_document_id": str(c.LOGICAL_DOCUMENT_ID),
        "document": document,
        "logical_document": logical,
        "generations": generations,
        "generation_rows": generation_rows,
        "active_pointer": pointer,
        "audit": audit,
        "texts": texts,
        "pages": pages,
        "representative_pages": representative_pages,
        "chunks": chunks,
        "ingestion_runs": ingestion_runs,
        "embedding_runs": embedding_runs,
        "visible_document": visible,
        "auth_sessions": auth_sessions,
        "milvus": milvus_snapshot(),
        "backend": {
            "pid": c.backend_pid(),
            "cmdline": c.backend_cmdline(c.backend_pid()),
        },
        "read_only_session": True,
    }


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: capture_state.py <label> <output.json>")
    import asyncio

    label, output = sys.argv[1], sys.argv[2]
    body = asyncio.run(snapshot(label))
    c.write_json(output, body)
    print(
        json.dumps(
            {
                "written": output,
                "label": label,
                "chunks": body["chunks"]["chunks"],
                "pages": body["pages"]["pages"],
                "vectors": body["milvus"].get("entities_for_c"),
                "active_generation": body["active_pointer"]["row"]["generation_id"]
                if body["active_pointer"]
                else None,
                "source_path": body["document"]["row"]["source_path"],
                "backend_pid": body["backend"]["pid"],
            }
        )
    )


if __name__ == "__main__":
    main()
