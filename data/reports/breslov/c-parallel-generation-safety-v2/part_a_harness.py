#!/usr/bin/env python3
"""PART A — parallel generation isolation against real DEV PostgreSQL + Milvus.

Synthetic OLD (ACTIVE) and NEW (CANDIDATE) generations of one logical document.
All writes are confined to an isolated synthetic scope/collection and an
isolated Milvus collection. CURRENT C is never written.

Frozen expectations live in this file; see frozen-manifest.json.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from uuid import UUID, uuid4

BACKEND = Path(os.environ.get(
    "AUTHORITATIVE_BACKEND",
    "/tmp/opencode/tebaai-b4a26a9/SrvRestAstroLS_v1/backend",
))
sys.path.insert(0, str(BACKEND))

import psycopg  # noqa: E402
from psycopg.rows import dict_row  # noqa: E402
from pymilvus import utility  # noqa: E402

import globalVar as g  # noqa: E402
import tests.test_generation_foundation as tgf  # noqa: E402
from infrastructure.milvus import client as mv  # noqa: E402
from modules.embeddings.client import embed_text  # noqa: E402
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

OUT = Path(__file__).resolve().parent
SCOPE = "safety_v2_gate"
COLLECTION = "safety_v2_gate"
OLD_MARKER = "SAFETY_V2_OLD_ONLY"
NEW_MARKER = "SAFETY_V2_NEW_ONLY"
VECTOR_PROBE = "safetyv2vectornomatch"

# The authoritative fixture module resolves these globals at call time.
tgf.SCOPE_CODE = SCOPE
tgf.COLLECTION_CODE = COLLECTION
tgf.OLD_MARKER = OLD_MARKER
tgf.NEW_MARKER = NEW_MARKER


def dsn() -> str:
    return (
        f"host={os.environ['DB_PG_IP']} port={os.environ.get('DB_PG_PORT', '5432')} "
        f"user={os.environ['DB_PG_USER']} password={os.environ['DB_PG_PASS']} "
        f"dbname={os.environ.get('TEBAAI_DB_NAME', 'tebaai')}"
    )


def write(name: str, payload) -> None:
    (OUT / name).write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


async def fetchone(conn, sql, params=None):
    async with conn.cursor() as cur:
        await cur.execute(sql, params)
        return await cur.fetchone()


async def fetchall(conn, sql, params=None):
    async with conn.cursor() as cur:
        await cur.execute(sql, params)
        return await cur.fetchall()


async def run(conn, sql, params=None) -> int:
    async with conn.cursor() as cur:
        await cur.execute(sql, params)
        return cur.rowcount


def ids(rows, key="document_id"):
    return [str(row[key]) for row in rows]


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
    """Remove only leftovers of this gate's isolated synthetic scope."""
    scope = await fetchone(
        conn, "SELECT id FROM knowledge_scopes WHERE knowledge_scope_code=%s", (SCOPE,)
    )
    if not scope:
        return
    scope_id = scope["id"]
    async with conn.transaction():
        await run(conn, """
            DELETE FROM library_generation_activation_audit
            WHERE logical_document_id IN (
                SELECT id FROM library_logical_documents WHERE knowledge_scope_id=%s)
        """, (scope_id,))
        await run(conn, """
            DELETE FROM library_logical_document_active_generations
            WHERE logical_document_id IN (
                SELECT id FROM library_logical_documents WHERE knowledge_scope_id=%s)
        """, (scope_id,))
        await run(conn, """
            DELETE FROM library_document_generations
            WHERE logical_document_id IN (
                SELECT id FROM library_logical_documents WHERE knowledge_scope_id=%s)
        """, (scope_id,))
        await run(conn, """
            UPDATE library_documents SET logical_document_id=NULL
            WHERE knowledge_scope_id=%s
        """, (scope_id,))
        doc_ids = [str(r["id"]) for r in await fetchall(
            conn, "SELECT id FROM library_documents WHERE knowledge_scope_id=%s", (scope_id,))]
        for doc in doc_ids:
            for table in ("library_document_chunks", "library_pages_v2",
                          "library_document_texts", "library_ingestion_runs_v2"):
                await run(conn, f"DELETE FROM {table} WHERE document_id=%s", (doc,))
            await run(conn, "DELETE FROM library_documents WHERE id=%s", (doc,))
        await run(conn, "DELETE FROM library_logical_documents WHERE knowledge_scope_id=%s",
                  (scope_id,))
        await run(conn, "DELETE FROM library_collections_legacy WHERE code=%s", (COLLECTION,))
        await run(conn, "DELETE FROM knowledge_scopes WHERE knowledge_scope_code=%s", (SCOPE,))


async def chunk_ids(conn, fx) -> tuple[str, str]:
    old = await fetchone(
        conn, "SELECT id FROM library_document_chunks WHERE document_id=%s", (fx.old_document_id,))
    new = await fetchone(
        conn, "SELECT id FROM library_document_chunks WHERE document_id=%s", (fx.new_document_id,))
    return str(old["id"]), str(new["id"])


async def state(conn, fx) -> dict:
    gens = await fetchall(
        conn,
        "SELECT id,status,retention_hold FROM library_document_generations "
        "WHERE logical_document_id=%s ORDER BY created_at,id",
        (fx.logical_id,),
    )
    pointer = await fetchone(
        conn,
        "SELECT generation_id,expected_generation_id,operation "
        "FROM library_logical_document_active_generations WHERE logical_document_id=%s",
        (fx.logical_id,),
    )
    active = [str(r["id"]) for r in gens if r["status"] == "ACTIVE"]
    return {
        "statuses": {str(r["id"]): r["status"] for r in gens},
        "retention_hold": {str(r["id"]): r["retention_hold"] for r in gens},
        "active_count": len(active),
        "active": active,
        "pointer": str(pointer["generation_id"]) if pointer else None,
        "pointer_expected": str(pointer["expected_generation_id"]) if pointer else None,
        "pointer_operation": pointer["operation"] if pointer else None,
    }


# ── Milvus isolated vector lane ─────────────────────────────────────────────

def setup_milvus(fx, old_chunk: str, new_chunk: str) -> str:
    name = f"tebaai_safety_v2_{uuid4().hex[:8]}"
    mv.create_connection()
    mv.ensure_collection(name, dimension=1536)
    old_vec = embed_text(OLD_MARKER)
    new_vec = embed_text(NEW_MARKER)
    base = {
        "collection_code": SCOPE,
        "language": "es",
        "source_type": "synthetic",
        "source_sha256": "f" * 64,
        "chunk_index": 0,
        "page_start": 1,
        "page_end": 1,
    }
    vectors = [
        {
            **base,
            "pk": f"old-{uuid4().hex}",
            "chunk_id": old_chunk,
            "document_id": str(fx.old_document_id),
            "title": "SAFETY_V2 synthetic old",
            "content_sha256": "a" * 64,
            "content_preview": OLD_MARKER,
            "embedding": old_vec,
        },
        {
            **base,
            "pk": f"new-{uuid4().hex}",
            "chunk_id": new_chunk,
            "document_id": str(fx.new_document_id),
            "title": "SAFETY_V2 synthetic new",
            "content_sha256": "b" * 64,
            "content_preview": NEW_MARKER,
            "embedding": new_vec,
        },
    ]
    inserted = mv.insert_vectors(name, vectors)
    if inserted != 2:
        raise RuntimeError(f"expected 2 synthetic vectors, inserted {inserted}")
    return name


def drop_milvus(name: str) -> None:
    try:
        if name in utility.list_collections():
            utility.drop_collection(name)
    except Exception:
        pass


def milvus_c_count() -> int | str:
    try:
        from pymilvus import Collection
        col = Collection("tebaai_breslov_chunks_v1")
        col.load()
        rows = col.query(
            expr='document_id == "ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa"',
            output_fields=["count(*)"],
        )
        return int(rows[0]["count(*)"]) if rows else 0
    except Exception as exc:  # noqa: BLE001
        return f"UNAVAILABLE:{type(exc).__name__}"


def direct_vector_search(name: str, query: str, expr: str) -> list[dict]:
    hits = mv.search_vectors(
        collection_name=name,
        query_embedding=embed_text(query),
        top_k=10,
        expr=expr,
        output_fields=["chunk_id", "document_id"],
    )
    return [{"chunk_id": h.get("chunk_id"), "document_id": h.get("document_id"),
             "distance": h.get("distance")} for h in hits]


async def hybrid_visibility(conn, fx, colname: str, marker: str) -> dict:
    marker_rows = await hybrid_search.search_chunks_hybrid(
        conn, SCOPE, marker, top_k=5, milvus_collection=colname,
    )
    probe_rows = await hybrid_search.search_chunks_hybrid(
        conn, SCOPE, VECTOR_PROBE, top_k=5, milvus_collection=colname,
    )
    coll_expr = f'collection_code == "{SCOPE}"'
    both_expr = (
        f'({coll_expr}) and (document_id == "{fx.old_document_id}" '
        f'or document_id == "{fx.new_document_id}")'
    )
    unfiltered = direct_vector_search(colname, VECTOR_PROBE, both_expr)
    filtered_old = direct_vector_search(
        colname, VECTOR_PROBE, f'({coll_expr}) and (document_id == "{fx.old_document_id}")')
    filtered_new = direct_vector_search(
        colname, VECTOR_PROBE, f'({coll_expr}) and (document_id == "{fx.new_document_id}")')
    return {
        "marker_query": {
            "documents": ids(marker_rows),
            "chunk_ids": [str(r["chunk_id"]) for r in marker_rows],
            "source_signals": [r.get("source_signals") for r in marker_rows],
        },
        "vector_only_query": {
            "query": VECTOR_PROBE,
            "documents": ids(probe_rows),
            "chunk_ids": [str(r["chunk_id"]) for r in probe_rows],
            "source_signals": [r.get("source_signals") for r in probe_rows],
        },
        "milvus_raw": {
            "both_documents": sorted({h["document_id"] for h in unfiltered}),
            "old_filter_documents": sorted({h["document_id"] for h in filtered_old}),
            "new_filter_documents": sorted({h["document_id"] for h in filtered_new}),
        },
    }


# ── Readers ─────────────────────────────────────────────────────────────────

async def text_visibility(conn, marker: str):
    rows = await search_chunks_text(conn, SCOPE, marker, top_k=5, mode="phrase")
    return {"marker": marker, "documents": ids(rows), "count": len(rows)}


async def research_visibility(conn, marker: str):
    ready = await research.resolve_ready_documents(conn, knowledge_scope_code=SCOPE)
    normal = await research.search_literal_candidates(
        conn, knowledge_scope_code=SCOPE, variants=[marker], languages=["es"],
        document_ids=None, top_k=5, include_test_candidates=True,
    )
    normal_chunk_ids = [str(r["chunk_id"]) for r in normal]
    resolved = await research.fetch_canonical_chunks(
        conn, knowledge_scope_code=SCOPE, chunk_ids=normal_chunk_ids,
        include_test_candidates=True,
    ) if normal_chunk_ids else []
    return {
        "ready_document_ids": ids(ready),
        "flag_alone_document_ids": sorted({str(r["document_id"]) for r in resolved}),
        "flag_alone_chunk_ids": normal_chunk_ids,
    }


async def relation_visibility(conn, fx, marker: str):
    rows = await search_fts_chunks(
        conn, knowledge_scope_id=fx.scope_id, variants=[marker], language="es",
        include_test_candidates=True, limit=5,
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


async def source_visibility(conn, fx, user_id):
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


async def citation_visibility(conn, old_chunk: str, new_chunk: str):
    old_rows = await research.fetch_canonical_chunks(
        conn, knowledge_scope_code=SCOPE, chunk_ids=[old_chunk], include_test_candidates=True)
    new_rows = await research.fetch_canonical_chunks(
        conn, knowledge_scope_code=SCOPE, chunk_ids=[new_chunk], include_test_candidates=True)
    return {
        "old_citation_documents": ids(old_rows),
        "new_citation_documents": ids(new_rows),
        "old_citation_visible": bool(old_rows),
        "new_citation_visible": bool(new_rows),
    }


async def snapshot_readers(conn, fx, user_id, old_chunk, new_chunk, colname):
    text = {"old": await text_visibility(conn, OLD_MARKER),
            "new": await text_visibility(conn, NEW_MARKER)}
    return {
        "text": text,
        "hybrid": {
            "old": await hybrid_visibility(conn, fx, colname, OLD_MARKER),
            "new": await hybrid_visibility(conn, fx, colname, NEW_MARKER),
        },
        "research_old": await research_visibility(conn, OLD_MARKER),
        "research_new": await research_visibility(conn, NEW_MARKER),
        "relation": {"old": await relation_visibility(conn, fx, OLD_MARKER),
                     "new": await relation_visibility(conn, fx, NEW_MARKER)},
        "viewer": await viewer_visibility(conn, fx),
        "source": await source_visibility(conn, fx, user_id),
        "citation": await citation_visibility(conn, old_chunk, new_chunk),
    }


def hybrid_docs(snap: dict, which: str) -> list[str]:
    return snap["hybrid"][which]["marker_query"]["documents"]


def hybrid_vector_only_docs(snap: dict, which: str) -> list[str]:
    return snap["hybrid"][which]["vector_only_query"]["documents"]


def hybrid_vector_signal(snap: dict, which: str) -> bool:
    return any(
        "vector" in (signals or [])
        for signals in snap["hybrid"][which]["vector_only_query"]["source_signals"]
    )


def leakage_count(snap: dict, document) -> int:
    """How many reader surfaces expose an inactive generation's document."""
    target = str(document)
    sources = [
        snap["text"]["old"]["documents"], snap["text"]["new"]["documents"],
        hybrid_docs(snap, "old"), hybrid_docs(snap, "new"),
        hybrid_vector_only_docs(snap, "old"), hybrid_vector_only_docs(snap, "new"),
        snap["research_old"]["flag_alone_document_ids"],
        snap["research_new"]["flag_alone_document_ids"],
        snap["relation"]["old"]["documents"], snap["relation"]["new"]["documents"],
        snap["citation"]["old_citation_documents"],
        snap["citation"]["new_citation_documents"],
    ]
    count = sum(1 for docs in sources if target in {str(item) for item in docs})
    if snap["viewer"]["resolved_document"] == target:
        count += 1
    if (
        snap["source"]["old"]["document_id"] == target
        and snap["source"]["old"]["allowed"]
    ) or (
        snap["source"]["new"]["document_id"] == target
        and snap["source"]["new"]["allowed"]
    ):
        count += 1
    return count


def visibility_assertions(snap: dict, expected_doc, other_doc) -> dict:
    """Compact flat view used only in the report; never drives PASS."""
    expected = str(expected_doc)
    return {
        "text_old_documents": snap["text"]["old"]["documents"],
        "text_new_documents": snap["text"]["new"]["documents"],
        "hybrid_old_documents": hybrid_docs(snap, "old"),
        "hybrid_new_documents": hybrid_docs(snap, "new"),
        "hybrid_vector_only_old_documents": hybrid_vector_only_docs(snap, "old"),
        "hybrid_vector_only_new_documents": hybrid_vector_only_docs(snap, "new"),
        "hybrid_vector_signal_old": hybrid_vector_signal(snap, "old"),
        "hybrid_vector_signal_new": hybrid_vector_signal(snap, "new"),
        "research_old_ready": snap["research_old"]["ready_document_ids"],
        "research_old_flag_alone": snap["research_old"]["flag_alone_document_ids"],
        "research_new_ready": snap["research_new"]["ready_document_ids"],
        "research_new_flag_alone": snap["research_new"]["flag_alone_document_ids"],
        "relation_old": snap["relation"]["old"]["documents"],
        "relation_new": snap["relation"]["new"]["documents"],
        "viewer_resolved": snap["viewer"]["resolved_document"],
        "source_old_allowed": snap["source"]["old"]["allowed"],
        "source_new_allowed": snap["source"]["new"]["allowed"],
        "citation_old_visible": snap["citation"]["old_citation_visible"],
        "citation_new_visible": snap["citation"]["new_citation_visible"],
        "other_document": str(other_doc),
    }


# ── Negative controls ───────────────────────────────────────────────────────

class _Rollback(Exception):
    pass


async def probe_activation(conn, **kwargs) -> dict:
    try:
        async with conn.transaction():
            try:
                result = await gen.activate_generation(conn, **kwargs)
                outcome = {"accepted": True, "result": result}
            except (gen.GenerationPreconditionError, gen.GenerationConflictError) as exc:
                outcome = {"accepted": False, "error_type": type(exc).__name__,
                           "error": str(exc)}
            raise _Rollback()
    except _Rollback:
        pass
    return outcome


async def probe_with_status(conn, gid, status, **kwargs) -> dict:
    async with conn.transaction():
        await run(conn, "UPDATE library_document_generations SET status=%s WHERE id=%s",
                  (status, gid))
    try:
        return await probe_activation(conn, **kwargs)
    finally:
        async with conn.transaction():
            await run(conn, "UPDATE library_document_generations SET status='CANDIDATE' WHERE id=%s",
                      (gid,))
            await run(conn, "UPDATE library_document_generations SET retention_hold=false WHERE id=%s",
                      (gid,))


async def probe_cross_document(conn, fx) -> dict:
    try:
        async with conn.transaction():
            other = await fetchone(
                conn,
                """
                INSERT INTO library_logical_documents(
                    collection_id, knowledge_scope_id, organization_id, workspace_id,
                    project_id, title, source_sha256)
                SELECT collection_id, knowledge_scope_id, organization_id, workspace_id,
                       project_id, 'SAFETY_V2 cross-document probe', %s
                FROM library_logical_documents WHERE id=%s
                RETURNING id
                """,
                ("e" * 64, fx.logical_id),
            )
            other_doc = uuid4()
            await run(
                conn,
                """
                INSERT INTO library_documents(
                    id, collection_id, title, language, source_type, source_filename,
                    source_size_bytes, source_sha256, status, knowledge_scope_id,
                    organization_id, workspace_id, project_id, logical_document_id)
                SELECT %s, collection_id, 'SAFETY_V2 cross-document probe', 'es', 'pdf',
                       'synthetic.pdf', 1, %s, 'ready', knowledge_scope_id,
                       organization_id, workspace_id, project_id, %s
                FROM library_logical_documents WHERE id=%s
                """,
                (other_doc, "e" * 64, other["id"], fx.logical_id),
            )
            other_gen = await gen.register_generation(
                conn, logical_document_id=other["id"], document_id=other_doc,
                pipeline_version="safety_v2_cross_document", source_sha256="e" * 64,
                status="CANDIDATE",
            )
            try:
                await gen.activate_generation(
                    conn, logical_document_id=fx.logical_id,
                    expected_active_generation_id=fx.old_generation_id,
                    new_generation_id=other_gen["id"], operation=gen.OPERATION_CUTOVER,
                )
                outcome = {"accepted": True}
            except (gen.GenerationPreconditionError, gen.GenerationConflictError) as exc:
                outcome = {"accepted": False, "error_type": type(exc).__name__,
                           "error": str(exc)}
            raise _Rollback()
    except _Rollback:
        pass
    return outcome


async def probe_never_active_rollback(conn, fx) -> dict:
    try:
        async with conn.transaction():
            other_doc = uuid4()
            await run(
                conn,
                """
                INSERT INTO library_documents(
                    id, collection_id, title, language, source_type, source_filename,
                    source_size_bytes, source_sha256, status, knowledge_scope_id,
                    organization_id, workspace_id, project_id, logical_document_id)
                SELECT %s, collection_id, 'SAFETY_V2 never-active probe', 'es', 'pdf',
                       'synthetic.pdf', 1, %s, 'ready', knowledge_scope_id,
                       organization_id, workspace_id, project_id, %s
                FROM library_logical_documents WHERE id=%s
                """,
                (other_doc, "f" * 64, fx.logical_id, fx.logical_id),
            )
            never = await gen.register_generation(
                conn, logical_document_id=fx.logical_id, document_id=other_doc,
                pipeline_version="safety_v2_never_active", source_sha256="f" * 64,
                status="INACTIVE",
            )
            await run(conn, "UPDATE library_document_generations SET retention_hold=true WHERE id=%s",
                      (never["id"],))
            await run(
                conn,
                "UPDATE library_logical_document_active_generations "
                "SET expected_generation_id=%s WHERE logical_document_id=%s",
                (never["id"], fx.logical_id),
            )
            try:
                await gen.activate_generation(
                    conn, logical_document_id=fx.logical_id,
                    expected_active_generation_id=fx.old_generation_id,
                    new_generation_id=never["id"], operation=gen.OPERATION_ROLLBACK,
                )
                outcome = {"accepted": True}
            except (gen.GenerationPreconditionError, gen.GenerationConflictError) as exc:
                outcome = {"accepted": False, "error_type": type(exc).__name__,
                           "error": str(exc)}
            raise _Rollback()
    except _Rollback:
        pass
    return outcome


async def negative_controls(conn, fx) -> dict:
    old_gid = str(fx.old_generation_id)
    new_gid = str(fx.new_generation_id)
    results = {}

    results["arbitrary_inactive_cutover"] = await probe_with_status(
        conn, new_gid, "INACTIVE",
        logical_document_id=fx.logical_id,
        expected_active_generation_id=old_gid, new_generation_id=new_gid,
        operation=gen.OPERATION_CUTOVER,
    )
    results["building_cutover"] = await probe_with_status(
        conn, new_gid, "BUILDING",
        logical_document_id=fx.logical_id,
        expected_active_generation_id=old_gid, new_generation_id=new_gid,
        operation=gen.OPERATION_CUTOVER,
    )
    results["failed_cutover"] = await probe_with_status(
        conn, new_gid, "FAILED",
        logical_document_id=fx.logical_id,
        expected_active_generation_id=old_gid, new_generation_id=new_gid,
        operation=gen.OPERATION_CUTOVER,
    )
    results["cross_document_cutover"] = await probe_cross_document(conn, fx)
    results["stale_cutover_pre_lifecycle"] = await probe_activation(
        conn, logical_document_id=fx.logical_id,
        expected_active_generation_id=str(uuid4()), new_generation_id=new_gid,
        operation=gen.OPERATION_CUTOVER,
    )
    results["stale_rollback_pre_lifecycle"] = await probe_activation(
        conn, logical_document_id=fx.logical_id,
        expected_active_generation_id=new_gid, new_generation_id=old_gid,
        operation=gen.OPERATION_ROLLBACK,
    )
    results["never_active_rollback"] = await probe_never_active_rollback(conn, fx)
    results["NEGATIVE_CONTROLS_ACCEPTED"] = sum(
        1 for value in results.values() if isinstance(value, dict) and value.get("accepted")
    )
    results["PASS"] = results["NEGATIVE_CONTROLS_ACCEPTED"] == 0
    return results


# ── Main ────────────────────────────────────────────────────────────────────

async def main() -> None:
    summary: dict = {}
    async with await psycopg.AsyncConnection.connect(
        dsn(), row_factory=dict_row, connect_timeout=5
    ) as conn:
        await purge_synthetic(conn)
        milvus_before = milvus_c_count()
        async with conn.transaction():
            fx = await tgf._create_synthetic(conn)
        colname = None
        try:
            user_id = await user_with_breslov_membership(conn)
            old_chunk, new_chunk = await chunk_ids(conn, fx)
            old_gid, new_gid = str(fx.old_generation_id), str(fx.new_generation_id)
            before_state = await state(conn, fx)
            new_run = await fetchone(
                conn, "SELECT status,finished_at FROM library_ingestion_runs_v2 WHERE run_id=%s",
                (fx.new_run_id,))
            fixture = {
                "scope_code": SCOPE,
                "collection_code": COLLECTION,
                "logical_document_id": str(fx.logical_id),
                "old_document_id": str(fx.old_document_id),
                "new_document_id": str(fx.new_document_id),
                "old_generation_id": old_gid,
                "new_generation_id": new_gid,
                "old_run_id": str(fx.old_run_id),
                "new_run_id": str(fx.new_run_id),
                "old_marker": OLD_MARKER,
                "new_marker": NEW_MARKER,
                "old_status": before_state["statuses"][old_gid],
                "new_status": before_state["statuses"][new_gid],
                "new_run_status": new_run["status"],
                "new_run_finished_at": new_run["finished_at"].isoformat() if new_run["finished_at"] else None,
                "new_is_newer_than_old": True,
                "active_pointer_is_old": before_state["pointer"] == old_gid,
            }
            write("synthetic-fixture.json", fixture)

            colname = setup_milvus(fx, old_chunk, new_chunk)
            fixture["milvus_collection"] = colname
            write("synthetic-fixture.json", fixture)

            # Negative controls before the lifecycle.
            write("negative-controls.json", await negative_controls(conn, fx))

            # ── BEFORE CUTOVER ───────────────────────────────────────────
            snap_before = await snapshot_readers(
                conn, fx, user_id, old_chunk, new_chunk, colname)
            explicit_hits = await search_chunks_text(
                conn, SCOPE, NEW_MARKER, top_k=5, mode="phrase",
                document_ids=[str(fx.new_document_id)])
            new_evidence = await gen.generation_evidence(conn, fx.new_generation_id)
            before_payload = {
                "state": before_state,
                "readers": snap_before,
                "explicit_candidate_inspection": {
                    "generation_id": new_gid,
                    "explicit_document_ids": ids(explicit_hits),
                    "explicit_chunk_ids": [str(r["chunk_id"]) for r in explicit_hits],
                    "generation_evidence_chunks": len(new_evidence["chunks"]),
                    "generation_evidence_pages": len(new_evidence["pages"]),
                    "normal_candidate_visibility": snap_before["text"]["new"]["documents"],
                    "EXPLICIT_CANDIDATE_INSPECTION": (
                        ids(explicit_hits) == [str(fx.new_document_id)]
                        and len(new_evidence["chunks"]) == 1
                    ),
                    "NORMAL_CANDIDATE_VISIBILITY": snap_before["text"]["new"]["documents"] == [],
                },
                "OLD_VISIBLE": (
                    snap_before["text"]["old"]["documents"] == [str(fx.old_document_id)]
                    and str(fx.old_document_id) in hybrid_docs(snap_before, "old")
                    and str(fx.old_document_id) in hybrid_vector_only_docs(snap_before, "old")
                    and hybrid_vector_signal(snap_before, "old")
                    and str(fx.old_document_id) in snap_before["research_old"]["flag_alone_document_ids"]
                    and snap_before["relation"]["old"]["documents"] == [str(fx.old_document_id)]
                    and snap_before["viewer"]["resolved_document"] == str(fx.old_document_id)
                    and snap_before["citation"]["old_citation_visible"]
                    and snap_before["source"]["old"]["allowed"]
                ),
                "NEW_INVISIBLE": (
                    str(fx.new_document_id) not in snap_before["text"]["new"]["documents"]
                    and str(fx.new_document_id) not in hybrid_docs(snap_before, "new")
                    and str(fx.new_document_id) not in hybrid_vector_only_docs(snap_before, "new")
                    and str(fx.new_document_id)
                    not in snap_before["research_new"]["flag_alone_document_ids"]
                    and str(fx.new_document_id) not in snap_before["relation"]["new"]["documents"]
                    and snap_before["viewer"]["resolved_document"] != str(fx.new_document_id)
                    and not snap_before["citation"]["new_citation_visible"]
                    and not snap_before["source"]["new"]["allowed"]
                ),
            }
            before_payload["CANDIDATE_PRE_CUTOVER_LEAKAGE"] = leakage_count(
                snap_before, fx.new_document_id
            )
            before_payload["PASS"] = (
                before_payload["OLD_VISIBLE"]
                and before_payload["NEW_INVISIBLE"]
                and before_payload["CANDIDATE_PRE_CUTOVER_LEAKAGE"] == 0
                and before_payload["explicit_candidate_inspection"]["EXPLICIT_CANDIDATE_INSPECTION"]
                and before_payload["explicit_candidate_inspection"]["NORMAL_CANDIDATE_VISIBILITY"]
            )
            write("before-cutover.json", before_payload)

            # ── CUTOVER ─────────────────────────────────────────────────
            async with conn.transaction():
                cutover = await gen.activate_generation(
                    conn, logical_document_id=fx.logical_id,
                    expected_active_generation_id=old_gid,
                    new_generation_id=new_gid, operation=gen.OPERATION_CUTOVER,
                )
            after_state = await state(conn, fx)
            cutover_payload = {
                "operation": "CUTOVER",
                "expected_active": old_gid,
                "target": new_gid,
                "result": cutover["result"],
                "from": cutover["from_generation_id"],
                "to": cutover["to_generation_id"],
                "state_after": after_state,
                "OLD_INACTIVE": after_state["statuses"][old_gid] == "INACTIVE",
                "NEW_ACTIVE": after_state["statuses"][new_gid] == "ACTIVE",
                "POINTER_IS_NEW": after_state["pointer"] == new_gid,
            }
            cutover_payload["PASS"] = (
                cutover["result"] == "APPLIED"
                and cutover_payload["OLD_INACTIVE"]
                and cutover_payload["NEW_ACTIVE"]
                and cutover_payload["POINTER_IS_NEW"]
            )
            write("cutover.json", cutover_payload)

            snap_after = await snapshot_readers(
                conn, fx, user_id, old_chunk, new_chunk, colname)
            after_payload = {
                "state": after_state,
                "readers": snap_after,
                "OLD_VISIBLE": (
                    str(fx.old_document_id) not in snap_after["text"]["old"]["documents"]
                    and str(fx.old_document_id) not in hybrid_docs(snap_after, "old")
                    and str(fx.old_document_id)
                    not in hybrid_vector_only_docs(snap_after, "old")
                    and str(fx.old_document_id)
                    not in snap_after["research_old"]["flag_alone_document_ids"]
                    and str(fx.old_document_id) not in snap_after["relation"]["old"]["documents"]
                    and snap_after["viewer"]["resolved_document"] != str(fx.old_document_id)
                    and not snap_after["citation"]["old_citation_visible"]
                    and not snap_after["source"]["old"]["allowed"]
                ),
                "NEW_VISIBLE": (
                    snap_after["text"]["new"]["documents"] == [str(fx.new_document_id)]
                    and str(fx.new_document_id) in hybrid_docs(snap_after, "new")
                    and str(fx.new_document_id)
                    in hybrid_vector_only_docs(snap_after, "new")
                    and hybrid_vector_signal(snap_after, "new")
                    and str(fx.new_document_id)
                    in snap_after["research_new"]["flag_alone_document_ids"]
                    and snap_after["relation"]["new"]["documents"] == [str(fx.new_document_id)]
                    and snap_after["viewer"]["resolved_document"] == str(fx.new_document_id)
                    and snap_after["citation"]["new_citation_visible"]
                    and snap_after["source"]["new"]["allowed"]
                ),
                "RETRIEVAL_CITATION_VIEWER_COHERENCE": (
                    snap_after["text"]["new"]["documents"] == [str(fx.new_document_id)]
                    and hybrid_docs(snap_after, "new") == [str(fx.new_document_id)]
                    and snap_after["citation"]["new_citation_documents"] == [str(fx.new_document_id)]
                    and snap_after["viewer"]["resolved_document"] == str(fx.new_document_id)
                ),
            }
            after_payload["OLD_POST_CUTOVER_LEAKAGE"] = leakage_count(
                snap_after, fx.old_document_id
            )
            after_payload["CROSS_GENERATION_CITATION"] = (
                0 if snap_after["citation"]["new_citation_documents"] == [str(fx.new_document_id)]
                and not snap_after["citation"]["old_citation_visible"] else 1
            )
            after_payload["PASS"] = (
                after_payload["OLD_VISIBLE"]
                and after_payload["NEW_VISIBLE"]
                and after_payload["OLD_POST_CUTOVER_LEAKAGE"] == 0
                and after_payload["RETRIEVAL_CITATION_VIEWER_COHERENCE"]
                and after_payload["CROSS_GENERATION_CITATION"] == 0
            )
            write("after-cutover.json", after_payload)

            # ── STALE CAS ───────────────────────────────────────────────
            stale = await probe_activation(
                conn, logical_document_id=fx.logical_id,
                expected_active_generation_id=old_gid,
                new_generation_id=old_gid, operation=gen.OPERATION_CUTOVER,
            )
            stale_state = await state(conn, fx)
            stale_payload = {
                "operation": "CUTOVER",
                "expected_active": old_gid,
                "target": old_gid,
                "rejected": not stale["accepted"],
                "error_type": stale.get("error_type"),
                "error": stale.get("error"),
                "state_after": stale_state,
                "NEW_STILL_ACTIVE": stale_state["statuses"][new_gid] == "ACTIVE",
                "POINTER_STILL_NEW": stale_state["pointer"] == new_gid,
            }
            stale_payload["PASS"] = (
                stale_payload["rejected"]
                and stale_payload["NEW_STILL_ACTIVE"]
                and stale_payload["POINTER_STILL_NEW"]
            )
            write("stale-cas.json", stale_payload)

            # ── ROLLBACK ────────────────────────────────────────────────
            async with conn.transaction():
                rollback = await gen.activate_generation(
                    conn, logical_document_id=fx.logical_id,
                    expected_active_generation_id=new_gid,
                    new_generation_id=old_gid, operation=gen.OPERATION_ROLLBACK,
                )
            back_state = await state(conn, fx)
            rollback_payload = {
                "operation": "ROLLBACK",
                "expected_active": new_gid,
                "target": old_gid,
                "result": rollback["result"],
                "from": rollback["from_generation_id"],
                "to": rollback["to_generation_id"],
                "state_after": back_state,
                "NEW_INACTIVE": back_state["statuses"][new_gid] == "INACTIVE",
                "OLD_ACTIVE": back_state["statuses"][old_gid] == "ACTIVE",
                "POINTER_IS_OLD": back_state["pointer"] == old_gid,
            }
            rollback_payload["PASS"] = (
                rollback["result"] == "APPLIED"
                and rollback_payload["NEW_INACTIVE"]
                and rollback_payload["OLD_ACTIVE"]
                and rollback_payload["POINTER_IS_OLD"]
            )
            write("rollback.json", rollback_payload)

            snap_back = await snapshot_readers(
                conn, fx, user_id, old_chunk, new_chunk, colname)
            back_payload = {
                "state": back_state,
                "readers": snap_back,
                "OLD_VISIBLE": (
                    snap_back["text"]["old"]["documents"] == [str(fx.old_document_id)]
                    and str(fx.old_document_id) in hybrid_docs(snap_back, "old")
                    and str(fx.old_document_id) in hybrid_vector_only_docs(snap_back, "old")
                    and hybrid_vector_signal(snap_back, "old")
                    and str(fx.old_document_id)
                    in snap_back["research_old"]["flag_alone_document_ids"]
                    and snap_back["relation"]["old"]["documents"] == [str(fx.old_document_id)]
                    and snap_back["viewer"]["resolved_document"] == str(fx.old_document_id)
                    and snap_back["citation"]["old_citation_visible"]
                    and snap_back["source"]["old"]["allowed"]
                ),
                "NEW_INVISIBLE": (
                    str(fx.new_document_id) not in snap_back["text"]["new"]["documents"]
                    and str(fx.new_document_id) not in hybrid_docs(snap_back, "new")
                    and str(fx.new_document_id)
                    not in hybrid_vector_only_docs(snap_back, "new")
                    and str(fx.new_document_id)
                    not in snap_back["research_new"]["flag_alone_document_ids"]
                    and str(fx.new_document_id) not in snap_back["relation"]["new"]["documents"]
                    and snap_back["viewer"]["resolved_document"] != str(fx.new_document_id)
                    and not snap_back["citation"]["new_citation_visible"]
                    and not snap_back["source"]["new"]["allowed"]
                ),
            }
            back_payload["NEW_POST_ROLLBACK_LEAKAGE"] = leakage_count(
                snap_back, fx.new_document_id
            )
            back_payload["PASS"] = (
                back_payload["OLD_VISIBLE"]
                and back_payload["NEW_INVISIBLE"]
                and back_payload["NEW_POST_ROLLBACK_LEAKAGE"] == 0
            )
            write("after-rollback.json", back_payload)

            # ── CLEANUP PROTECTION ──────────────────────────────────────
            protected_old = await gen.cleanup_protected_generations(conn, fx.old_document_id)
            protected_new = await gen.cleanup_protected_generations(conn, fx.new_document_id)
            delete_active_rejected = False
            try:
                async with conn.transaction():
                    await run(conn, "DELETE FROM library_document_generations WHERE id=%s",
                              (fx.old_generation_id,))
            except Exception:  # noqa: BLE001
                delete_active_rejected = True
            cleanup_payload = {
                "after_rollback": {"old": protected_old, "new": protected_new},
                "active_old_protected": any(str(r["id"]) == old_gid for r in protected_old),
                "rollback_target_new_protected": any(str(r["id"]) == new_gid for r in protected_new),
                "delete_active_generation_rejected": delete_active_rejected,
                "PASS": (
                    any(str(r["id"]) == old_gid for r in protected_old)
                    and any(str(r["id"]) == new_gid for r in protected_new)
                    and delete_active_rejected
                ),
            }
            write("cleanup.json", cleanup_payload)

            # ── SYNTHETIC CLEANUP ───────────────────────────────────────
            async with conn.transaction():
                await tgf._destroy_synthetic(conn, fx)
            if colname:
                drop_milvus(colname)
            leftover = {
                "logical_documents": (await fetchone(conn, """
                    SELECT count(*) AS c FROM library_logical_documents
                    WHERE knowledge_scope_id IN (
                        SELECT id FROM knowledge_scopes WHERE knowledge_scope_code=%s)
                """, (SCOPE,)))["c"],
                "documents": (await fetchone(conn, """
                    SELECT count(*) AS c FROM library_documents
                    WHERE knowledge_scope_id IN (
                        SELECT id FROM knowledge_scopes WHERE knowledge_scope_code=%s)
                """, (SCOPE,)))["c"],
                "generations": (await fetchone(conn, """
                    SELECT count(*) AS c FROM library_document_generations g
                    JOIN library_logical_documents l ON l.id=g.logical_document_id
                    WHERE l.knowledge_scope_id IN (
                        SELECT id FROM knowledge_scopes WHERE knowledge_scope_code=%s)
                """, (SCOPE,)))["c"],
                "active_pointers": (await fetchone(conn, """
                    SELECT count(*) AS c FROM library_logical_document_active_generations p
                    JOIN library_logical_documents l ON l.id=p.logical_document_id
                    WHERE l.knowledge_scope_id IN (
                        SELECT id FROM knowledge_scopes WHERE knowledge_scope_code=%s)
                """, (SCOPE,)))["c"],
                "chunks": (await fetchone(conn, """
                    SELECT count(*) AS c FROM library_document_chunks
                    WHERE knowledge_scope_id IN (
                        SELECT id FROM knowledge_scopes WHERE knowledge_scope_code=%s)
                """, (SCOPE,)))["c"],
                "vectors": (await fetchone(conn, """
                    SELECT count(*) AS c FROM library_chunk_embeddings e
                    JOIN library_document_chunks ch ON ch.id=e.chunk_id
                    WHERE ch.knowledge_scope_id IN (
                        SELECT id FROM knowledge_scopes WHERE knowledge_scope_code=%s)
                """, (SCOPE,)))["c"],
                "scope_rows": (await fetchone(conn,
                    "SELECT count(*) AS c FROM knowledge_scopes WHERE knowledge_scope_code=%s",
                    (SCOPE,)))["c"],
                "collection_rows": (await fetchone(conn,
                    "SELECT count(*) AS c FROM library_collections_legacy WHERE code=%s",
                    (COLLECTION,)))["c"],
                "milvus_collection_present": colname in utility.list_collections(),
            }
            leftover["PASS"] = all(value == 0 for key, value in leftover.items()
                                   if key not in {"PASS", "milvus_collection_present"}) \
                and not leftover["milvus_collection_present"]
            write("cleanup.json", {**cleanup_payload, "synthetic_leftovers": leftover})

            summary = {
                "fixture": fixture,
                "negative_controls": json.loads((OUT / "negative-controls.json").read_text()),
                "before": before_payload,
                "cutover": cutover_payload,
                "after": after_payload,
                "stale": stale_payload,
                "rollback": rollback_payload,
                "after_rollback": back_payload,
                "cleanup": json.loads((OUT / "cleanup.json").read_text()),
                "milvus_c_vectors_before": milvus_before,
                "milvus_c_vectors_after": milvus_c_count(),
            }
            write("part-a-summary.json", summary)
            print(json.dumps({
                "before_PASS": before_payload["PASS"],
                "cutover_PASS": cutover_payload["PASS"],
                "after_PASS": after_payload["PASS"],
                "stale_PASS": stale_payload["PASS"],
                "rollback_PASS": rollback_payload["PASS"],
                "after_rollback_PASS": back_payload["PASS"],
                "cleanup_PASS": leftover["PASS"],
                "negative_controls_PASS": summary["negative_controls"]["PASS"],
            }, indent=2))
        finally:
            if colname:
                drop_milvus(colname)


if __name__ == "__main__":
    asyncio.run(main())
