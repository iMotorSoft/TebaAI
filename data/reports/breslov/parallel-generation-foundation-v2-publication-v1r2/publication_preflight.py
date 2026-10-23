"""Foundation V2 publication preflight harness (real DEV PostgreSQL).

Creates an isolated synthetic logical document with an OLD (ACTIVE) and a NEW
(CANDIDATE) generation using the productive registration order:

    document (nullable logical link) -> ingestion run -> document/logical link
    -> generation

Then it exercises CUTOVER, ROLLBACK, the negative activation controls and the
FK-safe cleanup. Nothing here touches the real C document, Milvus, extraction or
embeddings.

Usage (from SrvRestAstroLS_v1/backend):

    PYTHONPATH=. uv run python <path>/publication_preflight.py out.json --label run1

Every run uses fresh identifiers derived from the label plus a random suffix.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

import psycopg
from psycopg import AsyncConnection
from psycopg.rows import dict_row

import globalVar as config
from modules.library import generation as generation_module
from modules.library.generation import (
    GENERATION_ACTIVE,
    GENERATION_BUILDING,
    GENERATION_CANDIDATE,
    GENERATION_FAILED,
    GENERATION_INACTIVE,
    OPERATION_CUTOVER,
    OPERATION_ROLLBACK,
    GenerationConflictError,
    GenerationPreconditionError,
    activate_generation,
    resolve_active_document_ids,
    set_generation_status,
)

OLD_MARKER = "PREFLIGHTV2OLDEV"
NEW_MARKER = "PREFLIGHTV2NEWEV"
ALT_MARKER = "PREFLIGHTV2ALTEV"


def _log(step: str, **data: Any) -> None:
    print(json.dumps({"step": step, **data}, default=str), flush=True)


async def _fetchone(conn, sql: str, params: dict | tuple | None = None):
    async with conn.cursor() as cur:
        await cur.execute(sql, params)
        return await cur.fetchone()


async def _run(conn, sql: str, params: dict | tuple | None = None) -> int:
    async with conn.cursor() as cur:
        await cur.execute(sql, params)
        return cur.rowcount


async def _insert_document(
    conn, tenant, scope_id, collection_id, document_id, label, marker, source_sha
):
    await _run(
        conn,
        """
        INSERT INTO library_documents(
            id, collection_id, title, language, source_type, source_filename,
            source_size_bytes, source_sha256, status, knowledge_scope_id,
            organization_id, workspace_id, project_id)
        VALUES (%s, %s, %s, 'es', 'pdf', 'preflight.pdf', 1, %s, 'ready', %s,
                %s, %s, %s)
        """,
        (
            document_id,
            collection_id,
            f"Foundation V2 preflight synthetic {label}",
            source_sha,
            scope_id,
            tenant["organization_id"],
            tenant["workspace_id"],
            tenant["project_id"],
        ),
    )
    text_id = uuid4()
    await _run(
        conn,
        """
        INSERT INTO library_document_texts(
            id, document_id, text_format, content, content_sha256, content_length,
            extraction_method, text_role, page_markers_enabled, page_count,
            knowledge_scope_id)
        VALUES (%s, %s, 'markdown', %s, %s, %s, 'synthetic', 'canonical', true, 1, %s)
        """,
        (
            text_id,
            document_id,
            marker,
            hashlib.sha256(marker.encode()).hexdigest(),
            len(marker),
            scope_id,
        ),
    )
    run_id = uuid4()
    await _run(
        conn,
        """
        INSERT INTO library_ingestion_runs_v2(
            run_id, document_id, pipeline_version, scope_code, status, finished_at)
        VALUES (%s, %s, 'preflight_v2', %s, 'completed', now())
        """,
        (run_id, document_id, _SCOPE_CODE),
    )
    return text_id, run_id


async def _insert_page_and_chunk(
    conn, tenant, scope_id, collection_id, text_id, run_id, document_id, label, marker
):
    await _run(
        conn,
        """
        INSERT INTO library_pages_v2(
            page_id, run_id, document_id, page_number, text, char_count,
            extraction_method, confidence, layout_notes)
        VALUES (%s, %s, %s, 1, %s, %s, 'synthetic', 1.0,
                jsonb_build_object('region_publication',
                    jsonb_build_object('page_status', 'FULL', 'marker', %s::text)))
        """,
        (uuid4(), run_id, document_id, marker, len(marker), marker),
    )
    await _run(
        conn,
        """
        INSERT INTO library_document_chunks(
            id, document_id, document_text_id, collection_id, chunk_index, chunk_uid,
            language, content, content_sha256, content_length, search_text_normalized,
            search_vector_es, search_vector_simple, page_start, page_end, citable,
            knowledge_scope_id, organization_id, workspace_id, project_id)
        VALUES (%s, %s, %s, %s, 0, %s, 'es', %s, %s, %s, %s,
                to_tsvector('spanish', %s), to_tsvector('simple', %s), 1, 1, true,
                %s, %s, %s, %s)
        """,
        (
            uuid4(),
            document_id,
            text_id,
            collection_id,
            f"{label}-chunk",
            marker,
            hashlib.sha256(marker.encode()).hexdigest(),
            len(marker),
            marker,
            marker,
            marker,
            scope_id,
            tenant["organization_id"],
            tenant["workspace_id"],
            tenant["project_id"],
        ),
    )


async def _register(conn, logical_id, document_id, run_id, status, label, source_sha):
    return await generation_module.register_generation(
        conn,
        logical_document_id=logical_id,
        document_id=document_id,
        pipeline_version=f"preflight_{label}_v1",
        source_sha256=source_sha,
        status=status,
        run_id=run_id,
    )


async def build_graph(conn, tenant, label, marker_prefix):
    scope_code = f"{_SCOPE_CODE}_{label}"
    collection_code = f"{_COLLECTION_CODE}_{label}"
    await _run(
        conn,
        """
        INSERT INTO knowledge_scopes(
            organization_id, workspace_id, project_id, knowledge_scope_code, name,
            description, scope_type, language_policy, status)
        VALUES (%(organization_id)s, %(workspace_id)s, %(project_id)s, %(scope)s,
                'Foundation V2 publication preflight scope',
                'isolated synthetic scope for the publication preflight harness',
                'bibliographic_corpus', 'es', 'active')
        """,
        {**tenant, "scope": scope_code},
    )
    scope_id = (
        await _fetchone(
            conn,
            "SELECT id FROM knowledge_scopes WHERE knowledge_scope_code=%s",
            (scope_code,),
        )
    )["id"]
    await _run(
        conn,
        """
        INSERT INTO library_collections_legacy(
            id, code, name, description, default_language, is_active)
        VALUES (gen_random_uuid(), %s, 'Foundation V2 preflight collection',
                'isolated synthetic collection', 'es', true)
        """,
        (collection_code,),
    )
    collection_id = (
        await _fetchone(
            conn,
            "SELECT id FROM library_collections_legacy WHERE code=%s",
            (collection_code,),
        )
    )["id"]

    # Approved source identity is unique per run: each run gets its own sha.
    source_sha = hashlib.sha256(f"{label}:{marker_prefix}".encode()).hexdigest()
    logical = await generation_module.ensure_logical_document(
        conn,
        collection_id=collection_id,
        knowledge_scope_id=scope_id,
        organization_id=tenant["organization_id"],
        workspace_id=tenant["workspace_id"],
        project_id=tenant["project_id"],
        title="Foundation V2 publication preflight synthetic document",
        source_sha256=source_sha,
        source_filename="preflight.pdf",
    )
    logical_id = logical["id"]

    nodes = {}
    for key, marker, status_value in (
        ("old", f"{marker_prefix}{OLD_MARKER}", GENERATION_ACTIVE),
        ("new", f"{marker_prefix}{NEW_MARKER}", GENERATION_CANDIDATE),
        ("alt", f"{marker_prefix}{ALT_MARKER}", GENERATION_CANDIDATE),
    ):
        document_id = uuid4()
        text_id, run_id = await _insert_document(
            conn, tenant, scope_id, collection_id, document_id, key, marker, source_sha
        )
        gen = await _register(
            conn, logical_id, document_id, run_id, status_value, key, source_sha
        )
        await _insert_page_and_chunk(
            conn,
            tenant,
            scope_id,
            collection_id,
            text_id,
            run_id,
            document_id,
            key,
            marker,
        )
        nodes[key] = {
            "document_id": str(document_id),
            "run_id": str(run_id),
            "generation_id": str(gen["id"]),
            "status": status_value,
            "marker": marker,
        }

    # A never-active INACTIVE generation for the negative controls.
    inactive_document_id = uuid4()
    inactive_text, inactive_run = await _insert_document(
        conn,
        tenant,
        scope_id,
        collection_id,
        inactive_document_id,
        "inactive",
        f"{marker_prefix}PREFLIGHTV2INACTIVEEV",
        source_sha,
    )
    inactive_gen = await _register(
        conn,
        logical_id,
        inactive_document_id,
        inactive_run,
        GENERATION_INACTIVE,
        "inactive",
        source_sha,
    )
    await _insert_page_and_chunk(
        conn,
        tenant,
        scope_id,
        collection_id,
        inactive_text,
        inactive_run,
        inactive_document_id,
        "inactive",
        f"{marker_prefix}PREFLIGHTV2INACTIVEEV",
    )
    nodes["inactive"] = {
        "document_id": str(inactive_document_id),
        "run_id": str(inactive_run),
        "generation_id": str(inactive_gen["id"]),
        "status": GENERATION_INACTIVE,
        "marker": f"{marker_prefix}PREFLIGHTV2INACTIVEEV",
    }

    await _run(
        conn,
        """
        INSERT INTO library_logical_document_active_generations(
            logical_document_id, generation_id, expected_generation_id, operation)
        VALUES (%s, %s, %s, 'BACKFILL')
        """,
        (logical_id, nodes["old"]["generation_id"], nodes["old"]["generation_id"]),
    )
    await _run(
        conn,
        """
        INSERT INTO library_generation_activation_audit(
            logical_document_id, from_generation_id, to_generation_id,
            expected_generation_id, operation, result, reason)
        VALUES (%s, NULL, %s, %s, 'BACKFILL', 'APPLIED',
                'publication preflight: deterministic backfill')
        """,
        (logical_id, nodes["old"]["generation_id"], nodes["old"]["generation_id"]),
    )
    return {
        "scope_code": scope_code,
        "collection_code": collection_code,
        "scope_id": str(scope_id),
        "collection_id": str(collection_id),
        "logical_id": str(logical_id),
        "source_sha256": source_sha,
        "nodes": nodes,
    }


async def _state(conn, graph) -> dict:
    rows = await (await conn.execute(
        "SELECT id, status FROM library_document_generations WHERE logical_document_id=%s",
        (graph["logical_id"],),
    )).fetchall()
    pointer = await _fetchone(
        conn,
        """
        SELECT generation_id, expected_generation_id, operation
        FROM library_logical_document_active_generations WHERE logical_document_id=%s
        """,
        (graph["logical_id"],),
    )
    visible = await resolve_active_document_ids(
        conn, knowledge_scope_code=graph["scope_code"]
    )
    return {
        "statuses": {str(r["id"]): r["status"] for r in rows},
        "pointer": str(pointer["generation_id"]) if pointer else None,
        "pointer_expected": str(pointer["expected_generation_id"]) if pointer else None,
        "visible_documents": visible,
    }


def _rejected(exc: Exception) -> dict:
    return {
        "outcome": "REJECTED",
        "exception": type(exc).__name__,
        "message": str(exc),
    }


async def negative_controls(conn, graph) -> list[dict]:
    nodes = graph["nodes"]
    logical = graph["logical_id"]
    results: list[dict] = []

    async def attempt(name, fn):
        try:
            async with conn.transaction():
                value = await fn()
            results.append(
                {"control": name, "outcome": "ACCEPTED", "value": value}
            )
        except (GenerationConflictError, GenerationPreconditionError) as exc:
            results.append({"control": name, **_rejected(exc)})
        except psycopg.Error as exc:
            results.append(
                {
                    "control": name,
                    "outcome": "REJECTED_BY_DATABASE",
                    "exception": type(exc).__name__,
                    "sqlstate": exc.sqlstate,
                    "message": str(exc),
                }
            )

    # BUILDING and FAILED targets are not switchable.
    for status_value in (GENERATION_BUILDING, GENERATION_FAILED):
        await _run(
            conn,
            "UPDATE library_document_generations SET status=%s WHERE id=%s",
            (status_value, nodes["alt"]["generation_id"]),
        )
        await attempt(
            f"cutover_target_{status_value.lower()}",
            lambda: activate_generation(
                conn,
                logical_document_id=logical,
                expected_active_generation_id=nodes["old"]["generation_id"],
                new_generation_id=nodes["alt"]["generation_id"],
                operation=OPERATION_CUTOVER,
            ),
        )
    await set_generation_status(
        conn, nodes["alt"]["generation_id"], GENERATION_CANDIDATE
    )

    # Arbitrary INACTIVE target for CUTOVER.
    await attempt(
        "cutover_target_arbitrary_inactive",
        lambda: activate_generation(
            conn,
            logical_document_id=logical,
            expected_active_generation_id=nodes["old"]["generation_id"],
            new_generation_id=nodes["inactive"]["generation_id"],
            operation=OPERATION_CUTOVER,
        ),
    )
    # Never-active INACTIVE target for ROLLBACK.
    await attempt(
        "rollback_target_never_active_inactive",
        lambda: activate_generation(
            conn,
            logical_document_id=logical,
            expected_active_generation_id=nodes["old"]["generation_id"],
            new_generation_id=nodes["inactive"]["generation_id"],
            operation=OPERATION_ROLLBACK,
        ),
    )
    # Stale CAS and stale rollback.
    await attempt(
        "stale_expected_active_generation",
        lambda: activate_generation(
            conn,
            logical_document_id=logical,
            expected_active_generation_id=nodes["new"]["generation_id"],
            new_generation_id=nodes["alt"]["generation_id"],
            operation=OPERATION_CUTOVER,
        ),
    )
    await attempt(
        "stale_rollback",
        lambda: activate_generation(
            conn,
            logical_document_id=logical,
            expected_active_generation_id=nodes["alt"]["generation_id"],
            new_generation_id=nodes["new"]["generation_id"],
            operation=OPERATION_ROLLBACK,
        ),
    )

    # Cross-document pointer: another logical document pointing at this
    # generation must be rejected by the composite foreign key.
    other = await _fetchone(
        conn,
        """
        INSERT INTO library_logical_documents(
            collection_id, knowledge_scope_id, organization_id, workspace_id,
            project_id, title, source_sha256)
        SELECT collection_id, knowledge_scope_id, organization_id, workspace_id,
               project_id, 'Foundation V2 preflight cross-document probe', %s
        FROM library_logical_documents WHERE id=%s
        RETURNING id
        """,
        ("e" * 64, logical),
    )
    try:
        async with conn.transaction():
            await _run(
                conn,
                """
                INSERT INTO library_logical_document_active_generations(
                    logical_document_id, generation_id, expected_generation_id, operation)
                VALUES (%s, %s, %s, 'BACKFILL')
                """,
                (other["id"], nodes["old"]["generation_id"], nodes["old"]["generation_id"]),
            )
        results.append({"control": "cross_document_pointer", "outcome": "ACCEPTED"})
    except psycopg.Error as exc:
        results.append(
            {
                "control": "cross_document_pointer",
                "outcome": "REJECTED_BY_DATABASE",
                "exception": type(exc).__name__,
                "sqlstate": exc.sqlstate,
                "constraint": "library_logical_document_active_generations_generation_fkey",
                "message": str(exc),
            }
        )

    # Non-immediate historical INACTIVE: after A -> alt, republish NEW as a
    # candidate and switch alt -> NEW. Rolling back to OLD now targets a retained
    # generation that is no longer the immediate predecessor.
    async with conn.transaction():
        await activate_generation(
            conn,
            logical_document_id=logical,
            expected_active_generation_id=nodes["old"]["generation_id"],
            new_generation_id=nodes["alt"]["generation_id"],
            operation=OPERATION_CUTOVER,
        )
    await set_generation_status(conn, nodes["new"]["generation_id"], GENERATION_CANDIDATE)
    async with conn.transaction():
        await activate_generation(
            conn,
            logical_document_id=logical,
            expected_active_generation_id=nodes["alt"]["generation_id"],
            new_generation_id=nodes["new"]["generation_id"],
            operation=OPERATION_CUTOVER,
        )
    await attempt(
        "rollback_target_non_immediate_historical",
        lambda: activate_generation(
            conn,
            logical_document_id=logical,
            expected_active_generation_id=nodes["new"]["generation_id"],
            new_generation_id=nodes["old"]["generation_id"],
            operation=OPERATION_ROLLBACK,
        ),
    )

    await conn.commit()
    await _run(conn, "DELETE FROM library_logical_documents WHERE id=%s", (other["id"],))
    await conn.commit()
    return results


async def cleanup(conn, graph) -> dict:
    logical = graph["logical_id"]
    await _run(
        conn,
        "DELETE FROM library_logical_document_active_generations WHERE logical_document_id=%s",
        (logical,),
    )
    await _run(
        conn,
        "DELETE FROM library_generation_activation_audit WHERE logical_document_id=%s",
        (logical,),
    )
    await _run(
        conn,
        "DELETE FROM library_document_generations WHERE logical_document_id=%s",
        (logical,),
    )
    document_ids = [n["document_id"] for n in graph["nodes"].values()]
    for document_id in document_ids:
        for table in ("library_document_chunks", "library_pages_v2", "library_document_texts"):
            await _run(conn, f"DELETE FROM {table} WHERE document_id=%s", (document_id,))
    for document_id in document_ids:
        await _run(conn, "DELETE FROM library_documents WHERE id=%s", (document_id,))
    for document_id in document_ids:
        await _run(conn, "DELETE FROM library_ingestion_runs_v2 WHERE document_id=%s", (document_id,))
    await _run(conn, "DELETE FROM library_logical_documents WHERE id=%s", (logical,))
    await _run(
        conn,
        "DELETE FROM library_collections_legacy WHERE code=%s",
        (graph["collection_code"],),
    )
    await _run(
        conn,
        "DELETE FROM knowledge_scopes WHERE knowledge_scope_code=%s",
        (graph["scope_code"],),
    )
    await conn.commit()

    remaining = {}
    checks = {
        "knowledge_scopes": ("SELECT count(*) FROM knowledge_scopes WHERE knowledge_scope_code=%s", (graph["scope_code"],)),
        "library_collections_legacy": ("SELECT count(*) FROM library_collections_legacy WHERE code=%s", (graph["collection_code"],)),
        "library_logical_documents": ("SELECT count(*) FROM library_logical_documents WHERE id=%s", (logical,)),
        "library_documents": ("SELECT count(*) FROM library_documents WHERE logical_document_id=%s", (logical,)),
        "library_document_generations": ("SELECT count(*) FROM library_document_generations WHERE logical_document_id=%s", (logical,)),
        "library_logical_document_active_generations": ("SELECT count(*) FROM library_logical_document_active_generations WHERE logical_document_id=%s", (logical,)),
        "library_generation_activation_audit": ("SELECT count(*) FROM library_generation_activation_audit WHERE logical_document_id=%s", (logical,)),
        "library_document_chunks": ("SELECT count(*) FROM library_document_chunks WHERE document_id = ANY(%s::uuid[])", (document_ids,)),
        "library_pages_v2": ("SELECT count(*) FROM library_pages_v2 WHERE document_id = ANY(%s::uuid[])", (document_ids,)),
        "library_ingestion_runs_v2": ("SELECT count(*) FROM library_ingestion_runs_v2 WHERE document_id = ANY(%s::uuid[])", (document_ids,)),
        "library_document_texts": ("SELECT count(*) FROM library_document_texts WHERE document_id = ANY(%s::uuid[])", (document_ids,)),
    }
    for name, (sql, params) in checks.items():
        row = await _fetchone(conn, sql, params)
        remaining[name] = list(row.values())[0]
    return {"remaining": remaining, "clean": all(v == 0 for v in remaining.values())}


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("out")
    parser.add_argument("--label", required=True)
    args = parser.parse_args()

    assert config.TEBAAI_ENV == "development", "preflight requires the DEV database"
    assert not config.is_tebaai_production()
    assert config.POSTGRES_HOST in {"127.0.0.1", "localhost"}

    out_path = Path(args.out)
    global _SCOPE_CODE, _COLLECTION_CODE
    _SCOPE_CODE = f"gen_publication_preflight_v2_{args.label}_{uuid4().hex[:8]}"
    _COLLECTION_CODE = _SCOPE_CODE

    report: dict[str, Any] = {
        "harness": "foundation_v2_publication_preflight",
        "label": args.label,
        "run_suffix": _SCOPE_CODE,
        "database": "tebaai",
        "fixture_errors": [],
        "fk_errors": [],
        "binding_errors": [],
        "indeterminate_datatype_errors": [],
        "setup_errors": [],
        "cleanup_errors": [],
    }

    conn = await AsyncConnection.connect(
        config.POSTGRES_DSN, row_factory=dict_row, connect_timeout=5
    )
    graph = None
    try:
        async with conn.transaction():
            tenant = await _fetchone(
                conn,
                """
                SELECT organization_id, workspace_id, project_id
                FROM knowledge_scopes WHERE knowledge_scope_code='breslov_primary'
                """,
            )
            assert tenant, "the primary scope is required as tenant template"
            graph = await build_graph(
                conn, tenant, args.label, uuid4().hex[:6]
            )
        report["fixture_identifier"] = {
            "scope_code": graph["scope_code"],
            "collection_code": graph["collection_code"],
            "logical_document_id": graph["logical_id"],
            "source_sha256": graph["source_sha256"],
            "nodes": graph["nodes"],
        }
        _log("fixture_created", logical_id=graph["logical_id"])

        async with conn.transaction():
            initial = await _state(conn, graph)
        report["initial"] = initial
        report["initial_ok"] = (
            initial["statuses"][graph["nodes"]["old"]["generation_id"]] == GENERATION_ACTIVE
            and initial["statuses"][graph["nodes"]["new"]["generation_id"]] == GENERATION_CANDIDATE
            and initial["pointer"] == graph["nodes"]["old"]["generation_id"]
            and initial["visible_documents"] == [graph["nodes"]["old"]["document_id"]]
        )
        if not report["initial_ok"]:
            report["setup_errors"].append("initial_state_mismatch")

        cutover = {}
        try:
            async with conn.transaction():
                cutover = await activate_generation(
                    conn,
                    logical_document_id=graph["logical_id"],
                    expected_active_generation_id=graph["nodes"]["old"]["generation_id"],
                    new_generation_id=graph["nodes"]["new"]["generation_id"],
                    operation=OPERATION_CUTOVER,
                )
            async with conn.transaction():
                after_cutover = await _state(conn, graph)
            cutover.update(
                {
                    "after": after_cutover,
                    "ok": (
                        cutover.get("result") == "APPLIED"
                        and after_cutover["statuses"][graph["nodes"]["old"]["generation_id"]] == GENERATION_INACTIVE
                        and after_cutover["statuses"][graph["nodes"]["new"]["generation_id"]] == GENERATION_ACTIVE
                        and after_cutover["pointer"] == graph["nodes"]["new"]["generation_id"]
                        and after_cutover["visible_documents"] == [graph["nodes"]["new"]["document_id"]]
                    ),
                }
            )
        except Exception as exc:  # noqa: BLE001
            report["setup_errors"].append(f"cutover:{type(exc).__name__}:{exc}")
            cutover = {"result": "EXCEPTION", "message": str(exc)}
        report["cutover"] = cutover
        _log("cutover", result=cutover.get("result"))

        rollback = {}
        try:
            async with conn.transaction():
                rollback = await activate_generation(
                    conn,
                    logical_document_id=graph["logical_id"],
                    expected_active_generation_id=graph["nodes"]["new"]["generation_id"],
                    new_generation_id=graph["nodes"]["old"]["generation_id"],
                    operation=OPERATION_ROLLBACK,
                )
            async with conn.transaction():
                after_rollback = await _state(conn, graph)
            rollback.update(
                {
                    "after": after_rollback,
                    "ok": (
                        rollback.get("result") == "APPLIED"
                        and after_rollback["statuses"][graph["nodes"]["new"]["generation_id"]] == GENERATION_INACTIVE
                        and after_rollback["statuses"][graph["nodes"]["old"]["generation_id"]] == GENERATION_ACTIVE
                        and after_rollback["pointer"] == graph["nodes"]["old"]["generation_id"]
                        and after_rollback["visible_documents"] == [graph["nodes"]["old"]["document_id"]]
                    ),
                }
            )
        except Exception as exc:  # noqa: BLE001
            report["setup_errors"].append(f"rollback:{type(exc).__name__}:{exc}")
            rollback = {"result": "EXCEPTION", "message": str(exc)}
        report["rollback"] = rollback
        _log("rollback", result=rollback.get("result"))

        report["negative_controls"] = await negative_controls(conn, graph)
        report["negative_controls_ok"] = all(
            item["outcome"].startswith("REJECTED")
            for item in report["negative_controls"]
        )
        _log("negative_controls", ok=report["negative_controls_ok"])

        report["cleanup"] = await cleanup(conn, graph)
        if not report["cleanup"]["clean"]:
            report["cleanup_errors"].append("synthetic_rows_remaining")
        _log("cleanup", clean=report["cleanup"]["clean"])
    except Exception as exc:  # noqa: BLE001
        report["fixture_errors"].append(f"{type(exc).__name__}: {exc}")
        if isinstance(exc, psycopg.errors.IndeterminateDatatype):
            report["indeterminate_datatype_errors"].append(str(exc))
        elif isinstance(exc, psycopg.errors.ForeignKeyViolation):
            report["fk_errors"].append(str(exc))
        elif isinstance(exc, psycopg.errors.ProgrammingError):
            report["binding_errors"].append(str(exc))
        try:
            await conn.rollback()
        except Exception:  # noqa: BLE001
            pass
        if graph is not None:
            try:
                report["cleanup"] = await cleanup(conn, graph)
            except Exception as cleanup_exc:  # noqa: BLE001
                report["cleanup_errors"].append(f"{type(cleanup_exc).__name__}: {cleanup_exc}")
    finally:
        await conn.close()

    report["counts"] = {
        "fixture_errors": len(report["fixture_errors"]),
        "fk_errors": len(report["fk_errors"]),
        "binding_errors": len(report["binding_errors"]),
        "indeterminate_datatype_errors": len(report["indeterminate_datatype_errors"]),
        "setup_errors": len(report["setup_errors"]),
        "cleanup_errors": len(report["cleanup_errors"]),
    }
    report["ok"] = (
        all(v == 0 for v in report["counts"].values())
        and report.get("initial_ok") is True
        and report.get("cutover", {}).get("ok") is True
        and report.get("rollback", {}).get("ok") is True
        and report.get("negative_controls_ok") is True
        and report.get("cleanup", {}).get("clean") is True
    )
    out_path.write_text(
        json.dumps(report, indent=2, default=str, allow_nan=False) + "\n"
    )
    print(json.dumps({"ok": report["ok"], "counts": report["counts"]}, indent=2))
    return 0 if report["ok"] else 1


_SCOPE_CODE = ""
_COLLECTION_CODE = ""


if __name__ == "__main__":
    raise SystemExit(__import__("asyncio").run(main()))
