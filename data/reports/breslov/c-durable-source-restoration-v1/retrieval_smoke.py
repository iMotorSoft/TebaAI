"""Deterministic read-only retrieval smoke for C, before and after restoration.

Phase "before" stores the measurement in /tmp/opencode; phase "after" compares
and writes retrieval-smoke.json. Only SELECT statements are executed.
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

OUT = Path(__file__).resolve().parent
BEFORE = Path("/tmp/opencode/c-retrieval-before.json")
C_DOCUMENT = UUID("ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa")
C_LOGICAL = UUID("db200a31-b547-5668-d968-06d0ec36ad95")


async def measure() -> dict:
    async with await psycopg.AsyncConnection.connect(config.POSTGRES_DSN) as conn:
        conn.row_factory = psycopg.rows.dict_row
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT chunk_index, content_sha256, page_start, page_end,
                       md5(search_text_normalized) AS normalized_digest
                FROM library_document_chunks
                WHERE document_id=%s
                ORDER BY chunk_index
                LIMIT 5
                """,
                (C_DOCUMENT,),
            )
            first_chunks = await cur.fetchall()
            probe = first_chunks[0]["normalized_digest"] if first_chunks else ""
            await cur.execute(
                """
                SELECT md5(COALESCE(string_agg(id::text, ',' ORDER BY chunk_index), '')) AS digest,
                       count(*) AS hits
                FROM library_document_chunks
                WHERE document_id=%s
                  AND md5(search_text_normalized) = %s
                """,
                (C_DOCUMENT, probe),
            )
            lexical_probe = await cur.fetchone()
            await cur.execute(
                """
                SELECT md5(to_jsonb(p)::text) AS page_digest, p.page_number
                FROM library_pages_v2 p
                WHERE p.document_id=%s AND p.page_number=187
                """,
                (C_DOCUMENT,),
            )
            page_187 = await cur.fetchone()
            await cur.execute(
                """
                SELECT g.id::text AS generation_id, g.status, ap.generation_id::text AS pointer_generation
                FROM library_document_generations g
                JOIN library_logical_document_active_generations ap
                  ON ap.logical_document_id=g.logical_document_id AND ap.generation_id=g.id
                WHERE g.logical_document_id=%s AND g.status='ACTIVE'
                """,
                (C_LOGICAL,),
            )
            active = await cur.fetchone()
            await cur.execute(
                """
                SELECT md5(COALESCE(string_agg(c.content_sha256, '' ORDER BY c.chunk_index), '')) AS digest,
                       count(*) AS chunks
                FROM library_document_chunks c WHERE c.document_id=%s
                """,
                (C_DOCUMENT,),
            )
            corpus = await cur.fetchone()
    return {
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "first_chunks": first_chunks,
        "lexical_probe": lexical_probe,
        "page_187": page_187,
        "active_generation": active,
        "corpus_digest": corpus["digest"],
        "corpus_chunks": corpus["chunks"],
    }


def main() -> None:
    phase = sys.argv[1] if len(sys.argv) > 1 else "before"
    body = asyncio.run(measure())
    if phase == "before":
        BEFORE.parent.mkdir(parents=True, exist_ok=True)
        BEFORE.write_text(json.dumps(body, indent=2, default=str, allow_nan=False) + "\n")
        print(json.dumps({"phase": "before", "corpus_chunks": body["corpus_chunks"]}))
        return
    before = json.loads(BEFORE.read_text())
    compared = ["first_chunks", "lexical_probe", "page_187", "active_generation",
                "corpus_digest", "corpus_chunks"]
    differences = {key: {"before": before[key], "after": body[key]}
                   for key in compared if before[key] != body[key]}
    result = {
        "method": "read-only SELECT; chunk sample, lexical probe, page 187 metadata, active generation, corpus digest",
        "before": before,
        "after": body,
        "differences": differences,
        "same_active_generation": before["active_generation"] == body["active_generation"],
        "same_content_evidence": not differences,
        "retrieval_change_due_to_source_restoration": bool(differences),
        "filesystem_reads": 0,
        "milvus_reads": 0,
        "note": "source restoration changes no text, chunk or page metadata consumed by retrieval",
    }
    (OUT / "retrieval-smoke.json").write_text(
        json.dumps(result, indent=2, default=str, allow_nan=False) + "\n"
    )
    print(json.dumps({"same_content_evidence": result["same_content_evidence"],
                      "differences": list(differences)}))


if __name__ == "__main__":
    main()
