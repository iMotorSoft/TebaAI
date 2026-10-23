#!/usr/bin/env python3
"""V1R2 reader/lifecycle harness against real DEV PostgreSQL.

Synthetic OLD (ACTIVE) + NEW (CANDIDATE) generations of one logical document.
Exercises text, hybrid, research, relation QA, viewer, citation/source,
CUTOVER, ROLLBACK, stale CAS, idempotency, audit, cleanup protection and
CAS atomicity. Nothing touches C, Milvus persistence, extraction or embeddings.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

BACKEND = Path(__file__).resolve().parents[4] / "SrvRestAstroLS_v1" / "backend"
sys.path.insert(0, str(BACKEND))

from psycopg import AsyncConnection  # noqa: E402
from psycopg.rows import dict_row  # noqa: E402

import globalVar as g  # noqa: E402
from modules.library import generation as gen  # noqa: E402
from modules.library import hybrid_search  # noqa: E402
from modules.library import simple_research_repository as research  # noqa: E402
from modules.library.errors import ScopeAccessDeniedError  # noqa: E402
from modules.library.relation_qa_repository import search_fts_chunks  # noqa: E402
from modules.library.source_repository import (  # noqa: E402
    get_authorized_source,
    get_page_publication,
)
from modules.library.text_search import search_chunks_text  # noqa: E402
from tests.test_generation_foundation import (  # noqa: E402
    COLLECTION_CODE,
    NEW_MARKER,
    OLD_MARKER,
    SCOPE_CODE,
    _create_synthetic,
    _destroy_synthetic,
)

OUT = Path(__file__).resolve().parent


@asynccontextmanager
async def connection():
    conn = await AsyncConnection.connect(g.POSTGRES_DSN, row_factory=dict_row,
                                         connect_timeout=5)
    try:
        yield conn
    finally:
        await conn.close()


async def fetchone(conn, sql: str, params=None):
    async with conn.cursor() as cur:
        await cur.execute(sql, params)
        return await cur.fetchone()


async def fetchall(conn, sql: str, params=None):
    async with conn.cursor() as cur:
        await cur.execute(sql, params)
        return await cur.fetchall()


async def run(conn, sql: str, params=None) -> int:
    async with conn.cursor() as cur:
        await cur.execute(sql, params)
        return cur.rowcount


async def user_with_breslov_membership(conn) -> UUID:
    row = await fetchone(
        conn,
        """
        SELECT u.id
        FROM users u
        JOIN organization_members om ON om.user_id=u.id AND om.status='active'
        JOIN workspace_members wm ON wm.user_id=u.id AND wm.status='active'
        JOIN project_members pm ON pm.user_id=u.id AND pm.status='active'
        JOIN knowledge_scopes ks
          ON ks.organization_id=om.organization_id
         AND ks.workspace_id=wm.workspace_id
         AND ks.project_id=pm.project_id
        WHERE u.is_active=true AND ks.knowledge_scope_code='breslov_primary'
        LIMIT 1
        """,
    )
    if not row:
        raise RuntimeError("no active user with complete membership chain")
    return row["id"]


async def purge_synthetic(conn) -> None:
    """Remove only the known synthetic fixture scope/collection leftovers."""
    async with conn.transaction():
        await run(conn, """
            DELETE FROM library_generation_activation_audit
            WHERE logical_document_id IN (
                SELECT id FROM library_logical_documents WHERE knowledge_scope_id IN
                (SELECT id FROM knowledge_scopes WHERE knowledge_scope_code=%s))
        """, (SCOPE_CODE,))
        await run(conn, """
            DELETE FROM library_logical_document_active_generations
            WHERE logical_document_id IN (
                SELECT id FROM library_logical_documents WHERE knowledge_scope_id IN
                (SELECT id FROM knowledge_scopes WHERE knowledge_scope_code=%s))
        """, (SCOPE_CODE,))
        await run(conn, """
            DELETE FROM library_document_generations
            WHERE logical_document_id IN (
                SELECT id FROM library_logical_documents WHERE knowledge_scope_id IN
                (SELECT id FROM knowledge_scopes WHERE knowledge_scope_code=%s))
        """, (SCOPE_CODE,))
        await run(conn, """
            UPDATE library_documents SET logical_document_id=NULL
            WHERE knowledge_scope_id IN (SELECT id FROM knowledge_scopes WHERE knowledge_scope_code=%s)
        """, (SCOPE_CODE,))
        doc_ids = [str(r["id"]) for r in await fetchall(
            conn, """SELECT id FROM library_documents WHERE knowledge_scope_id IN
                     (SELECT id FROM knowledge_scopes WHERE knowledge_scope_code=%s)""",
            (SCOPE_CODE,))]
        for doc in doc_ids:
            for table in ("library_document_chunks", "library_pages_v2",
                          "library_document_texts", "library_ingestion_runs_v2"):
                await run(conn, f"DELETE FROM {table} WHERE document_id=%s", (doc,))
            await run(conn, "DELETE FROM library_documents WHERE id=%s", (doc,))
        await run(conn, """
            DELETE FROM library_logical_documents WHERE knowledge_scope_id IN
            (SELECT id FROM knowledge_scopes WHERE knowledge_scope_code=%s)
        """, (SCOPE_CODE,))
        await run(conn, "DELETE FROM library_collections_legacy WHERE code=%s", (COLLECTION_CODE,))
        await run(conn, "DELETE FROM knowledge_scopes WHERE knowledge_scope_code=%s", (SCOPE_CODE,))


def ids(rows, key="document_id"):
    return [str(row[key]) for row in rows]


async def chunk_ids(conn, fx) -> tuple[str, str]:
    old = await fetchone(conn, "SELECT id FROM library_document_chunks WHERE document_id=%s", (fx.old_document_id,))
    new = await fetchone(conn, "SELECT id FROM library_document_chunks WHERE document_id=%s", (fx.new_document_id,))
    return str(old["id"]), str(new["id"])


async def text_visibility(conn, fx, marker: str):
    rows = await search_chunks_text(conn, SCOPE_CODE, marker, top_k=5, mode="phrase")
    return {"marker": marker, "documents": ids(rows), "count": len(rows)}


async def fake_vector_hits(old_chunk: str, new_chunk: str, fx):
    return [
        {"chunk_id": old_chunk, "document_id": str(fx.old_document_id), "distance": 0.91,
         "chunk_index": 0, "page_start": 1, "page_end": 1},
        {"chunk_id": new_chunk, "document_id": str(fx.new_document_id), "distance": 0.92,
         "chunk_index": 0, "page_start": 1, "page_end": 1},
    ]


async def hybrid_visibility(conn, fx, old_chunk: str, new_chunk: str):
    calls: dict = {}
    hits = await fake_vector_hits(old_chunk, new_chunk, fx)

    def fake_search_vectors(*, collection_name, query_embedding, top_k, expr=None, output_fields=None):
        calls["expr"] = expr
        return hits

    with patch.object(hybrid_search, "embed_text", lambda _q: [0.0] * 1536), \
         patch.object(hybrid_search, "ensure_collection", lambda *a, **k: None), \
         patch.object(hybrid_search, "search_vectors", fake_search_vectors), \
         patch("infrastructure.milvus.client.create_connection", lambda *a, **k: None):
        rows = await hybrid_search.search_chunks_hybrid(
            conn, SCOPE_CODE, "visible-marker", top_k=5,
        )
    return {
        "vector_lane_returned": len(hits),
        "milvus_expr": calls.get("expr"),
        "result_documents": ids(rows),
        "result_chunk_ids": [str(row["chunk_id"]) for row in rows],
        "vector_signal_present": any(
            "vector" in (row.get("source_signals") or []) for row in rows
        ),
    }


async def documents_for_chunks(conn, chunk_ids):
    if not chunk_ids:
        return []
    rows = await fetchall(
        conn,
        "SELECT id::text AS chunk_id, document_id::text AS document_id FROM library_document_chunks WHERE id = ANY(%s::uuid[])",
        ([str(item) for item in chunk_ids],),
    )
    mapping = {row["chunk_id"]: row["document_id"] for row in rows}
    seen = []
    for chunk_id in chunk_ids:
        doc = mapping.get(str(chunk_id))
        if doc and doc not in seen:
            seen.append(doc)
    return seen


async def research_visibility(conn, fx, marker: str):
    ready = await research.resolve_ready_documents(conn, knowledge_scope_code=SCOPE_CODE)
    normal = await research.search_literal_candidates(
        conn, knowledge_scope_code=SCOPE_CODE, variants=[marker],
        languages=["es"], document_ids=None, top_k=5,
        include_test_candidates=True,
    )
    explicit = await research.search_literal_candidates(
        conn, knowledge_scope_code=SCOPE_CODE, variants=[marker],
        languages=["es"], document_ids=None, top_k=5,
        include_test_candidates=True,
        candidate_document_ids=[str(fx.new_document_id)],
    )
    return {
        "ready_document_ids": ids(ready),
        "flag_alone_document_ids": await documents_for_chunks(
            conn, [row["chunk_id"] for row in normal]),
        "explicit_candidate_document_ids": await documents_for_chunks(
            conn, [row["chunk_id"] for row in explicit]),
        "flag_alone_chunk_ids": [str(row["chunk_id"]) for row in normal],
        "explicit_candidate_chunk_ids": [str(row["chunk_id"]) for row in explicit],
    }


async def relation_visibility(conn, fx, marker: str):
    rows = await search_fts_chunks(
        conn, knowledge_scope_id=fx.scope_id, variants=[marker],
        language="es", include_test_candidates=True, limit=5,
    )
    return {"documents": ids(rows), "count": len(rows)}


async def viewer_visibility(conn, fx):
    old_pub = await get_page_publication(conn, fx.old_document_id, 1)
    new_pub = await get_page_publication(conn, fx.new_document_id, 1)
    return {
        "old_document_publication": old_pub,
        "new_document_publication": new_pub,
        "resolved_document": (
            str(fx.old_document_id) if old_pub else
            str(fx.new_document_id) if new_pub else None
        ),
        "resolved_marker": (old_pub or new_pub or {}).get("marker") if (old_pub or new_pub) else None,
    }


async def source_visibility(conn, fx, user_id: UUID):
    result = {}
    for label, doc in (("old", fx.old_document_id), ("new", fx.new_document_id)):
        try:
            row = await get_authorized_source(conn, user_id=user_id, document_id=doc)
            result[label] = {"allowed": True, "document_id": str(row["id"]),
                             "source_path": row["source_path"],
                             "source_sha256": row["source_sha256"]}
        except ScopeAccessDeniedError:
            result[label] = {"allowed": False, "document_id": None,
                             "source_path": None, "source_sha256": None}
    return result


async def citation_visibility(conn, fx, old_chunk: str, new_chunk: str):
    old_rows = await research.fetch_canonical_chunks(
        conn, knowledge_scope_code=SCOPE_CODE, chunk_ids=[old_chunk],
        include_test_candidates=True,
    )
    new_rows = await research.fetch_canonical_chunks(
        conn, knowledge_scope_code=SCOPE_CODE, chunk_ids=[new_chunk],
        include_test_candidates=True,
    )
    return {
        "old_citation_documents": ids(old_rows),
        "new_citation_documents": ids(new_rows),
        "old_citation_visible": bool(old_rows),
        "new_citation_visible": bool(new_rows),
    }


async def state(conn, fx):
    gens = await fetchall(
        conn, "SELECT id,status,retention_hold FROM library_document_generations WHERE logical_document_id=%s ORDER BY id",
        (fx.logical_id,))
    pointer = await fetchone(
        conn, "SELECT generation_id,expected_generation_id FROM library_logical_document_active_generations WHERE logical_document_id=%s",
        (fx.logical_id,))
    active = [str(r["id"]) for r in gens if r["status"] == "ACTIVE"]
    return {
        "statuses": {str(r["id"]): r["status"] for r in gens},
        "retention_hold": {str(r["id"]): r["retention_hold"] for r in gens},
        "active_count": len(active),
        "active": active,
        "pointer": str(pointer["generation_id"]) if pointer else None,
        "pointer_expected": str(pointer["expected_generation_id"]) if pointer else None,
    }


async def audit_rows(conn, fx):
    rows = await fetchall(
        conn,
        """SELECT operation,result,from_generation_id,to_generation_id,expected_generation_id
           FROM library_generation_activation_audit WHERE logical_document_id=%s
           ORDER BY created_at,id""",
        (fx.logical_id,),
    )
    return [{k: (str(v) if v is not None else None) for k, v in dict(r).items()} for r in rows]


async def main() -> None:
    results: dict = {}
    async with connection() as conn:
        await purge_synthetic(conn)
        async with conn.transaction():
            fx = await _create_synthetic(conn)
        try:
            user_id = await user_with_breslov_membership(conn)
            old_chunk, new_chunk = await chunk_ids(conn, fx)
            before = await state(conn, fx)

            old_gid, new_gid = str(fx.old_generation_id), str(fx.new_generation_id)
            results["generation-identity-results.json"] = {
                "logical_document_id": str(fx.logical_id),
                "old_generation_id": old_gid,
                "new_generation_id": new_gid,
                "generation_ids_distinct": old_gid != new_gid,
                "same_logical_document": True,
                "pointer": before["pointer"],
                "pointer_is_old": before["pointer"] == old_gid,
                "PASS": old_gid != new_gid and before["pointer"] == old_gid,
            }

            # exactly one ACTIVE, database rejects a second
            second_active_rejected = False
            second_active_error = None
            try:
                async with conn.transaction():
                    await run(conn, "UPDATE library_document_generations SET status='ACTIVE' WHERE id=%s",
                              (fx.new_generation_id,))
            except Exception as exc:  # noqa: BLE001
                second_active_rejected = "uq_library_document_generations_single_active" in str(exc) or \
                    "duplicate key" in str(exc)
                second_active_error = type(exc).__name__
            async with conn.transaction():
                await run(conn, "DELETE FROM library_generation_activation_audit WHERE logical_document_id=%s",
                          (fx.logical_id,))
                await run(conn, "DELETE FROM library_logical_document_active_generations WHERE logical_document_id=%s",
                          (fx.logical_id,))
                await run(conn, "DELETE FROM library_document_generations WHERE logical_document_id=%s",
                          (fx.logical_id,))
                doc_ids = [str(fx.old_document_id), str(fx.new_document_id)]
                await run(conn, "DELETE FROM library_document_chunks WHERE document_id=ANY(%s::uuid[])", (doc_ids,))
                await run(conn, "DELETE FROM library_pages_v2 WHERE document_id=ANY(%s::uuid[])", (doc_ids,))
                await run(conn, "DELETE FROM library_document_texts WHERE document_id=ANY(%s::uuid[])", (doc_ids,))
                await run(conn, "DELETE FROM library_ingestion_runs_v2 WHERE document_id=ANY(%s::uuid[])", (doc_ids,))
                await run(conn, "DELETE FROM library_documents WHERE id=ANY(%s::uuid[])", (doc_ids,))
                await run(conn, "DELETE FROM library_logical_documents WHERE id=%s", (fx.logical_id,))
                await run(conn, "DELETE FROM library_collections_legacy WHERE code=%s", (COLLECTION_CODE,))
                await run(conn, "DELETE FROM knowledge_scopes WHERE knowledge_scope_code=%s", (SCOPE_CODE,))
            # recreate for the rest of the lifecycle
            async with conn.transaction():
                fx = await _create_synthetic(conn)
            old_chunk, new_chunk = await chunk_ids(conn, fx)
            old_gid, new_gid = str(fx.old_generation_id), str(fx.new_generation_id)
            before = await state(conn, fx)
            results["exactly-one-active-results.json"] = {
                "initial_active_count": before["active_count"],
                "initial_active_is_old": before["active"] == [old_gid],
                "second_active_rejected": second_active_rejected,
                "second_active_error": second_active_error,
                "PASS": before["active_count"] == 1 and second_active_rejected,
            }

            # BEFORE lifecycle
            text_before = {
                "old": await text_visibility(conn, fx, OLD_MARKER),
                "new": await text_visibility(conn, fx, NEW_MARKER),
            }
            hybrid_before = await hybrid_visibility(conn, fx, old_chunk, new_chunk)
            research_before = await research_visibility(conn, fx, NEW_MARKER)
            relation_before = {
                "old": await relation_visibility(conn, fx, OLD_MARKER),
                "new": await relation_visibility(conn, fx, NEW_MARKER),
            }
            viewer_before = await viewer_visibility(conn, fx)
            source_before = await source_visibility(conn, fx, user_id)
            citation_before = await citation_visibility(conn, fx, old_chunk, new_chunk)

            results["text-search-results.json"] = {
                "before_cutover": text_before,
                "PASS_before": text_before["old"]["documents"] == [str(fx.old_document_id)]
                    and text_before["new"]["documents"] == [],
            }
            results["hybrid-search-results.json"] = {
                "before_cutover": hybrid_before,
                "PASS_before": hybrid_before["result_documents"] == [str(fx.old_document_id)],
            }
            results["research-results.json"] = {
                "before_cutover": research_before,
                "PASS_before": research_before["ready_document_ids"] == [str(fx.old_document_id)]
                    and research_before["flag_alone_document_ids"] == [str(fx.old_document_id)]
                    and str(fx.new_document_id) not in research_before["flag_alone_document_ids"],
            }
            results["relation-qa-results.json"] = {
                "before_cutover": relation_before,
                "PASS_before": relation_before["old"]["documents"] == [str(fx.old_document_id)]
                    and relation_before["new"]["documents"] == [],
            }
            results["viewer-results.json"] = {
                "before_cutover": viewer_before,
                "PASS_before": viewer_before["resolved_document"] == str(fx.old_document_id),
            }
            results["citation-source-results.json"] = {
                "before_cutover": {
                    "citation": citation_before,
                    "source": source_before,
                },
                "PASS_before": citation_before["old_citation_visible"]
                    and not citation_before["new_citation_visible"]
                    and source_before["old"]["allowed"] and not source_before["new"]["allowed"],
            }
            explicit_new_hits = await search_chunks_text(
                conn, SCOPE_CODE, NEW_MARKER, top_k=5, mode="phrase",
                document_ids=[str(fx.new_document_id)],
            )
            new_evidence = await gen.generation_evidence(conn, fx.new_generation_id)
            results["candidate-inspection-results.json"] = {
                "explicit_candidate_document_ids": ids(explicit_new_hits),
                "explicit_candidate_chunk_ids": [str(row["chunk_id"]) for row in explicit_new_hits],
                "generation_evidence_chunks": len(new_evidence["chunks"]),
                "generation_evidence_pages": len(new_evidence["pages"]),
                "normal_candidate_visibility": text_before["new"]["documents"],
                "EXPLICIT_CANDIDATE_INSPECTION": ids(explicit_new_hits) == [str(fx.new_document_id)]
                    and len(new_evidence["chunks"]) == 1,
                "NORMAL_CANDIDATE_VISIBILITY": text_before["new"]["documents"] == [],
                "PASS": ids(explicit_new_hits) == [str(fx.new_document_id)]
                    and len(new_evidence["chunks"]) == 1
                    and text_before["new"]["documents"] == [],
            }

            # CUTOVER
            async with conn.transaction():
                cutover = await gen.activate_generation(
                    conn, logical_document_id=fx.logical_id,
                    expected_active_generation_id=old_gid,
                    new_generation_id=new_gid, operation=gen.OPERATION_CUTOVER,
                )
            after_cutover = await state(conn, fx)
            text_after = {"old": await text_visibility(conn, fx, OLD_MARKER),
                          "new": await text_visibility(conn, fx, NEW_MARKER)}
            hybrid_after = await hybrid_visibility(conn, fx, old_chunk, new_chunk)
            research_after = await research_visibility(conn, fx, NEW_MARKER)
            relation_after = {"old": await relation_visibility(conn, fx, OLD_MARKER),
                              "new": await relation_visibility(conn, fx, NEW_MARKER)}
            viewer_after = await viewer_visibility(conn, fx)
            source_after = await source_visibility(conn, fx, user_id)
            citation_after = await citation_visibility(conn, fx, old_chunk, new_chunk)
            results["cutover-results.json"] = {
                "operation": "CUTOVER", "result": cutover["result"],
                "from": cutover["from_generation_id"], "to": cutover["to_generation_id"],
                "expected": cutover["expected_generation_id"],
                "after": after_cutover,
                "OLD_INACTIVE": after_cutover["statuses"][old_gid] == "INACTIVE",
                "NEW_ACTIVE": after_cutover["statuses"][new_gid] == "ACTIVE",
                "pointer_is_new": after_cutover["pointer"] == new_gid,
                "PASS": cutover["result"] == "APPLIED"
                    and after_cutover["statuses"][old_gid] == "INACTIVE"
                    and after_cutover["statuses"][new_gid] == "ACTIVE"
                    and after_cutover["pointer"] == new_gid,
            }
            results["text-search-results.json"]["after_cutover"] = text_after
            results["text-search-results.json"]["PASS_after"] = (
                text_after["old"]["documents"] == [] and text_after["new"]["documents"] == [str(fx.new_document_id)])
            results["hybrid-search-results.json"]["after_cutover"] = hybrid_after
            results["hybrid-search-results.json"]["PASS_after"] = hybrid_after["result_documents"] == [str(fx.new_document_id)]
            results["research-results.json"]["after_cutover"] = research_after
            results["research-results.json"]["PASS_after"] = research_after["ready_document_ids"] == [str(fx.new_document_id)]
            results["relation-qa-results.json"]["after_cutover"] = relation_after
            results["relation-qa-results.json"]["PASS_after"] = (
                relation_after["old"]["documents"] == [] and relation_after["new"]["documents"] == [str(fx.new_document_id)])
            results["viewer-results.json"]["after_cutover"] = viewer_after
            results["viewer-results.json"]["PASS_after"] = viewer_after["resolved_document"] == str(fx.new_document_id)
            results["citation-source-results.json"]["after_cutover"] = {"citation": citation_after, "source": source_after}
            results["citation-source-results.json"]["PASS_after"] = (
                citation_after["new_citation_visible"] and not citation_after["old_citation_visible"]
                and source_after["new"]["allowed"] and not source_after["old"]["allowed"])

            # CUTOVER audit
            audit = await audit_rows(conn, fx)
            cutover_audit = [row for row in audit if row["operation"] == "CUTOVER" and row["result"] == "APPLIED"]
            results["cutover-audit-results.json"] = {
                "audit": cutover_audit[-1] if cutover_audit else None,
                "PASS": bool(cutover_audit) and cutover_audit[-1]["from_generation_id"] == old_gid
                    and cutover_audit[-1]["to_generation_id"] == new_gid
                    and cutover_audit[-1]["expected_generation_id"] == old_gid,
            }

            # STALE CAS (expected OLD no longer matches the active NEW)
            stale_rejected = False
            stale_error = None
            try:
                async with conn.transaction():
                    await gen.activate_generation(
                        conn, logical_document_id=fx.logical_id,
                        expected_active_generation_id=old_gid,
                        new_generation_id=old_gid, operation=gen.OPERATION_CUTOVER,
                    )
            except gen.GenerationConflictError as exc:
                stale_rejected = True
                stale_error = str(exc)
            state_stale = await state(conn, fx)
            results["stale-cas-results.json"] = {
                "rejected": stale_rejected, "error": stale_error,
                "active_after": state_stale["active"], "pointer_after": state_stale["pointer"],
                "PASS": stale_rejected and state_stale["pointer"] == new_gid,
            }

            # IDEMPOTENCY of repeated cutover to the same target
            async with conn.transaction():
                repeated = await gen.activate_generation(
                    conn, logical_document_id=fx.logical_id,
                    expected_active_generation_id=new_gid,
                    new_generation_id=new_gid, operation=gen.OPERATION_CUTOVER,
                )
            results["idempotency-results.json"] = {
                "result": repeated["result"], "PASS": repeated["result"] == "IDEMPOTENT",
                "active_count": (await state(conn, fx))["active_count"],
            }

            # ROLLBACK
            async with conn.transaction():
                rollback = await gen.activate_generation(
                    conn, logical_document_id=fx.logical_id,
                    expected_active_generation_id=new_gid,
                    new_generation_id=old_gid, operation=gen.OPERATION_ROLLBACK,
                )
            after_rollback = await state(conn, fx)
            text_back = {"old": await text_visibility(conn, fx, OLD_MARKER),
                         "new": await text_visibility(conn, fx, NEW_MARKER)}
            hybrid_back = await hybrid_visibility(conn, fx, old_chunk, new_chunk)
            research_back = await research_visibility(conn, fx, NEW_MARKER)
            relation_back = {"old": await relation_visibility(conn, fx, OLD_MARKER),
                             "new": await relation_visibility(conn, fx, NEW_MARKER)}
            viewer_back = await viewer_visibility(conn, fx)
            source_back = await source_visibility(conn, fx, user_id)
            citation_back = await citation_visibility(conn, fx, old_chunk, new_chunk)
            results["rollback-results.json"] = {
                "operation": "ROLLBACK", "result": rollback["result"],
                "from": rollback["from_generation_id"], "to": rollback["to_generation_id"],
                "after": after_rollback,
                "NEW_INACTIVE": after_rollback["statuses"][new_gid] == "INACTIVE",
                "OLD_ACTIVE": after_rollback["statuses"][old_gid] == "ACTIVE",
                "pointer_is_old": after_rollback["pointer"] == old_gid,
                "PASS": rollback["result"] == "APPLIED"
                    and after_rollback["statuses"][new_gid] == "INACTIVE"
                    and after_rollback["statuses"][old_gid] == "ACTIVE"
                    and after_rollback["pointer"] == old_gid,
            }
            results["text-search-results.json"]["after_rollback"] = text_back
            results["text-search-results.json"]["PASS_after_rollback"] = (
                text_back["old"]["documents"] == [str(fx.old_document_id)] and text_back["new"]["documents"] == [])
            results["hybrid-search-results.json"]["after_rollback"] = hybrid_back
            results["hybrid-search-results.json"]["PASS_after_rollback"] = hybrid_back["result_documents"] == [str(fx.old_document_id)]
            results["research-results.json"]["after_rollback"] = research_back
            results["research-results.json"]["PASS_after_rollback"] = research_back["ready_document_ids"] == [str(fx.old_document_id)]
            results["relation-qa-results.json"]["after_rollback"] = relation_back
            results["relation-qa-results.json"]["PASS_after_rollback"] = (
                relation_back["old"]["documents"] == [str(fx.old_document_id)] and relation_back["new"]["documents"] == [])
            results["viewer-results.json"]["after_rollback"] = viewer_back
            results["viewer-results.json"]["PASS_after_rollback"] = viewer_back["resolved_document"] == str(fx.old_document_id)
            results["citation-source-results.json"]["after_rollback"] = {"citation": citation_back, "source": source_back}
            results["citation-source-results.json"]["PASS_after_rollback"] = (
                citation_back["old_citation_visible"] and not citation_back["new_citation_visible"]
                and source_back["old"]["allowed"] and not source_back["new"]["allowed"])

            audit = await audit_rows(conn, fx)
            rollback_audit = [row for row in audit if row["operation"] == "ROLLBACK" and row["result"] == "APPLIED"]
            results["rollback-audit-results.json"] = {
                "audit": rollback_audit[-1] if rollback_audit else None,
                "PASS": bool(rollback_audit) and rollback_audit[-1]["from_generation_id"] == new_gid
                    and rollback_audit[-1]["to_generation_id"] == old_gid
                    and rollback_audit[-1]["expected_generation_id"] == new_gid,
            }

            # CLEANUP / RETENTION
            protected_old = await gen.cleanup_protected_generations(conn, fx.old_document_id)
            protected_new = await gen.cleanup_protected_generations(conn, fx.new_document_id)
            results["cleanup-retention-results.json"] = {
                "after_rollback": {"old": protected_old, "new": protected_new},
                "retained_previous_active_protected": any(str(r["id"]) == new_gid for r in protected_new),
                "active_protected": any(str(r["id"]) == old_gid for r in protected_old),
                "PASS": any(str(r["id"]) == old_gid for r in protected_old)
                    and any(str(r["id"]) == new_gid for r in protected_new),
            }

            # CAS atomicity: a failure inside the switch transaction rolls back fully
            atomic_before = await state(conn, fx)
            try:
                async with conn.transaction():
                    await gen.activate_generation(
                        conn, logical_document_id=fx.logical_id,
                        expected_active_generation_id=old_gid,
                        new_generation_id=new_gid, operation=gen.OPERATION_CUTOVER,
                    )
                    raise RuntimeError("forced rollback for atomicity probe")
            except RuntimeError:
                pass
            atomic_after = await state(conn, fx)
            results["cas-atomicity-results.json"] = {
                "before": atomic_before, "after_forced_rollback": atomic_after,
                "never_two_active": atomic_after["active_count"] == 1,
                "never_zero_active": atomic_after["active_count"] == 1,
                "state_restored": atomic_before == atomic_after,
                "PASS": atomic_before == atomic_after and atomic_after["active_count"] == 1,
            }

            # final summary
            for name, payload in results.items():
                if isinstance(payload, dict):
                    payload["gate"] = "TEBAAI_BRESLOV_PARALLEL_GENERATION_FOUNDATION_V2_PUBLICATION_V1R2"
                    payload["scenario"] = "synthetic OLD ACTIVE / NEW CANDIDATE; real DEV PostgreSQL; read-only C"
                    (OUT / name).write_text(json.dumps(payload, indent=2, default=str) + "\n",
                                            encoding="utf-8")

        finally:
            await purge_synthetic(conn)

    print(json.dumps({k: v.get("PASS", v.get("PASS_before")) for k, v in results.items()}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
