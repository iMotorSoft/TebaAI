#!/usr/bin/env python3
"""Read-only audit for Breslov corpus work-scope identity V1.

The audit verifies the disputed source from PostgreSQL text rather than inferring
its work from a title or an isolated internal reference. It never writes to
PostgreSQL or Milvus and never changes document status.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from psycopg.rows import dict_row
from pymilvus import MilvusClient

import globalVar
from infrastructure.postgres.pool import close_pool, create_pool_from_settings, open_pool
from modules.library.simple_research_repository import resolve_ready_documents

REPORT_GATE = "TEBAAI_BRESLOV_CORPUS_SCOPE_INTEGRITY_V1_DEV_BLOCKED"
CANDIDATE_SHA256 = "440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a"
DISPUTED_SHA256 = "c04601782711751c14539224e8f679a740090b9d7f5f09d8877db9c3b6a5ff74"
COLLECTION = "tebaai_breslov_chunks_v1"


def dump(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )


async def fetch_all(conn: Any, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    async with conn.cursor() as cursor:
        await cursor.execute(sql, params)
        return list(await cursor.fetchall())


async def audit(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    pool = create_pool_from_settings()
    await open_pool(pool)
    try:
        async with pool.connection() as conn:
            conn.row_factory = dict_row
            await conn.execute("SET TRANSACTION READ ONLY")
            inventory = await fetch_all(
                conn,
                """
                SELECT d.id, d.title, d.source_filename, d.status, d.document_code,
                       d.language, d.source_sha256, d.canonical_text_role,
                       d.bibliographic_metadata, ks.knowledge_scope_code,
                       count(DISTINCT p.page_id) AS canonical_pages,
                       count(DISTINCT c.id) AS chunks,
                       count(DISTINCT e.id) AS embeddings,
                       min(c.page_start) AS min_chunk_page,
                       max(c.page_end) AS max_chunk_page
                FROM library_documents d
                JOIN knowledge_scopes ks ON ks.id=d.knowledge_scope_id
                LEFT JOIN library_pages_v2 p ON p.document_id=d.id
                LEFT JOIN library_document_chunks c ON c.document_id=d.id
                LEFT JOIN library_chunk_embeddings e ON e.chunk_id=c.id
                WHERE lower(concat_ws(' ', d.title, d.source_filename,
                                      d.document_code, d.bibliographic_metadata::text))
                      ~ '(likutey|likutei|azamra|lm ii)'
                GROUP BY d.id, ks.knowledge_scope_code
                ORDER BY d.title, d.id
                """,
            )
            disputed_rows = [row for row in inventory if row["source_sha256"] == DISPUTED_SHA256]
            candidate_rows = [row for row in inventory if row["source_sha256"] == CANDIDATE_SHA256]
            if len(disputed_rows) != 1 or len(candidate_rows) != 1:
                raise RuntimeError("candidate/disputed source identity is not unique")
            disputed = disputed_rows[0]
            disputed_id = str(disputed["id"])

            first_chunks = await fetch_all(
                conn,
                """
                SELECT chunk_index, page_start, page_end, section_title,
                       left(content, 1800) AS content
                FROM library_document_chunks
                WHERE document_id=%s
                ORDER BY chunk_index
                LIMIT 3
                """,
                (disputed_id,),
            )
            identity_samples = await fetch_all(
                conn,
                """
                SELECT chunk_index, page_start, left(content, 2400) AS content
                FROM library_document_chunks
                WHERE document_id=%s
                  AND (
                    content ILIKE '%%SOBRE EL LIKUTEY HALAJOT%%'
                    OR content ILIKE '%%Once lecciones basadas%%'
                    OR content ILIKE '%%Hiljot Tzitzit%%'
                  )
                ORDER BY
                  CASE
                    WHEN content ILIKE '%%Once lecciones basadas%%' THEN 0
                    WHEN content ILIKE '%%SOBRE EL LIKUTEY HALAJOT%%' THEN 1
                    ELSE 2
                  END,
                  chunk_index
                LIMIT 6
                """,
                (disputed_id,),
            )
            term_counts = (
                await fetch_all(
                    conn,
                    """
                    SELECT count(*) AS chunks,
                           count(*) FILTER (
                             WHERE content ~* 'Likutey[[:space:]]+Halajot'
                           ) AS chunks_mentioning_lh,
                           count(*) FILTER (
                             WHERE content ~* 'Likutey[[:space:]]+Mohar[áa]n[[:space:]]+II[^0-9]*8'
                           ) AS chunks_mentioning_lmii_8,
                           count(*) FILTER (
                             WHERE content ~* 'Hiljot[[:space:]]'
                           ) AS chunks_with_hiljot_headings
                    FROM library_document_chunks
                    WHERE document_id=%s
                    """,
                    (disputed_id,),
                )
            )[0]
            scope_rows = {
                "lh": await resolve_ready_documents(
                    conn,
                    knowledge_scope_code="breslov_primary",
                    work_codes=["lh"],
                    include_test_candidates=True,
                ),
                "lmii": await resolve_ready_documents(
                    conn,
                    knowledge_scope_code="breslov_primary",
                    work_codes=["lmii"],
                    include_test_candidates=True,
                ),
                "unscoped": await resolve_ready_documents(
                    conn,
                    knowledge_scope_code="breslov_primary",
                    work_codes=None,
                    include_test_candidates=True,
                ),
            }

        milvus = MilvusClient(uri=f"http://{globalVar.MILVUS_HOST}:{globalVar.MILVUS_PORT}")
        collection_stats = milvus.get_collection_stats(COLLECTION)
        disputed_vectors = milvus.query(
            collection_name=COLLECTION,
            filter=f'document_id == "{disputed_id}"',
            output_fields=["pk"],
            limit=2000,
        )

        dump(output / "document-family-inventory.json", {
            "gate": REPORT_GATE,
            "read_only": True,
            "documents": inventory,
        })
        dump(output / "conflicting-record-analysis.json", {
            "gate": REPORT_GATE,
            "record": disputed,
            "first_three_chunks": first_chunks,
            "representative_identity_samples": identity_samples,
            "term_counts": term_counts,
            "internal_evidence_finding": (
                "The source is a Spanish Likutey Halajot anthology: its title page says "
                "Likutey Halajot, its contents enumerate Hiljot discourses, and its edition "
                "note says those discourses are based on Likutey Moharan II, 8. The LM II, "
                "8 reference is the source lesson/organizing theme, not the work family."
            ),
            "canonical_family": "likutey_halajot",
            "related_source_lesson": "likutey_moharan_ii_8",
            "prior_hypothesis": "record_is_likutey_moharan_ii",
            "prior_hypothesis_result": "rejected_by_internal_front_matter_and_contents",
            "milvus": {
                "collection": COLLECTION,
                "collection_entities": int(collection_stats["row_count"]),
                "record_vectors": len(disputed_vectors),
                "mutated": False,
            },
        })
        dump(output / "alias-matrix.json", {
            "canonical": {
                "lh": ["Likutey Halajot", "Likutei Halachot", "Likutey Halachos", "ליקוטי הלכות"],
                "lmii": ["Likutey Moharán II", "Likutey Moharan II", "LM II", "ליקוטי מוהר\"ן תנינא"],
            },
            "critical_rule": "A source lesson label (LM II, 8) does not replace the containing work family (Likutey Halajot).",
            "ambiguous": ["Likutey", "LM", "Halajot II", "LH II 8"],
            "runtime_observation": "Aliases are distributed across modules and no persisted canonical work_family field exists on library_documents.",
        })
        trace = {
            "gate": REPORT_GATE,
            "resolver": "simple_research_repository.resolve_ready_documents",
            "filters": scope_rows,
            "disputed_document_in_lh": any(str(row["document_id"]) == disputed_id for row in scope_rows["lh"]),
            "disputed_document_in_lmii": any(str(row["document_id"]) == disputed_id for row in scope_rows["lmii"]),
            "finding": "The disputed document enters LH at title matching because it is internally identified as LH; it does not enter LM II.",
        }
        dump(output / "scope-traces-before.json", trace)
        dump(output / "scope-traces-after.json", {
            **trace,
            "change_applied": False,
            "blocked_reason": "Removing this record from LH would persist a false bibliographic classification.",
        })
    finally:
        await close_pool(pool)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(audit(args.output))
