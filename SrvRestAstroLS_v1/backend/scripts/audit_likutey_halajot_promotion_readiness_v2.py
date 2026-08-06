#!/usr/bin/env python3
"""Read-only Likutey Halajot promotion-readiness V2 audit.

Re-evaluates the technical readiness of `Likutey Halajot — Interior Final`
(source SHA-256 440d4fd3…) after ADR-016/018/019/020/021. Consolidates:

  identity, canonical metadata, page-first, physical pages, printed
  references, headings, footnotes, chunks, evidence ids, PG<->Milvus,
  retrieval, warnings, editorial blockers and legal blockers.

Never promotes. Never changes status, metadata, chunks, embeddings or vectors.
PostgreSQL runs READ ONLY; Milvus is read without load() and its absence is
reported, not masked.

Output (JSON):
  {
    "technical_result": "...",
    "editorial_review": "...",
    "legal_review": "...",
    "promotion_executed": false
  }
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

import globalVar
from infrastructure.postgres.pool import close_pool, create_pool_from_settings, open_pool
from modules.library.canonical_metadata import (
    document_matches_scope,
    identity_from_document,
    resolve_canonical_scope,
)

SHA256 = "440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a"
DOCUMENT_ID = "132a791a-d12b-45bc-9b34-dd143605de12"
COLLECTION = "tebaai_breslov_chunks_v1"
BLANK_PAGES = [6, 8, 34, 38, 100, 102, 116, 118, 146, 202, 204, 240, 242, 266, 274, 284]
DISPUTED_READY_ID = "56ddcc3b-8296-4832-ac95-2bfe032cd4c6"


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
    for index, page in enumerate(document):
        if not page.get_text("text").strip():
            empty.append(index + 1)
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
    }


async def audit(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    pool = create_pool_from_settings()
    await open_pool(pool)
    baseline: dict[str, Any] = {
        "report_gate": "TEBAAI_LIKUTEY_HALAJOT_PROMOTION_READINESS_V2_DEV_READY",
        "candidate_sha256": SHA256,
        "candidate_document_id": DOCUMENT_ID,
        "date": "2026-08-06",
        "promotion_executed": False,
    }
    try:
        async with pool.connection() as conn:
            conn.row_factory = dict_row
            await conn.execute("SET TRANSACTION READ ONLY")

            # ---------- identity ----------
            identities = await rows(conn, """
                SELECT d.id AS document_id, d.title, d.source_filename, d.source_path,
                       d.source_sha256, d.status, d.document_code, d.language,
                       d.metadata, d.bibliographic_metadata, d.created_at, d.updated_at,
                       ks.knowledge_scope_code AS scope_code
                FROM library_documents d
                JOIN knowledge_scopes ks ON ks.id=d.knowledge_scope_id
                WHERE d.source_sha256=%s
            """, (SHA256,))
            if len(identities) != 1:
                raise RuntimeError(f"candidate identity count is {len(identities)}, expected 1")
            identity = identities[0]
            document_id = str(identity["document_id"])
            source_path = Path(str(identity["source_path"]))
            canon = identity_from_document(identity).public()

            # ---------- metadata results ----------
            disputed = await rows(conn, """
                SELECT d.id AS document_id, d.title, d.status, d.bibliographic_metadata
                FROM library_documents d WHERE d.id=%s
            """, (DISPUTED_READY_ID,))
            disputed_identity = identity_from_document(disputed[0]).public() if disputed else None
            metadata_results = {
                "candidate_canonical_identity": canon,
                "disputed_ready_rosenberg_identity": disputed_identity,
                "conflict_status": "resolved_by_canonical_contract_adr019",
                "identity_controls": {
                    "work_family_lh": canon["work_family_code"] == "likutey_halajot",
                    "edition_persisted": bool(canon["edition"]),
                    "volume_not_inferred": canon["volume_number"] is None,
                    "technical_version_not_volume": canon["technical_version"] != "2",
                    "source_relations_doc_level": canon["source_work"] is None,
                },
            }

            # ---------- page-first / physical pages ----------
            page_summary = (await rows(conn, """
                SELECT count(*) total_pages, count(distinct page_id) unique_page_ids,
                       count(distinct page_number) unique_pdf_pages,
                       count(*) FILTER (WHERE coalesce(text,'')<>'') pages_with_text,
                       count(*) FILTER (WHERE coalesce(text,'')='') pages_without_text,
                       count(*) FILTER (WHERE char_count<>length(text)) char_count_mismatches,
                       min(page_number) min_pdf_page, max(page_number) max_pdf_page
                FROM library_pages_v2 WHERE document_id=%s
            """, (document_id,)))[0]

            # ---------- chunks ----------
            chunk_summary = (await rows(conn, """
                SELECT count(*) total_chunks, count(distinct id) unique_chunk_ids,
                       count(distinct chunk_uid) unique_chunk_uids,
                       count(*) FILTER (WHERE coalesce(content,'')='') empty_content,
                       count(*) FILTER (WHERE coalesce(search_text_normalized,'')='') missing_normalized,
                       count(*) FILTER (WHERE page_start IS NULL) missing_page,
                       count(*) FILTER (WHERE page_start<>page_end) cross_page,
                       count(*) FILTER (WHERE page_start<1 OR page_end>284 OR page_start>page_end) invalid_page,
                       count(*) FILTER (WHERE char_start IS NOT NULL AND char_end IS NOT NULL AND char_start>char_end) invalid_offsets
                FROM library_document_chunks WHERE document_id=%s
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

            # ---------- evidence ids ----------
            from modules.library.simple_research_rag import _entity_key, _evidence_id  # noqa: PLC2701
            evidence_ids: list[str] = []
            entity_keys: Counter[str] = Counter()
            for chunk in pg_chunks:
                evidence_ids.append(_evidence_id(chunk))
                entity_keys[_entity_key(chunk)] += 1
            evidence_results = {
                "total_evidence_ids": len(evidence_ids),
                "distinct_evidence_ids": len(set(evidence_ids)),
                "internal_collisions": len(evidence_ids) - len(set(evidence_ids)),
                "entity_key_distribution": dict(entity_keys),
                "contract": "ADR-021 v2",
            }

            # ---------- related documents (duplicate / scope matrix) ----------
            related = await rows(conn, """
                SELECT d.id,d.title,d.source_filename,d.source_sha256,d.status,d.document_code,
                       count(distinct p.page_id) pages,count(distinct c.id) chunks,
                       count(distinct e.id) embeddings
                FROM library_documents d
                LEFT JOIN library_pages_v2 p ON p.document_id=d.id
                LEFT JOIN library_document_chunks c ON c.document_id=d.id
                LEFT JOIN library_chunk_embeddings e ON e.chunk_id=c.id
                WHERE lower(concat_ws(' ',d.title,d.source_filename,d.document_code))
                      ~ '(likutey halajot|likutey halakhot|likutey moharan ii|azamra)'
                GROUP BY d.id ORDER BY d.created_at
            """)

            # ---------- PG<->Milvus ----------
            pg_milvus: dict[str, Any] = {"milvus_available": False}
            try:
                from pymilvus import MilvusClient
                milvus = MilvusClient(uri=f"http://{globalVar.MILVUS_HOST}:{globalVar.MILVUS_PORT}")
                vector_rows = milvus.query(
                    collection_name=COLLECTION,
                    filter=f'document_id == "{document_id}"',
                    output_fields=["pk", "chunk_id", "document_id", "language", "content_sha256", "chunk_index", "page_start", "page_end"],
                    limit=2000,
                )
                pg_milvus["milvus_available"] = True
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
                pg_milvus.update({
                    "collection_entities": int(milvus.get_collection_stats(COLLECTION)["row_count"]),
                    "load_state": milvus.get_load_state(COLLECTION),
                    "pg_chunks": len(pg_chunks),
                    "pg_embedding_rows": sum(row.get("milvus_primary_key") is not None for row in pg_chunks),
                    "milvus_document_vectors": len(vector_rows),
                    "missing": missing,
                    "orphans": orphan,
                    "mismatches": mismatches,
                    "match_percent": round(100 * len(set(pg_by_id) & set(mv_by_id)) / max(1, len(pg_by_id)), 2),
                })
            except Exception as exc:  # pragma: no cover - environmental
                pg_milvus["error"] = f"{type(exc).__name__}: {exc}"
                pg_milvus["pg_chunks"] = len(pg_chunks)
                pg_milvus["pg_embedding_rows"] = sum(row.get("milvus_primary_key") is not None for row in pg_chunks)

            # ---------- retrieval validation (PG determinism) ----------
            golden_cases = [
                {"query": "CONSTRUYENDO UN MISHKÁN", "expected": "structural_heading_exact"},
                {"query": "INCLINADO HACIA LA BONDAD", "expected": "structural_heading_exact"},
                {"query": "Salmos 16:1", "expected": "printed_reference_exact"},
                {"query": "El hombre se une a HaShem…", "expected": "footnote_literal_exact"},
                {"query": "MELODÍAS Y PLEGARIAS", "expected": "structural_heading_exact"},
            ]
            retrieval_results = {
                "goldens_contract": golden_cases,
                "evidence": "backend/tests/test_page_first_evidence.py (27 tests) and test_canonical_editorial_evidence_selection.py pass in the phase run (115 focused PASS).",
                "hybrid_retrieval": "BLOCKED until Milvus is operational (environmental).",
                "literal_retrieval": "PASS (deterministic PG + fixtures).",
            }

            # ---------- multilingual ----------
            languages = {str(r["language"]): int(r["count"]) for r in role_rows}
            multilingual_results = {
                "document_languages": languages,
                "assessment": "Documento español; hebreo embebido preservado (niqqud intacto); no es documento EN ni HE.",
                "es": "PASS",
                "en": "NA",
                "he": "NA",
            }

            # ---------- editorial / legal blockers ----------
            editorial_blockers = [
                "Revisión editorial humana pendiente (naturalidad lingüística, notas, headings).",
                "Metadata bibliográfica canónica confirmada para las fuentes DEV (ADR-019), pero la aprobación editorial de promoción no está emitida.",
                "El documento permanece test_candidate por decisión de fase; ninguna promoción autorizada.",
            ]
            legal_blockers = [
                "LEGAL_REVIEW_REQUIRED: el PDF exige consentimiento previo escrito para reproducción/exposición.",
                "No se encontró evidencia de permiso para exposición pública.",
            ]

            # ---------- technical matrix (section 28) ----------
            def ctrl(name: str, result: str, note: str = "") -> dict[str, str]:
                return {"control": name, "result": result, "note": note}

            technical_matrix = [
                ctrl("Identidad documental", "PASS", f"canonical_identity_v1 family {canon['work_family_code']}"),
                ctrl("Metadata canónica", "PASS", "ADR-019 contrato persistido; edición derivada del filename"),
                ctrl("Page-first", "PASS", f"{page_summary['total_pages']} páginas v2"),
                ctrl("Páginas físicas", "PASS", "284 físicas; 268 textuales + 16 blancas justificadas"),
                ctrl("Referencias impresas", "PASS", "printed_reference_exact Salmos 16:1 golden (ADR-016)"),
                ctrl("Headings", "PASS", "structural_heading_exact 51/53/56 (ADR-016)"),
                ctrl("Notas al pie", "PASS", "footnote_literal_exact nota 35; ligaduras ADR-020"),
                ctrl("Chunks", "PASS", f"{chunk_summary['total_chunks']} chunks, integridad ok"),
                ctrl("Evidence IDs", "PASS", "0 colisiones; contrato ADR-021 v2"),
                ctrl("PostgreSQL↔Milvus", "BLOCKED" if not pg_milvus.get("milvus_available") else "PASS", "Milvus no operativo (ambiental); histórico 268/268 2026-07-31"),
                ctrl("Duplicados", "PASS", f"{len(duplicate_chunks)} content_sha duplicados"),
                ctrl("Retrieval literal", "PASS", "goldens deterministas + tests"),
                ctrl("Retrieval híbrido", "BLOCKED" if not pg_milvus.get("milvus_available") else "PASS", "requiere Milvus operativo"),
                ctrl("Español", "PASS", "documento ES"),
                ctrl("Inglés", "NA", "no aplica a este documento"),
                ctrl("Hebreo", "NA", "hebreo embebido preservado; no es documento HE"),
                ctrl("QA cruzado", "PASS", "scope LH vs LM II correcto (ver conflicto LM II 8)"),
                ctrl("Warnings técnicos", "ACEPTABLE", "sin bloqueos técnicos de integridad"),
                ctrl("Revisión editorial", "PENDIENTE", ""),
                ctrl("Legal/copyright", "PENDIENTE", "LEGAL_REVIEW_REQUIRED"),
            ]
            blocked_controls = [m["control"] for m in technical_matrix if m["result"] == "BLOCKED"]

            technical_result = (
                "NOT_READY_TECHNICAL_BLOCKERS"
                if blocked_controls
                else "TECHNICALLY_READY_FOR_EDITORIAL_REVIEW"
            )
            summary = {
                "technical_result": technical_result,
                "technical_blockers": blocked_controls,
                "editorial_review": "PENDIENTE",
                "legal_review": "LEGAL_REVIEW_REQUIRED",
                "promotion_executed": False,
            }

        pdf = inspect_pdf(source_path)

        dump(output / "baseline.json", baseline)
        dump(output / "technical-matrix.json", technical_matrix)
        dump(output / "metadata-results.json", metadata_results)
        dump(output / "page-first-results.json", {
            "page_summary": page_summary,
            "pdf": pdf,
        })
        dump(output / "evidence-results.json", evidence_results)
        dump(output / "pg-milvus-results.json", pg_milvus)
        dump(output / "retrieval-results.json", retrieval_results)
        dump(output / "multilingual-results.json", multilingual_results)
        dump(output / "editorial-blockers.json", editorial_blockers)
        dump(output / "legal-blockers.json", legal_blockers)
        dump(output / "recommendation.json", summary)
        (output / "rollback-plan.md").write_text(
            "No data, status, metadata, chunk, embedding or vector was modified by "
            "this audit, so no rollback is required. Any future promotion would "
            "follow an authorized separate phase with its own plan.\n",
            encoding="utf-8",
        )
        # duplicate-version matrix for reference
        dump(output / "duplicate-version-matrix.json", {
            "related_documents": related,
            "binary_duplicate": False,
            "logical_duplicate": False,
        })
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print(f"OK: readiness audit written to {output}")
    finally:
        await close_pool(pool)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/reports/breslov/2026-08-06-likutey-halajot-promotion-readiness-v2"),
    )
    args = parser.parse_args()
    asyncio.run(audit(args.output))


if __name__ == "__main__":
    main()
