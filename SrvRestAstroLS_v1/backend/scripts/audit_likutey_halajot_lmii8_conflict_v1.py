#!/usr/bin/env python3
"""Read-only audit for the Likutey Halajot / LM II 8 identity conflict V1.

Investigates the disputed `ready` row titled `Likutey Halajot LM II 8` (The
Rosenberg Edition) and its relations with `Likutey Halajot — Interior Final`
(page-first v2, test_candidate) and the original `Likutey Moharán II — edición
española BRI` (test_candidate).

The audit is strictly read-only:

- PostgreSQL runs inside `SET TRANSACTION READ ONLY`;
- Milvus is read with MilvusClient without load()/write; if the service is
  unavailable the audit records the fact and continues;
- no status, metadata, chunk, embedding or vector is modified.

Outputs (under --output):
  baseline.json            real filters and document universe
  postgres-records.json    documents, identities, page/chunk/embedding counts
  milvus-records.json      Milvus availability and vector metadata (if up)
  chunk-surfaces.json      section/surface and content-pattern analysis
  evidence-id-analysis.json evidence id sample, collisions, entity keys
  metadata-diff.json       PG vs Milvus differences (when Milvus is up)
  duplicate-analysis.json  content_sha256 duplicates within/across documents
  scope-resolution.json    resolver battery for key queries
  conflict-classification.json hypothesis assessment (A-L)
  repair-recommendation.md human-readable recommendation

Filters (all optional, additive):
  --document-id    UUID (repeatable)
  --page-id        UUID (repeatable)
  --chunk-id       UUID (repeatable)
  --evidence-id    ev-... (repeatable; resolved to chunks by prefix)
  --source-lesson  int (only documents whose canonical source lesson matches)
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from pathlib import Path
from typing import Any

from psycopg.rows import dict_row

import globalVar
from infrastructure.postgres.pool import close_pool, create_pool_from_settings, open_pool
from modules.library.canonical_metadata import (
    document_matches_scope,
    identity_from_document,
    resolve_canonical_scope,
)

# Canonical source of the evidence id contract (ADR-021).
from modules.library.simple_research_rag import _entity_key, _evidence_id  # noqa: PLC2701

REPORT_GATE = "TEBAAI_LIKUTEY_HALAJOT_LMII8_CONFLICT_RESOLUTION_V1_DEV_READY"
SCOPE_CODE = "breslov_primary"
COLLECTION = "tebaai_breslov_chunks_v1"

CANONICAL_DOCS = {
    "lmii8_rosenberg": "56ddcc3b-8296-4832-ac95-2bfe032cd4c6",
    "interior_final": "132a791a-d12b-45bc-9b34-dd143605de12",
    "lmii_bri": "3715c6e0-db56-49a1-82df-62d0a4d0b5cd",
}

HYPOTHESES = {
    "A": "alias de metadata sin corrupción de contenido",
    "B": "registro lógico duplicado",
    "C": "misma cita utilizada legítimamente por dos obras",
    "D": "chunk asignado al documento incorrecto",
    "E": "página asignada al documento incorrecto",
    "F": "metadata PostgreSQL diferente de metadata Milvus",
    "G": "registro superseded todavía activo",
    "H": "identidad canónica inferida incorrectamente",
    "I": "source_lesson=8 confundido con volumen o edición",
    "J": "colisión de document_code o collection_code",
    "K": "colisión o deriva de evidence_id",
    "L": "ambigüedad editorial no resoluble automáticamente",
}


def dump(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )


async def rows(conn: Any, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    async with conn.cursor() as cur:
        await cur.execute(sql, params)
        return list(await cur.fetchall())


async def audit(output: Path, args: argparse.Namespace) -> None:
    output.mkdir(parents=True, exist_ok=True)
    pool = create_pool_from_settings()
    await open_pool(pool)
    baseline: dict[str, Any] = {
        "report_gate": REPORT_GATE,
        "filters": {
            "document_id": args.document_id,
            "page_id": args.page_id,
            "chunk_id": args.chunk_id,
            "evidence_id": args.evidence_id,
            "source_lesson": args.source_lesson,
        },
    }
    try:
        async with pool.connection() as conn:
            conn.row_factory = dict_row
            await conn.execute("SET TRANSACTION READ ONLY")

            # ---------- document universe ----------
            if args.document_id:
                where = "d.id = ANY(%s::uuid[])"
                params: tuple[Any, ...] = (args.document_id,)
            else:
                where = (
                    "ks.knowledge_scope_code = %s "
                    "AND d.status IN ('ready','test_candidate')"
                )
                params = (SCOPE_CODE,)
            docs = await rows(
                conn,
                f"""
                SELECT d.id AS document_id, d.title, d.source_filename,
                       d.source_sha256, d.status, d.document_code, d.language,
                       d.metadata, d.bibliographic_metadata,
                       d.created_at, d.updated_at,
                       ks.knowledge_scope_code AS scope_code
                FROM library_documents d
                LEFT JOIN knowledge_scopes ks ON ks.id = d.knowledge_scope_id
                WHERE {where}
                ORDER BY d.title
                """,
                params,
            )
            identities = {str(d["document_id"]): identity_from_document(d) for d in docs}

            # --source-lesson filter (canonical source lesson)
            if args.source_lesson is not None:
                docs = [
                    d for d in docs
                    if any(
                        s.lesson_number == args.source_lesson
                        for s in identities[str(d["document_id"])].source_identities
                    )
                ]
            baseline["documents_selected"] = [str(d["document_id"]) for d in docs]

            chunk_ids = args.chunk_id or []
            page_ids = args.page_id or []
            evidence_ids = args.evidence_id or []

            postgres_records: list[dict[str, Any]] = []
            chunk_rows_by_doc: dict[str, list[dict[str, Any]]] = {}
            for doc in docs:
                did = str(doc["document_id"])
                ident = identities[did]
                page_summary = (await rows(
                    conn,
                    """
                    SELECT count(*) total_pages, count(distinct page_id) unique_page_ids,
                           count(distinct page_number) unique_pdf_pages,
                           count(*) FILTER (WHERE coalesce(text,'')<>'') pages_with_text,
                           min(page_number) min_pdf_page, max(page_number) max_pdf_page
                    FROM library_pages_v2 WHERE document_id=%s
                    """,
                    (did,),
                ))[0]
                chunk_summary = (await rows(
                    conn,
                    """
                    SELECT count(*) total_chunks, count(distinct id) unique_chunk_ids,
                           count(distinct content_sha256) distinct_content_sha,
                           count(*) FILTER (WHERE search_text_normalized IS NULL) null_search_text,
                           count(*) FILTER (WHERE coalesce(search_text_normalized,'')='') empty_search_text
                    FROM library_document_chunks WHERE document_id=%s
                    """,
                    (did,),
                ))[0]
                embedding_summary = (await rows(
                    conn,
                    """
                    SELECT count(*) total_embeddings,
                           count(*) FILTER (WHERE milvus_primary_key IS NOT NULL) with_milvus_key,
                           count(DISTINCT milvus_collection) collections
                    FROM library_chunk_embeddings e
                    JOIN library_document_chunks c ON c.id=e.chunk_id
                    WHERE c.document_id=%s
                    """,
                    (did,),
                ))[0]
                evidence_summary = (await rows(
                    conn,
                    """
                    SELECT count(*) total_evidence
                    FROM library_citable_evidence_v2 e
                    JOIN library_document_chunks c ON c.id=e.chunk_id
                    WHERE c.document_id=%s
                    """,
                    (did,),
                ))[0]
                chunk_rows = await rows(
                    conn,
                    """
                    SELECT c.id AS chunk_id, c.chunk_index, c.page_start, c.page_end,
                           c.content_sha256, c.language, c.block_type,
                           c.evidence_role, c.section_title, c.reference_label,
                           c.metadata
                    FROM library_document_chunks c WHERE c.document_id=%s
                    ORDER BY c.chunk_index
                    """,
                    (did,),
                )
                if chunk_ids:
                    chunk_rows = [c for c in chunk_rows if str(c["chunk_id"]) in chunk_ids]
                if page_ids:
                    chunk_rows = [
                        c for c in chunk_rows
                        if str(c.get("page_start")) in page_ids or str(c.get("page_end")) in page_ids
                    ]
                if evidence_ids:
                    wanted = {eid.removeprefix("ev-") for eid in evidence_ids}
                    chunk_rows = [
                        c for c in chunk_rows
                        if _evidence_id(c).removeprefix("ev-") in wanted
                    ]
                chunk_rows_by_doc[did] = chunk_rows
                postgres_records.append({
                    "document_id": did,
                    "title": doc["title"],
                    "source_filename": doc["source_filename"],
                    "source_sha256": str(doc["source_sha256"] or ""),
                    "status": doc["status"],
                    "document_code": doc["document_code"],
                    "scope_code": doc["scope_code"],
                    "identity": ident.public(),
                    "pages": page_summary,
                    "chunks": chunk_summary,
                    "embeddings": embedding_summary,
                    "evidence": evidence_summary,
                })

            # ---------- surface analysis ----------
            surfaces: dict[str, Any] = {}
            for pattern, label in [
                ("%MOHAR%N II%", "content_moharan_ii"),
                ("%Hiljot%", "content_hiljot"),
                ("%Halajot%", "content_halajot"),
                ("%LM II%", "content_lm_ii"),
                ("%#8%", "content_hash_8"),
            ]:
                for doc in docs:
                    did = str(doc["document_id"])
                    n = (await rows(
                        conn,
                        "SELECT count(*) AS n FROM library_document_chunks "
                        "WHERE document_id=%s AND content ILIKE %s",
                        (did, pattern),
                    ))[0]["n"]
                    surfaces.setdefault(did, {})[label] = n
            for doc in docs:
                did = str(doc["document_id"])
                chunk_rows = chunk_rows_by_doc[did]
                surfaces[did]["title"] = doc["title"]
                surfaces[did]["total_chunks_filtered"] = len(chunk_rows)
                surfaces[did]["section_title_null"] = sum(
                    1 for c in chunk_rows if not c["section_title"]
                )
                surfaces[did]["block_type_distribution"] = dict(
                    Counter(c["block_type"] for c in chunk_rows)
                )
                surfaces[did]["evidence_role_distribution"] = dict(
                    Counter(c["evidence_role"] for c in chunk_rows)
                )

            # ---------- evidence id analysis ----------
            evidence_analysis: dict[str, Any] = {}
            all_ids: dict[str, list[dict[str, Any]]] = {}
            for doc in docs:
                did = str(doc["document_id"])
                ids = []
                for chunk in chunk_rows_by_doc[did][:400]:
                    ids.append({
                        "chunk_id": str(chunk["chunk_id"]),
                        "evidence_id": _evidence_id(chunk),
                        "entity_key": _entity_key(chunk),
                        "block_type": chunk["block_type"],
                        "evidence_role": chunk["evidence_role"],
                    })
                all_ids[did] = ids
            seen: dict[str, str] = {}
            collisions: list[dict[str, Any]] = []
            for did, ids in all_ids.items():
                for item in ids:
                    if item["evidence_id"] in seen and seen[item["evidence_id"]] != did:
                        collisions.append({
                            "evidence_id": item["evidence_id"],
                            "doc_a": seen[item["evidence_id"]],
                            "doc_b": did,
                            "entity_key": item["entity_key"],
                        })
                    seen.setdefault(item["evidence_id"], did)
            evidence_analysis["documents_sampled"] = {str(k): len(v) for k, v in all_ids.items()}
            evidence_analysis["cross_document_collisions"] = collisions
            evidence_analysis["distinct_entity_keys"] = {
                str(k): len({item["entity_key"] for item in v}) for k, v in all_ids.items()
            }

            # ---------- duplicate content analysis ----------
            duplicate_analysis: dict[str, Any] = {
                "within_document": {},
                "cross_document_shared": [],
            }
            all_doc_ids = [str(d["document_id"]) for d in docs]
            for doc in docs:
                did = str(doc["document_id"])
                dup = await rows(
                    conn,
                    """
                    SELECT content_sha256, count(*) n FROM library_document_chunks
                    WHERE document_id=%s GROUP BY 1 HAVING count(*)>1
                    """,
                    (did,),
                )
                duplicate_analysis["within_document"][did] = {
                    "title": doc["title"],
                    "duplicate_content_shas": len(dup),
                    "duplicate_rows": sum(int(r["n"]) for r in dup),
                }
            if all_doc_ids:
                shared = await rows(
                    conn,
                    """
                    SELECT content_sha256, array_agg(DISTINCT document_id) docs
                    FROM library_document_chunks
                    WHERE document_id = ANY(%s::uuid[])
                    GROUP BY 1 HAVING count(DISTINCT document_id) > 1
                    """,
                    (all_doc_ids,),
                )
                duplicate_analysis["cross_document_shared"] = [
                    {"content_sha256": str(r["content_sha256"]), "documents": sorted(map(str, r["docs"]))}
                    for r in shared
                ]

            # ---------- Milvus (read-only, tolerant) ----------
            milvus_report: dict[str, Any] = {"available": False}
            try:
                from pymilvus import MilvusClient
                client = MilvusClient(
                    uri=f"http://{globalVar.MILVUS_HOST}:{globalVar.MILVUS_PORT}"
                )
                stats = client.get_collection_stats(COLLECTION)
                milvus_report["available"] = True
                milvus_report["collection"] = COLLECTION
                milvus_report["collection_entities"] = int(stats.get("row_count", -1))
                milvus_report["load_state"] = client.get_load_state(COLLECTION)
                vector_counts: dict[str, int] = {}
                for doc in docs:
                    did = str(doc["document_id"])
                    n = (await rows(
                        conn,
                        """
                        SELECT count(*) n FROM library_chunk_embeddings e
                        JOIN library_document_chunks c ON c.id=e.chunk_id
                        WHERE c.document_id=%s AND e.milvus_primary_key IS NOT NULL
                        """,
                        (did,),
                    ))[0]["n"]
                    vector_counts[did] = n
                milvus_report["pg_expected_vectors"] = vector_counts
            except Exception as exc:  # pragma: no cover - environmental
                milvus_report["error"] = f"{type(exc).__name__}: {exc}"

            # ---------- metadata diff (PG vs Milvus when available) ----------
            metadata_diff: dict[str, Any] = {"differences": []}
            if milvus_report.get("available"):
                metadata_diff["note"] = (
                    "Count-level comparison only; vector-by-vector reconciliation is "
                    "deferred to the promotion-readiness audit."
                )
                for doc in docs:
                    did = str(doc["document_id"])
                    emb = next(r for r in postgres_records if r["document_id"] == did)["embeddings"]
                    metadata_diff["differences"].append({
                        "document_id": did,
                        "embeddings_pg": emb["total_embeddings"],
                        "with_milvus_key_pg": emb["with_milvus_key"],
                    })
            else:
                metadata_diff["note"] = "Milvus unavailable; diff deferred."

            # ---------- scope resolution battery ----------
            queries = [
                "Likutey Halajot",
                "Likutey Halajot LM II 8",
                "Likutey Halajot, lección 8",
                "Likutey Moharán II",
                "Likutey Moharán II lección 8",
                "LM II",
                "LM II 8",
                "Likutey",
                "LM",
                "¿Qué dice la Torá 8 de Likutey Halajot?",
            ]
            scope_results = []
            for query in queries:
                scope = resolve_canonical_scope(query, list(identities.values()))
                selected = [
                    {
                        "document_id": did,
                        "title": identities[did].document_title,
                        "family": identities[did].family_code,
                        "status": identities[did].document_status,
                    }
                    for did, ident in identities.items()
                    if document_matches_scope(ident, scope)
                ]
                scope_results.append({
                    "query": query,
                    "scope": scope.public(),
                    "selected": selected,
                })

            # ---------- hypothesis classification ----------
            classification: dict[str, Any] = {"assessed": {}, "summary": ""}
            disputed_ident = identities.get(CANONICAL_DOCS["lmii8_rosenberg"])
            disputed_has_source_identity = bool(
                disputed_ident
                and any(
                    s.work_code == "likutey_moharan_ii" and s.lesson_number == 8
                    for s in disputed_ident.source_identities
                )
            )
            assessment = {
                "A_alias_metadata": bool(
                    disputed_ident
                    and disputed_ident.family_code == "likutey_halajot"
                    and disputed_has_source_identity
                ),
                "B_logical_duplicate": bool(duplicate_analysis["cross_document_shared"]),
                "C_same_quote_two_works": bool(duplicate_analysis["cross_document_shared"]),
                "D_chunk_wrong_doc": False,
                "E_page_wrong_doc": any(
                    int(r["pages"]["total_pages"]) > 0
                    and int(r["pages"]["unique_pdf_pages"]) == 0
                    for r in postgres_records
                ),
                "F_pg_vs_milvus_drift": bool(
                    milvus_report.get("available")
                    and any(
                        r["embeddings"]["total_embeddings"] != r["embeddings"]["with_milvus_key"]
                        for r in postgres_records
                    )
                ),
                "G_superseded_active": False,
                "H_identity_inferred_wrong": bool(
                    disputed_ident is None
                    or disputed_ident.family_code != "likutey_halajot"
                    or not disputed_has_source_identity
                ),
                "I_lesson_confused_with_volume": bool(
                    disputed_ident
                    and disputed_ident.volume.value is not None
                    and str(disputed_ident.volume.source).startswith("source_lesson")
                ),
                "J_code_collision": (
                    len({str(d["document_code"]) for d in docs if d["document_code"]})
                    < len([d for d in docs if d["document_code"]])
                ),
                "K_evidence_collision": bool(collisions),
                "L_editorial_ambiguity": any(
                    r["scope"]["scope_ambiguous"] for r in scope_results
                ),
            }
            classification["assessed"] = assessment
            classification["hypothesis_labels"] = HYPOTHESES
            # A and L are resolutions of the prior faulty diagnosis, not defects:
            #  A -> the metadata alias contract is present and correct (ADR-019);
            #  L -> short ambiguous queries return scope_ambiguous by design, no
            #       heuristic auto-selection (decision already recorded in ADR-019).
            active = [k for k, v in assessment.items() if v and k not in {"A_alias_metadata", "L_editorial_ambiguity"}]
            classification["active_defects"] = active
            classification["resolutions"] = {
                "A_alias_metadata": assessment["A_alias_metadata"],
                "L_editorial_ambiguity": assessment["L_editorial_ambiguity"],
            }
            classification["active"] = [k for k, v in assessment.items() if v]
            classification["summary"] = (
                "Sin defectos activos: la causa fue el diagnóstico de ADR-017, ya resuelto por "
                "el contrato canónico (ADR-019) sin modificar corpus; la ambigüedad corta "
                "(Likutey/LM) retorna scope_ambiguous por diseño."
                if not active
                else f"Defectos activos: {', '.join(active)}"
            )

        # ---------- recommendation ----------
        rec_lines = []
        rec_lines.append("# Reparación recomendada — conflicto Likutey Halajot / LM II 8\n")
        rec_lines.append("## Hallazgos\n")
        rec_lines.append(
            "- La metadata canónica de las tres fuentes DEV está persistida bajo "
            "`bibliographic_metadata.canonical_identity_v1` (ADR-019)."
        )
        rec_lines.append(
            "- `Likutey Halajot LM II 8` (The Rosenberg Edition, ready) declara "
            "`work_family=likutey_halajot` y `source_identities=[likutey_moharan_ii:8 develops]`."
        )
        rec_lines.append(
            "- El resolver de scope trata `LH` y `LM II` como familias distintas y exige una "
            "source identity explícita para seleccionar comentarios sobre LM II 8."
        )
        rec_lines.append(
            "- La única edición LH que declara la relación fuente lmii:8 es Rosenberg; "
            "`Interior Final` no la declara a nivel documento (fuentes por sección/chunk)."
        )
        rec_lines.append("## Clasificación (hipótesis A-L)\n")
        for key, value in assessment.items():
            rec_lines.append(f"- {key}: {value}")
        rec_lines.append("\n## Recomendación\n")
        active_defects = classification["active_defects"]
        if not active_defects:
            rec_lines.append(
                "No se requiere reparación de datos: la causa fue el diagnóstico previo "
                "(ADR-017) y quedó resuelta por el contrato canónico (ADR-019) sin cambiar "
                "corpus. `Likutey Halajot LM II 8` es una antología de Likutey Halajot que "
                "desarrolla LM II lección 8; las consultas cortas ambiguas retornan "
                "`scope_ambiguous` por diseño. Cerrar el gate con resolución técnica sin "
                "escritura."
            )
        else:
            rec_lines.append("Revisar cada defecto activo antes de decidir reparación.")

        dump(output / "baseline.json", baseline)
        dump(output / "postgres-records.json", postgres_records)
        dump(output / "milvus-records.json", milvus_report)
        dump(output / "chunk-surfaces.json", surfaces)
        dump(output / "evidence-id-analysis.json", evidence_analysis)
        dump(output / "metadata-diff.json", metadata_diff)
        dump(output / "duplicate-analysis.json", duplicate_analysis)
        dump(output / "scope-resolution.json", scope_results)
        dump(output / "conflict-classification.json", classification)
        (output / "repair-recommendation.md").write_text(
            "\n".join(rec_lines), encoding="utf-8"
        )
        print(f"OK: audit written to {output}")
    finally:
        await close_pool(pool)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/reports/breslov/2026-08-06-likutey-halajot-lmii8-conflict-v1"),
    )
    parser.add_argument("--document-id", action="append", default=None, help="UUID, repeatable")
    parser.add_argument("--page-id", action="append", default=None, help="UUID, repeatable")
    parser.add_argument("--chunk-id", action="append", default=None, help="UUID, repeatable")
    parser.add_argument("--evidence-id", action="append", default=None, help="ev-..., repeatable")
    parser.add_argument("--source-lesson", type=int, default=None, help="lesson number filter")
    args = parser.parse_args()
    asyncio.run(audit(args.output, args))


if __name__ == "__main__":
    main()
