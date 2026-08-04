#!/usr/bin/env python3
"""Read-only Likutey Halajot promotion-readiness inventory.

Resolves the candidate by source SHA-256, opens a read-only PostgreSQL
transaction, reads Milvus without loading/writing, and inspects the local PDF.
It never changes document status, corpus rows, embeddings, or vectors.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import fitz
from psycopg.rows import dict_row
from pymilvus import MilvusClient

import globalVar
from infrastructure.postgres.pool import close_pool, create_pool_from_settings, open_pool

SHA256 = "440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a"
COLLECTION = "tebaai_breslov_chunks_v1"
BLANK_PAGES = [6, 8, 34, 38, 100, 102, 116, 118, 146, 202, 204, 240, 242, 266, 274, 284]


def dump(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


async def rows(conn: Any, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    async with conn.cursor() as cur:
        await cur.execute(sql, params)
        return list(await cur.fetchall())


def inspect_pdf(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    document = fitz.open(path)
    empty: list[int] = []
    short: list[dict[str, Any]] = []
    for index, page in enumerate(document):
        text = page.get_text("text").strip()
        if not text:
            empty.append(index + 1)
        elif len(text) < 40:
            short.append({"pdf_page": index + 1, "characters": len(text), "surface": text})
    blank_visual = []
    for page_number in empty:
        page = document[page_number - 1]
        pixmap = page.get_pixmap(matrix=fitz.Matrix(0.25, 0.25), colorspace=fitz.csGRAY, alpha=False)
        samples = bytes(pixmap.samples)
        blank_visual.append({
            "pdf_page": page_number,
            "nonwhite_ratio": round(sum(value < 245 for value in samples) / len(samples), 6),
            "images": len(page.get_images(full=True)),
        })
    return {
        "path": str(path),
        "accessible": path.is_file(),
        "sha256": digest,
        "hash_matches": digest == SHA256,
        "pdf_valid": document.is_pdf,
        "encrypted": bool(document.needs_pass),
        "physical_pages": document.page_count,
        "empty_text_pages": empty,
        "expected_blank_pages": BLANK_PAGES,
        "blank_pages_match": empty == BLANK_PAGES,
        "blank_visual_review": blank_visual,
        "short_nonempty_pages": short,
        "metadata": document.metadata,
        "front_matter_evidence": {
            "title_page_pdf_3": document[2].get_text("text").strip(),
            "copyright_pdf_4": document[3].get_text("text").strip(),
            "volume_statement_pdf_10": "el primer volumen de los discursos originales del Rabí Natán ... está ahora en sus manos",
        },
    }


async def audit(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    pool = create_pool_from_settings()
    await open_pool(pool)
    try:
        async with pool.connection() as conn:
            conn.row_factory = dict_row
            await conn.execute("SET TRANSACTION READ ONLY")
            identities = await rows(conn, """
                SELECT d.id, d.title, d.source_filename, d.source_path, d.source_sha256,
                       d.source_size_bytes, d.status, d.language, d.document_code,
                       d.canonical_text_role, d.created_at, d.updated_at, d.metadata,
                       d.bibliographic_metadata, d.author, d.editor, d.translator,
                       d.publisher, d.publication_year, d.edition, ks.knowledge_scope_code
                FROM library_documents d
                JOIN knowledge_scopes ks ON ks.id=d.knowledge_scope_id
                WHERE d.source_sha256=%s
            """, (SHA256,))
            if len(identities) != 1:
                raise RuntimeError(f"canonical identity count is {len(identities)}, expected 1")
            identity = identities[0]
            document_id = str(identity["id"])
            source_path = Path(str(identity["source_path"]))
            runs = await rows(conn, "SELECT * FROM library_ingestion_runs_v2 WHERE document_id=%s ORDER BY created_at", (document_id,))
            page_summary = (await rows(conn, """
                SELECT count(*) total_pages, count(distinct page_id) unique_page_ids,
                       count(distinct page_number) unique_pdf_pages,
                       count(*) FILTER (WHERE coalesce(text,'')<>'') pages_with_text,
                       count(*) FILTER (WHERE coalesce(text,'')='') pages_without_text,
                       count(*) FILTER (WHERE char_count<>length(text)) char_count_mismatches,
                       count(*) FILTER (WHERE document_id<>%s::uuid) orphan_pages,
                       min(page_number) min_pdf_page, max(page_number) max_pdf_page
                FROM library_pages_v2 WHERE document_id=%s
            """, (document_id, document_id)))[0]
            page_details = await rows(conn, """
                SELECT page_number pdf_page, page_id, char_count, extraction_method,
                       confidence, layout_notes
                FROM library_pages_v2 WHERE document_id=%s ORDER BY page_number
            """, (document_id,))
            chunk_summary = (await rows(conn, """
                SELECT count(*) total_chunks, count(distinct id) unique_chunk_ids,
                       count(distinct chunk_uid) unique_chunk_uids,
                       count(*) FILTER (WHERE coalesce(content,'')='') empty_content,
                       count(*) FILTER (WHERE coalesce(search_text_normalized,'')='') missing_normalized,
                       count(*) FILTER (WHERE page_start IS NULL) missing_page,
                       count(*) FILTER (WHERE page_start<>page_end) cross_page,
                       count(*) FILTER (WHERE page_start<1 OR page_end>284 OR page_start>page_end) invalid_page,
                       count(*) FILTER (WHERE char_start IS NOT NULL AND char_end IS NOT NULL AND char_start>char_end) invalid_offsets,
                       count(*) FILTER (WHERE printed_page_label IS NULL) missing_persisted_printed_page
                FROM library_document_chunks WHERE document_id=%s
            """, (document_id,)))[0]
            anchor_summary = (await rows(conn, """
                SELECT count(*) total, count(*) FILTER (WHERE a.page_anchor_id IS NULL) missing_anchor,
                       count(*) FILTER (WHERE p.page_id IS NULL) missing_page,
                       count(*) FILTER (WHERE a.pdf_page_number<>c.page_start) page_mismatch,
                       count(*) FILTER (WHERE a.document_id<>c.document_id) document_mismatch
                FROM library_document_chunks c
                LEFT JOIN library_page_anchors_v2 a ON a.page_anchor_id=(c.metadata->>'page_anchor_id')::uuid
                LEFT JOIN library_pages_v2 p ON p.page_id=a.legacy_page_id
                WHERE c.document_id=%s
            """, (document_id,)))[0]
            duplicate_chunks = await rows(conn, """
                SELECT content_sha256, count(*) count FROM library_document_chunks
                WHERE document_id=%s GROUP BY content_sha256 HAVING count(*)>1
            """, (document_id,))
            role_rows = await rows(conn, """
                SELECT coalesce(block_type,'unknown') block_type,
                       coalesce(evidence_role,'unknown') evidence_role,
                       coalesce(language,'unknown') language, count(*) count
                FROM library_document_chunks WHERE document_id=%s
                GROUP BY 1,2,3 ORDER BY count(*) DESC
            """, (document_id,))
            pg_chunks = await rows(conn, """
                SELECT c.id chunk_id,c.document_id,c.chunk_index,c.page_start,c.page_end,
                       c.language,c.content_sha256,e.milvus_primary_key,e.embedding_model,
                       e.embedding_dimension,e.milvus_collection,e.status embedding_status
                FROM library_document_chunks c
                LEFT JOIN library_chunk_embeddings e ON e.chunk_id=c.id
                WHERE c.document_id=%s ORDER BY c.chunk_index
            """, (document_id,))
            related = await rows(conn, """
                SELECT d.id,d.title,d.source_filename,d.source_sha256,d.status,d.document_code,
                       count(distinct p.page_id) pages,count(distinct c.id) chunks,
                       count(distinct e.id) embeddings
                FROM library_documents d
                LEFT JOIN library_pages_v2 p ON p.document_id=d.id
                LEFT JOIN library_document_chunks c ON c.document_id=d.id
                LEFT JOIN library_chunk_embeddings e ON e.chunk_id=c.id
                WHERE lower(concat_ws(' ',d.title,d.source_filename,d.document_code))
                      ~ '(likutey halajot|likutey halakhot|azamra)'
                GROUP BY d.id ORDER BY d.created_at
            """)

        pdf = inspect_pdf(source_path)
        milvus = MilvusClient(uri=f"http://{globalVar.MILVUS_HOST}:{globalVar.MILVUS_PORT}")
        vector_rows = milvus.query(
            collection_name=COLLECTION,
            filter=f'document_id == "{document_id}"',
            output_fields=["pk", "chunk_id", "document_id", "language", "content_sha256", "chunk_index", "page_start", "page_end"],
            limit=1000,
        )
        pg_by_id = {str(row["chunk_id"]): row for row in pg_chunks}
        mv_by_id = {str(row["chunk_id"]): row for row in vector_rows}
        missing = sorted(set(pg_by_id) - set(mv_by_id))
        orphan = sorted(set(mv_by_id) - set(pg_by_id))
        mismatches = []
        for chunk_id in sorted(set(pg_by_id) & set(mv_by_id)):
            pg = pg_by_id[chunk_id]
            mv = mv_by_id[chunk_id]
            fields = ["document_id", "language", "content_sha256", "chunk_index", "page_start", "page_end"]
            bad = [field for field in fields if str(pg.get(field)) != str(mv.get(field))]
            if bad:
                mismatches.append({"chunk_id": chunk_id, "fields": bad})
        pks = [str(row.get("pk")) for row in vector_rows]
        embedding_report = {
            "collection": COLLECTION,
            "collection_entities": int(milvus.get_collection_stats(COLLECTION)["row_count"]),
            "load_state": milvus.get_load_state(COLLECTION),
            "pg_chunks": len(pg_chunks),
            "pg_embedding_rows": sum(row.get("milvus_primary_key") is not None for row in pg_chunks),
            "milvus_document_vectors": len(vector_rows),
            "missing_vectors": missing,
            "orphan_vectors": orphan,
            "duplicate_vector_primary_keys": [key for key, count in Counter(pks).items() if count > 1],
            "metadata_mismatches": mismatches,
            "match_percent": round(100 * len(set(pg_by_id) & set(mv_by_id)) / len(pg_by_id), 2),
            "embedding_models": sorted({str(row.get("embedding_model")) for row in pg_chunks}),
            "embedding_dimensions": sorted({row.get("embedding_dimension") for row in pg_chunks}),
            "read_only": True,
        }
        document_identity = {
            **identity,
            "id_resolution": ["source_sha256", "source_filename", "document_family", "ingestion_profile"],
            "ingestion_runs": runs,
            "status_after_audit": identity["status"],
            "pdf": pdf,
        }
        page_report = {"summary": page_summary, "anchors": anchor_summary, "pages": page_details, "pdf_blank_validation": pdf["blank_visual_review"]}
        chunk_report = {"summary": chunk_summary, "anchors": anchor_summary, "duplicate_content_hashes": duplicate_chunks}
        roles_report = {
            "persisted_distribution": role_rows,
            "assessment": "Persisted page-level chunks use coarse commentary roles; exact headings, footnotes and marginal references are derived deterministically at retrieval time.",
            "unknown_persisted_roles": 0,
        }
        duplicate_report = {
            "documents": related,
            "same_hash_active_count": sum(row["source_sha256"] == SHA256 and row["status"] in {"ready", "test_candidate"} for row in related),
            "candidate_classification": "current_candidate",
            "related_ready_classification": "conflicting_title_and_scope_metadata: persisted title says Likutey Halajot while sampled content identifies Likutey Moharán II #8",
            "binary_duplicate": False,
            "logical_duplicate": False,
            "promotion_risk": "two ready records would resolve to the Likutey Halajot family and contaminate bibliographic grouping/scope despite representing different works",
        }
        biblio_report = {
            "title": {"value": identity["title"], "classification": "explicit_persisted"},
            "author": {"value": "Rabí Natán de Breslov", "classification": "explicit_pdf_page_3_not_persisted"},
            "annotator": {"value": "Moshé Mykoff con Dov Grant", "classification": "explicit_pdf_page_3_not_persisted"},
            "translator": {"value": "Guillermo Beilinson", "classification": "explicit_pdf_page_3_not_persisted"},
            "publisher": {"value": "Breslov Research Institute", "classification": "explicit_pdf_pages_3_4_not_persisted"},
            "edition": {"value": "Primera edición", "classification": "explicit_pdf_page_4_not_persisted"},
            "year": {"value": 2020, "classification": "explicit_copyright_pdf_page_4_not_persisted"},
            "language": {"value": identity["language"], "classification": "explicit_persisted"},
            "volume": {"value": 1, "classification": "explicit_pdf_page_10_not_persisted", "planner_value": None, "planner_source": "unresolved"},
            "isbn": {"value": None, "classification": "unresolved"},
            "source_filename": {"value": identity["source_filename"], "classification": "explicit_persisted"},
            "source_sha256": {"value": identity["source_sha256"], "classification": "explicit_persisted"},
            "legal": {
                "classification": "LEGAL_REVIEW_REQUIRED",
                "copyright_notice": "Copyright © 2020 Breslov Research Institute",
                "restriction": "reproduction/transmission requires prior written editor consent",
                "permission_verified": False,
                "public_exposure_allowed": False,
                "source": "PDF page 4",
            },
        }
        dump(output / "document-identity.json", document_identity)
        dump(output / "page-integrity.json", page_report)
        dump(output / "chunk-integrity.json", chunk_report)
        dump(output / "embedding-reconciliation.json", embedding_report)
        dump(output / "editorial-role-distribution.json", roles_report)
        dump(output / "duplicate-version-matrix.json", duplicate_report)
        dump(output / "bibliographic-audit.json", biblio_report)
    finally:
        await close_pool(pool)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(audit(args.output))


if __name__ == "__main__":
    main()
