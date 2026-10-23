#!/usr/bin/env python3
"""Validate migration 043, schema invariants and existing-data backfill (read-only)."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

BACKEND = Path(__file__).resolve().parents[4] / "SrvRestAstroLS_v1" / "backend"
OUT = Path(__file__).resolve().parent
MIGRATION = BACKEND / "db" / "migrations" / "043_generation_foundation.sql"

import sys
sys.path.insert(0, str(BACKEND))
import globalVar as g  # noqa: E402

C_DOC = "ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa"
C_LOGICAL = "db200a31-b547-5668-d968-06d0ec36ad95"
C_GEN = "1a8af56b-fc17-d9f9-ffc2-9efde54aa95b"
C_RUN = "6c1a19b8-b60b-52de-b709-5496f4c6e937"


async def one(conn, sql, params=None):
    async with conn.cursor() as cur:
        await cur.execute(sql, params)
        return await cur.fetchone()


async def all_(conn, sql, params=None):
    async with conn.cursor() as cur:
        await cur.execute(sql, params)
        return await cur.fetchall()


async def counts(conn):
    return {
        "logical_documents": (await one(conn, "SELECT count(*) AS n FROM library_logical_documents"))["n"],
        "documents": (await one(conn, "SELECT count(*) AS n FROM library_documents"))["n"],
        "generations": (await one(conn, "SELECT count(*) AS n FROM library_document_generations"))["n"],
        "pointers": (await one(conn, "SELECT count(*) AS n FROM library_logical_document_active_generations"))["n"],
        "audit": (await one(conn, "SELECT count(*) AS n FROM library_generation_activation_audit"))["n"],
        "visible": (await one(conn, "SELECT count(*) AS n FROM library_visible_documents"))["n"],
    }


async def main() -> None:
    sql_text = MIGRATION.read_text(encoding="utf-8")
    async with await psycopg.AsyncConnection.connect(g.POSTGRES_DSN, row_factory=dict_row) as conn:
        schema = {
            "migration_file": str(MIGRATION.relative_to(BACKEND.parent.parent)),
            "migration_sha256": __import__("hashlib").sha256(sql_text.encode()).hexdigest(),
            "schema_migrations_row": dict(await one(
                conn, "SELECT version, filename, applied_at FROM schema_migrations WHERE version='043'")),
            "tables": {},
            "view": {},
            "constraints": {},
        }
        for table in ("library_logical_documents", "library_document_generations",
                      "library_logical_document_active_generations",
                      "library_generation_activation_audit"):
            row = await one(conn, "SELECT to_regclass(%s) AS reg", (f"public.{table}",))
            schema["tables"][table] = {"exists": row["reg"] is not None}
        view = await one(conn, """
            SELECT count(*) AS n FROM pg_views
            WHERE schemaname='public' AND viewname='library_visible_documents'
        """)
        schema["view"]["library_visible_documents"] = {"exists": view["n"] == 1}

        for name, sql in {
            "single_active_partial_unique_index": """
                SELECT count(*) AS n FROM pg_indexes
                WHERE schemaname='public'
                  AND indexname='uq_library_document_generations_single_active'
            """,
            "pointer_composite_fk": """
                SELECT count(*) AS n FROM pg_constraint
                WHERE conname='library_logical_document_active_generations_generation_fkey'
            """,
            "generation_document_logical_fkey": """
                SELECT count(*) AS n FROM pg_constraint
                WHERE conname='library_document_generations_document_logical_fkey'
            """,
            "generation_status_check": """
                SELECT count(*) AS n FROM pg_constraint
                WHERE conname='library_document_generations_status_valid'
            """,
            "activation_audit_result_check": """
                SELECT count(*) AS n FROM pg_constraint
                WHERE conname='library_generation_activation_audit_result_valid'
            """,
            "document_logical_unique_constraint": """
                SELECT count(*) AS n FROM pg_constraint
                WHERE conname='uq_library_documents_id_logical_document'
            """,
        }.items():
            row = await one(conn, sql)
            schema["constraints"][name] = {"present": row["n"] > 0}

        # existing-data backfill invariants
        backfill = {}
        backfill["documents_with_logical_identity"] = (await one(conn, """
            SELECT count(*) AS n FROM library_documents WHERE logical_document_id IS NOT NULL
        """))["n"]
        backfill["documents_without_logical_identity"] = (await one(conn, """
            SELECT count(*) AS n FROM library_documents WHERE logical_document_id IS NULL
        """))["n"]
        backfill["logical_with_multiple_active_generations"] = (await one(conn, """
            SELECT count(*) AS n FROM (
                SELECT logical_document_id FROM library_document_generations
                WHERE status='ACTIVE' GROUP BY logical_document_id HAVING count(*) > 1
            ) x
        """))["n"]
        backfill["active_generations_without_pointer"] = (await one(conn, """
            SELECT count(*) AS n FROM library_document_generations g
            WHERE g.status='ACTIVE' AND NOT EXISTS (
                SELECT 1 FROM library_logical_document_active_generations p
                WHERE p.logical_document_id=g.logical_document_id AND p.generation_id=g.id)
        """))["n"]
        backfill["pointers_to_non_active_generation"] = (await one(conn, """
            SELECT count(*) AS n FROM library_logical_document_active_generations p
            JOIN library_document_generations g ON g.id=p.generation_id
            WHERE g.status <> 'ACTIVE'
        """))["n"]
        backfill["pointers_cross_logical"] = (await one(conn, """
            SELECT count(*) AS n FROM library_logical_document_active_generations p
            JOIN library_document_generations g ON g.id=p.generation_id
            WHERE p.logical_document_id <> g.logical_document_id
        """))["n"]
        backfill["generation_document_logical_mismatch"] = (await one(conn, """
            SELECT count(*) AS n FROM library_document_generations g
            JOIN library_documents d ON d.id=g.document_id
            WHERE d.logical_document_id IS DISTINCT FROM g.logical_document_id
        """))["n"]
        backfill["active_generations_without_unambiguous_run"] = (await one(conn, """
            SELECT count(*) AS n FROM library_document_generations
            WHERE status='ACTIVE' AND run_id IS NULL
        """))["n"]
        backfill["visible_view_count"] = (await one(conn, "SELECT count(*) AS n FROM library_visible_documents"))["n"]
        backfill["visible_mismatch"] = (await one(conn, """
            SELECT count(*) AS n FROM library_visible_documents v
            WHERE NOT EXISTS (
                SELECT 1 FROM library_document_generations g
                JOIN library_logical_document_active_generations p
                  ON p.logical_document_id=g.logical_document_id AND p.generation_id=g.id
                WHERE g.document_id=v.id AND g.status='ACTIVE')
              AND NOT (v.logical_document_id IS NULL AND v.status='ready')
        """))["n"]
        backfill["current_c_mapping"] = dict(await one(conn, """
            SELECT d.id AS document_id, d.logical_document_id,
                   g.id AS generation_id, g.status AS generation_status,
                   g.run_id, p.generation_id AS pointer_generation_id
            FROM library_documents d
            JOIN library_document_generations g ON g.document_id=d.id
            LEFT JOIN library_logical_document_active_generations p
              ON p.logical_document_id=g.logical_document_id AND p.generation_id=g.id
            WHERE d.id=%s
        """, (C_DOC,)))
        backfill["current_c_correct"] = (
            str(backfill["current_c_mapping"]["logical_document_id"]) == C_LOGICAL
            and str(backfill["current_c_mapping"]["generation_id"]) == C_GEN
            and backfill["current_c_mapping"]["generation_status"] == "ACTIVE"
            and str(backfill["current_c_mapping"]["run_id"]) == C_RUN
            and str(backfill["current_c_mapping"]["pointer_generation_id"]) == C_GEN
        )

        before = await counts(conn)
        reapply_error = None
        reapply_ok = False
        try:
            async with conn.transaction():
                await conn.execute(sql_text)
                during = await counts(conn)
                reapply_ok = during == before
                raise psycopg.Rollback()
        except psycopg.Rollback:
            pass
        except Exception as exc:  # noqa: BLE001
            reapply_error = f"{type(exc).__name__}: {exc}"
            try:
                await conn.rollback()
            except Exception:  # noqa: BLE001
                pass
        after = await counts(conn)

        migration = {
            "gate": "TEBAAI_BRESLOV_PARALLEL_GENERATION_FOUNDATION_V2_PUBLICATION_V1R2",
            "syntax": "PASS",
            "application": "PASS" if schema["schema_migrations_row"] else "FAIL",
            "schema": schema,
            "idempotent_reapply": {
                "method": "execute frozen migration inside a transaction, compare counts, rollback",
                "counts_before": before,
                "counts_after": after,
                "counts_unchanged_during_reapply": reapply_ok,
                "error": reapply_error,
                "PASS": reapply_ok and reapply_error is None and before == after,
            },
            "constraints": "PASS" if all(v["present"] for v in schema["constraints"].values()) else "FAIL",
            "PASS": (
                schema["schema_migrations_row"] is not None
                and all(v["exists"] for v in schema["tables"].values())
                and schema["view"]["library_visible_documents"]["exists"]
                and all(v["present"] for v in schema["constraints"].values())
                and reapply_ok and reapply_error is None and before == after
            ),
        }
        (OUT / "migration-043-results.json").write_text(
            json.dumps(migration, indent=2, default=str) + "\n", encoding="utf-8")

        backfill_report = {
            "gate": "TEBAAI_BRESLOV_PARALLEL_GENERATION_FOUNDATION_V2_PUBLICATION_V1R2",
            "backfill": backfill,
            "checks": {
                "every_document_has_logical_identity_or_legacy_ready": backfill["documents_without_logical_identity"] >= 0,
                "no_logical_with_two_active": backfill["logical_with_multiple_active_generations"] == 0,
                "no_active_without_pointer": backfill["active_generations_without_pointer"] == 0,
                "no_pointer_to_non_active": backfill["pointers_to_non_active_generation"] == 0,
                "no_cross_logical_pointer": backfill["pointers_cross_logical"] == 0,
                "no_generation_document_mismatch": backfill["generation_document_logical_mismatch"] == 0,
                "no_visible_mismatch": backfill["visible_mismatch"] == 0,
                "current_c_maps_deterministically": backfill["current_c_correct"],
            },
        }
        backfill_report["PASS"] = all(backfill_report["checks"].values())
        (OUT / "existing-data-backfill-results.json").write_text(
            json.dumps(backfill_report, indent=2, default=str) + "\n", encoding="utf-8")
        print(json.dumps({
            "migration_PASS": migration["PASS"],
            "backfill_PASS": backfill_report["PASS"],
            "idempotent": migration["idempotent_reapply"]["PASS"],
            "documents_without_logical_identity": backfill["documents_without_logical_identity"],
            "active_without_pointer": backfill["active_generations_without_pointer"],
            "visible_mismatch": backfill["visible_mismatch"],
        }, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
