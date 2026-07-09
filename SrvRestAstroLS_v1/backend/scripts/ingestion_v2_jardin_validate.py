#!/usr/bin/env python3
"""Ingestion V2 validation — El Jardín de las Almas. Read-only."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool

REPORT = Path(__file__).resolve().parent.parent.parent.parent / "data/reports/breslov/2026-07-09-ingestion-v2-jardin-sql-pilot"
ACID_PAGES = [36, 42, 280, 384, 389, 408, 437, 438]


def _v(row, idx=0):
    """Get value from psycopg row (tolerates dict-like or tuple-like)."""
    if row is None:
        return None
    if isinstance(row, dict):
        keys = list(row.keys())
        return row[keys[idx]]
    return row[idx]


async def fetch_val(cur, sql: str):
    await cur.execute(sql)
    return _v(await cur.fetchone())


async def main() -> int:
    pool = create_pool_from_settings()
    await open_pool(pool)

    results = {}

    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                # 1. Tables exist
                tables = [
                    "library_ingestion_runs_v2", "library_pages_v2", "library_sections_v2",
                    "library_concept_mentions_v2", "library_source_references_v2",
                    "library_internal_relations_v2", "library_document_wiki_v2",
                ]
                for t in tables:
                    await cur.execute(f"SELECT to_regclass('public.{t}') AS klass")
                    exists = _v(await cur.fetchone()) is not None
                    results[f"table_{t}"] = "exists" if exists else "MISSING"
                    if not exists:
                        print(f"  FAIL: Table {t} does not exist")

                # 2. Runs
                run_count = await fetch_val(cur, "SELECT count(*) FROM library_ingestion_runs_v2")
                results["runs_count"] = run_count
                print(f"  Runs: {run_count}")

                if run_count > 0:
                    await cur.execute("SELECT run_id, document_id, status, metrics_json FROM library_ingestion_runs_v2 ORDER BY created_at DESC LIMIT 1")
                    row = await cur.fetchone()
                    results["last_run"] = {
                        "run_id": str(_v(row, 0)), "document_id": str(_v(row, 1)),
                        "status": str(_v(row, 2)),
                        "metrics": json.loads(_v(row, 3)) if isinstance(_v(row, 3), str) else _v(row, 3),
                    }
                    print(f"  Last run: {_v(row, 2)}")

                # 3. Pages
                pages = await fetch_val(cur, "SELECT count(*) FROM library_pages_v2")
                results["pages_count"] = pages
                print(f"  Pages: {pages}")

                if pages and pages > 0:
                    await cur.execute("SELECT page_number FROM library_pages_v2 ORDER BY page_number")
                    rows = await cur.fetchall()
                    page_nums = [_v(r) for r in rows]
                    results["pages_numbers"] = page_nums[:50]
                    found_acid = [p for p in ACID_PAGES if p in page_nums]
                    missing_acid = [p for p in ACID_PAGES if p not in page_nums]
                    results["acid_pages_found"] = found_acid
                    results["acid_pages_missing"] = missing_acid
                    print(f"  Acid pages found: {len(found_acid)}/{len(ACID_PAGES)} {found_acid}")
                    if missing_acid:
                        print(f"  Acid pages missing: {missing_acid}")

                # 4. Sections
                sections = await fetch_val(cur, "SELECT count(*) FROM library_sections_v2")
                results["sections_count"] = sections
                print(f"  Sections: {sections}")

                if sections and sections > 0:
                    await cur.execute("SELECT title FROM library_sections_v2 ORDER BY order_index LIMIT 20")
                    rows = await cur.fetchall()
                    results["section_titles"] = [_v(r) for r in rows]

                # 5. Concepts
                concepts = await fetch_val(cur, "SELECT count(*) FROM library_concept_mentions_v2")
                results["concepts_count"] = concepts
                print(f"  Concepts: {concepts}")

                if concepts and concepts > 0:
                    await cur.execute("SELECT label FROM library_concept_mentions_v2 ORDER BY label")
                    rows = await cur.fetchall()
                    results["concept_labels"] = [_v(r) for r in rows]

                # 6. Source references
                src_refs = await fetch_val(cur, "SELECT count(*) FROM library_source_references_v2")
                results["source_refs_count"] = src_refs
                print(f"  Source refs: {src_refs}")

                if src_refs and src_refs > 0:
                    await cur.execute("SELECT source_type FROM library_source_references_v2 ORDER BY source_type")
                    rows = await cur.fetchall()
                    results["source_types"] = [_v(r) for r in rows]

                # 7. Relations
                rels = await fetch_val(cur, "SELECT count(*) FROM library_internal_relations_v2")
                results["relations_count"] = rels
                print(f"  Relations: {rels}")

                if rels and rels > 0:
                    await cur.execute("SELECT concept_a, concept_b, relation_type FROM library_internal_relations_v2 ORDER BY concept_a")
                    rows = await cur.fetchall()
                    results["relations"] = [(_v(r, 0), _v(r, 1), _v(r, 2)) for r in rows]

                # 8. Wiki
                wiki_count = await fetch_val(cur, "SELECT count(*) FROM library_document_wiki_v2")
                results["wiki_count"] = wiki_count
                print(f"  Wiki entries: {wiki_count}")

                # Overall
                errors = [k for k, v in results.items() if k.startswith("table_") and v == "MISSING"]
                if errors:
                    results["overall"] = "FAIL"
                elif pages == 0:
                    results["overall"] = "WARN"
                elif sections == 0 and concepts == 0:
                    results["overall"] = "WARN"
                else:
                    results["overall"] = "PASS"
                print(f"\n  OVERALL: {results['overall']}")

    finally:
        await close_pool(pool)

    REPORT.mkdir(parents=True, exist_ok=True)
    (REPORT / "validation.json").write_text(json.dumps(results, indent=2, default=str, ensure_ascii=False))
    return 0 if results.get("overall") != "FAIL" else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
