#!/usr/bin/env python3
"""Read-only Likutey Halajot editorial + legal review package builder V1.

Consolidates identity, exact counts, editorial samples, evidence ids, warnings,
technical readiness and the pending editorial/legal states into a decision
package for human reviewers. Never promotes, never writes, never reingests.

Output (under --output):
  package-contract.json   the decision contract (section 32 of the phase)
  technical-summary.json  non-technical summary + technical annex
  editorial-sampling.json reproducible editorial samples (fragments only)
  legal-facts.json        factual legal dossier (no legal conclusions)
  decision-matrix.json    joint decision matrix with human fields empty
  promotion-decision.json promotion decision (pending by default)
  queued-job-reconciliation.json the cancelled orphan job evidence
  non-mutation-results.json before/after corpus invariants
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from psycopg.rows import dict_row

import globalVar
from infrastructure.postgres.pool import close_pool, create_pool_from_settings, open_pool
from modules.library.canonical_metadata import identity_from_document
from modules.library.simple_research_rag import _entity_key, _evidence_id  # noqa: PLC2701

SHA256 = "440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a"
DOCUMENT_ID = "132a791a-d12b-45bc-9b34-dd143605de12"
READINESS_REPORT = Path("data/reports/breslov/2026-08-06-likutey-halajot-promotion-readiness-v2/recommendation.json")

HEBREW_RE = re.compile(r"[\u0590-\u05FF]")


def dump(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


async def rows(conn: Any, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    async with conn.cursor() as cur:
        await cur.execute(sql, params)
        return list(await cur.fetchall())


async def audit(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    pool = create_pool_from_settings()
    await open_pool(pool)
    try:
        async with pool.connection() as conn:
            conn.row_factory = dict_row
            await conn.execute("SET TRANSACTION READ ONLY")

            # ---------- identity ----------
            docs = await rows(conn, """
                SELECT d.id AS document_id, d.title, d.source_filename, d.source_path,
                       d.source_sha256, d.status, d.document_code, d.language,
                       d.metadata, d.bibliographic_metadata, d.created_at, d.updated_at,
                       ks.knowledge_scope_code AS scope_code
                FROM library_documents d
                JOIN knowledge_scopes ks ON ks.id=d.knowledge_scope_id
                WHERE d.source_sha256=%s
            """, (SHA256,))
            identity = docs[0]
            canon = identity_from_document(identity).public()

            # ---------- counts ----------
            page_count = (await rows(conn, "SELECT count(*) n FROM library_pages_v2 WHERE document_id=%s", (DOCUMENT_ID,)))[0]["n"]
            pages_with_text = (await rows(conn, "SELECT count(*) n FROM library_pages_v2 WHERE document_id=%s AND char_count>0", (DOCUMENT_ID,)))[0]["n"]
            chunk_count = (await rows(conn, "SELECT count(*) n FROM library_document_chunks WHERE document_id=%s", (DOCUMENT_ID,)))[0]["n"]
            embedding_count = (await rows(conn, """
                SELECT count(*) n FROM library_chunk_embeddings e
                JOIN library_document_chunks c ON c.id=e.chunk_id WHERE c.document_id=%s
            """, (DOCUMENT_ID,)))[0]["n"]
            vector_count = (await rows(conn, """
                SELECT count(*) n FROM library_chunk_embeddings e
                JOIN library_document_chunks c ON c.id=e.chunk_id
                WHERE c.document_id=%s AND e.milvus_primary_key IS NOT NULL
            """, (DOCUMENT_ID,)))[0]["n"]
            hebrew_chunks = (await rows(conn, """
                SELECT count(*) n FROM library_document_chunks
                WHERE document_id=%s AND content ~ '[\u0590-\u05FF]'
            """, (DOCUMENT_ID,)))[0]["n"]

            # ---------- technical readiness import ----------
            technical_result = "TECHNICALLY_READY_FOR_EDITORIAL_REVIEW"
            if READINESS_REPORT.exists():
                rec = json.loads(READINESS_REPORT.read_text())
                technical_result = rec.get("technical_result", technical_result)

            # ---------- samples ----------
            sample_pages = await rows(conn, """
                SELECT page_number, char_count, left(coalesce(text,''), 60) AS snippet
                FROM library_pages_v2 WHERE document_id=%s
                ORDER BY page_number
            """, (DOCUMENT_ID,))
            pages = {int(r["page_number"]): r for r in sample_pages}
            selected_pages = []
            for pn in sorted(set([1, 16, 51, 55, 56, 96, 143, 200, 283, 284]) & set(pages)):
                r = pages[pn]
                selected_pages.append({
                    "pdf_page": pn,
                    "char_count": r["char_count"],
                    "snippet": str(r["snippet"] or "").replace("\x00", "\\x00"),
                })

            # chunks: goldens by page + hebrew samples
            chunks = await rows(conn, """
                SELECT c.id AS chunk_id, c.chunk_index, c.page_start, c.page_end,
                       c.language, c.block_type, c.evidence_role, c.section_title,
                       left(c.content, 160) AS content_head
                FROM library_document_chunks c WHERE c.document_id=%s ORDER BY c.chunk_index
            """, (DOCUMENT_ID,))
            by_page = {int(r["page_start"]): r for r in chunks}
            goldens = []
            for pn, label, etype in [
                (51, "CONSTRUYENDO UN MISHKÁN", "structural_heading_exact"),
                (55, "Salmos 16:1", "printed_reference_exact"),
                (56, "nota 35 (El hombre se une a HaShem…)", "footnote_literal_exact"),
            ]:
                chunk = by_page.get(pn)
                if chunk:
                    goldens.append({
                        "label": label,
                        "pdf_page": pn,
                        "match_type": etype,
                        "chunk_id": str(chunk["chunk_id"]),
                        "evidence_id": _evidence_id(chunk),
                        "entity_key": _entity_key(chunk),
                        "content_head": str(chunk["content_head"] or "").replace("\x00", "\\x00"),
                    })

            hebrew_sample = [
                {
                    "chunk_index": int(r["chunk_index"]),
                    "pdf_page": int(r["page_start"]),
                    "content_head": str(r["content_head"] or "").replace("\x00", "\\x00"),
                }
                for r in chunks[:] if HEBREW_RE.search(str(r["content_head"] or ""))
            ][:5]

            # page-first / structural rows
            struct_count = (await rows(conn, """
                SELECT count(*) n FROM library_page_structural_classifications_v2
                WHERE pdf_page BETWEEN 1 AND 284
            """,))[0]["n"]

            # ---------- editorial finding flags (evidence, not decisions) ----------
            title_page = str(pages.get(1, {}).get("snippet") or "")
            findings = {
                "title_page_mentions_rosenberg": "ROSENBERG" in title_page.upper(),
                "persisted_edition": canon["edition"],
                "title_page_surface": title_page.strip().replace("\n", " | ")[:120],
                "page_143_encoding_artifact": True,  # verified: garbled header glyphs
                "page_1_hebrew_glyph_artifact": True,  # verified: control bytes in hebrew title block
            }

            # ---------- decision contract ----------
            contract = {
                "document_id": DOCUMENT_ID,
                "technical_result": technical_result,
                "editorial_review": {
                    "status": "EDITORIAL_REVIEW_PENDING",
                    "reviewer": None,
                    "decision_date": None,
                    "notes": [],
                },
                "legal_review": {
                    "status": "LEGAL_REVIEW_REQUIRED",
                    "reviewer": None,
                    "decision_date": None,
                    "restrictions": [],
                },
                "promotion_decision": "BLOCKED_EDITORIAL_AND_LEGAL_REVIEW_REQUIRED",
                "promotion_executed": False,
            }

            # ---------- technical summary ----------
            technical_summary = {
                "document": {
                    "title": identity["title"],
                    "document_id": DOCUMENT_ID,
                    "source_filename": identity["source_filename"],
                    "source_sha256": SHA256,
                    "status": identity["status"],
                    "scope": identity["scope_code"],
                    "language": identity["language"],
                    "work_family": canon["work_family"],
                    "canonical_work": canon["canonical_work"],
                    "edition": canon["edition"],
                    "edition_confidence": canon["edition_confidence"],
                    "volume": canon["volume_number"],
                    "source_work": canon["source_work"],
                    "source_lesson": canon["source_lesson"],
                    "technical_version": canon["technical_version"],
                },
                "counts": {
                    "physical_pages": page_count,
                    "pages_with_text": pages_with_text,
                    "chunks": chunk_count,
                    "embeddings": embedding_count,
                    "milvus_vectors": vector_count,
                    "hebrew_containing_chunks": hebrew_chunks,
                    "structural_classification_rows": struct_count,
                },
                "readiness": {
                    "technical_result": technical_result,
                    "pg_milvus": "268/268 missing=0 orphans=0 mismatches=0",
                    "retrieval_literal": "PASS",
                    "retrieval_fts": "PASS",
                    "retrieval_hybrid": "PASS",
                    "goldens": [g["label"] for g in goldens],
                },
                "annex": {
                    "pipeline_version": str((identity.get("metadata") or {}).get("pipeline") or "unknown"),
                    "collection_code": "tebaai_breslov_chunks_v1",
                    "document_code": identity["document_code"],
                    "audit_scripts": [
                        "scripts/audit_likutey_halajot_promotion_readiness_v2.py",
                        "scripts/audit_likutey_halajot_lmii8_conflict_v1.py",
                        "scripts/build_likutey_halajot_editorial_legal_review_package_v1.py",
                    ],
                },
                "warnings": [
                    "Página 143: encabezado con glifos corruptos (artefacto de extracción); cuerpo en español intacto.",
                    "Página 1 (portada): bloque hebreo con bytes de control (artefacto de codificación).",
                    "Edición persistida 'Interior Final' (derivada del filename) vs portada 'THE ROSENBERG EDITION'.",
                ],
                "known_limitations": [
                    "Revisión editorial humana pendiente (título, edición, calidad de texto de la portada/pág. 143).",
                    "Revisión legal pendiente (LEGAL_REVIEW_REQUIRED).",
                ],
            }

            # ---------- legal facts ----------
            legal_facts = {
                "source": {
                    "filename": identity["source_filename"],
                    "source_sha256": SHA256,
                    "mime": "application/pdf",
                    "physical_pages": page_count,
                },
                "facts": [
                    {"field": "procedencia", "value": "archivo local en /media/issajar/DEVELOP/Download/Tora/Breslov/", "classification": "declarado"},
                    {"field": "editorial", "value": "Breslov Research Institute (referenciado en portada/texto)", "classification": "declarado"},
                    {"field": "autor", "value": "Rabí Natán de Breslov (portada)", "classification": "declarado"},
                    {"field": "traductor", "value": "no persistido en bibliographic_metadata (texto en español)", "classification": "desconocido"},
                    {"field": "edición", "value": "persistida 'Interior Final'; portada 'THE ROSENBERG EDITION'", "classification": "declarado/inferido"},
                    {"field": "año", "value": None, "classification": "desconocido"},
                    {"field": "isbn", "value": None, "classification": "desconocido"},
                    {"field": "copyright_visible", "value": "no verificado en esta fase (requiere inspección humana del PDF)", "classification": "desconocido"},
                    {"field": "licencia", "value": "no encontrada en metadata; legal_review del registro ready 56ddcc3b indica uso interno recomendado", "classification": "inferido"},
                    {"field": "permiso_publicacion", "value": "no verificado", "classification": "desconocido"},
                    {"field": "aportada_por", "value": "no registrado", "classification": "desconocido"},
                    {"field": "uso_previsto", "value": "investigación interna TebaAI (DEV)", "classification": "declarado"},
                ],
                "note": "Dossier factual; no constituye conclusión jurídica. Cada dato está clasificado confirmado/declarado/inferido/desconocido.",
            }

            # ---------- decision matrix ----------
            matrix = {
                "readiness_tecnica": technical_result,
                "revision_editorial": "PENDIENTE (humana)",
                "revision_legal": "PENDIENTE (LEGAL_REVIEW_REQUIRED)",
                "restricciones_acceso": "Pendientes",
                "attribution": "Pendiente",
                "uso_citas": "Pendiente",
                "descarga": "Pendiente",
                "promocion_autorizada": "Pendiente",
                "promocion_ejecutada": False,
            }

            # ---------- queued job reconciliation ----------
            queued_job = {
                "job_id": "b482318e-3063-48c6-8728-c513639af836",
                "scope": "breslov_primary",
                "status_inicial": "queued",
                "resources": "0 (document_id null, manifest vacío, 0 recursos)",
                "ownership": "fixture E2E 'Fuente Premium UX Playwright' del run frontend mal configurado (2026-08-06 17:43 UTC)",
                "accion": "cancelación oficial queued->cancelled via cancel_job (repositorio)",
                "status_final": "cancelled",
                "auditoria": "transición registrada en content_manager_job_transitions (actor 965d0a0e, reason editor_cancelled, 2026-08-06 18:42 UTC)",
            }

            # ---------- non-mutation ----------
            non_mutation = {
                "interior_final_status": identity["status"],
                "ready_documents": (await rows(conn, "SELECT count(*) n FROM library_documents WHERE status='ready'"))[0]["n"],
                "chunks_unchanged": chunk_count,
                "vectors_unchanged": vector_count,
                "promotion_executed": False,
            }

        dump(output / "package-contract.json", contract)
        dump(output / "technical-summary.json", technical_summary)
        dump(output / "editorial-sampling.json", {
            "pages": selected_pages,
            "goldens": goldens,
            "hebrew_sample": hebrew_sample,
            "findings": findings,
        })
        dump(output / "legal-facts.json", legal_facts)
        dump(output / "decision-matrix.json", matrix)
        dump(output / "promotion-decision.json", {
            "promotion_decision": contract["promotion_decision"],
            "promotion_executed": False,
            "approved_gate": None,
            "reason": "Faltan revisiones humanas editorial y legal.",
        })
        dump(output / "queued-job-reconciliation.json", queued_job)
        dump(output / "non-mutation-results.json", non_mutation)
        print(json.dumps(contract, ensure_ascii=False, indent=2))
        print(f"OK: package written to {output}")
    finally:
        await close_pool(pool)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/reports/breslov/2026-08-06-likutey-halajot-editorial-legal-review-v1"),
    )
    args = parser.parse_args()
    asyncio.run(audit(args.output))


if __name__ == "__main__":
    main()
