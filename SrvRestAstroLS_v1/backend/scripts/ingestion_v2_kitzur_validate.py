#!/usr/bin/env python3
"""Ingestion V2 validation — KITZUR CreateSpace. Read-only."""

from __future__ import annotations

import argparse, asyncio, json, sys
from pathlib import Path

from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool

QUERY_CONCEPTS = ["alegría", "plegaria", "sangre", "habla", "hitbodedut", "emuná"]
QUERY_RELATIONS = [("alegría", "plegaria"), ("sangre", "habla"), ("hitbodedut", "plegaria")]


def _v(row, idx=0):
    if row is None:
        return None
    if isinstance(row, dict):
        keys = list(row.keys())
        return row[keys[idx]]
    return row[idx]


async def main() -> int:
    parser = argparse.ArgumentParser(description="KITZUR CreateSpace Ingestion V2 Validation")
    parser.add_argument("--run-id", required=True, help="Run UUID to validate")
    parser.add_argument("--report-dir", required=True, type=Path)
    args = parser.parse_args()

    report_dir = args.report_dir
    report_dir.mkdir(parents=True, exist_ok=True)
    results = {}

    pool = create_pool_from_settings()
    await open_pool(pool)

    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                rid = args.run_id

                # 1. Run exists
                await cur.execute("SELECT status, document_id, scope_code, pipeline_version, metrics_json, warnings_json FROM library_ingestion_runs_v2 WHERE run_id = %s", (rid,))
                row = await cur.fetchone()
                if not row:
                    print("FAIL: Run not found"); return 1
                status = _v(row, 0)
                doc_id = _v(row, 1)
                metrics = json.loads(_v(row, 4)) if isinstance(_v(row, 4), str) else _v(row, 4) or {}
                warnings_list = json.loads(_v(row, 5)) if isinstance(_v(row, 5), str) else _v(row, 5) or []
                results["run_status"] = status
                results["document_id"] = doc_id
                results["metrics"] = metrics
                results["warnings"] = warnings_list
                print(f"  Run: {rid[:8]}... status={status} doc={str(doc_id)[:12]}...")

                # 2. Pages
                await cur.execute("SELECT count(*) FROM library_pages_v2 WHERE run_id = %s", (rid,))
                pages = _v(await cur.fetchone())
                await cur.execute("SELECT count(*) FROM library_pages_v2 WHERE run_id = %s AND char_count > 0", (rid,))
                pages_with_text = _v(await cur.fetchone())
                results["pages_total"] = pages
                results["pages_with_text"] = pages_with_text
                print(f"  Pages: {pages} total, {pages_with_text} with text")
                pages_passed = pages == 512 and pages_with_text >= 506

                # 3. Sections
                await cur.execute("SELECT count(*) FROM library_sections_v2 WHERE run_id = %s", (rid,))
                sections = _v(await cur.fetchone())
                results["sections"] = sections
                print(f"  Sections: {sections}")

                # 4. Concepts
                await cur.execute("SELECT count(*) FROM library_concept_mentions_v2 WHERE run_id = %s", (rid,))
                concepts = _v(await cur.fetchone())
                results["concept_mentions"] = concepts
                print(f"  Concept mentions: {concepts}")

                # 5. Source refs
                await cur.execute("SELECT count(*) FROM library_source_references_v2 WHERE run_id = %s", (rid,))
                src_refs = _v(await cur.fetchone())
                results["source_references"] = src_refs
                print(f"  Source refs: {src_refs}")

                # 6. Relations
                await cur.execute("SELECT count(*) FROM library_internal_relations_v2 WHERE run_id = %s", (rid,))
                rels = _v(await cur.fetchone())
                results["internal_relations"] = rels
                print(f"  Relations: {rels}")

                # 7. Wiki
                await cur.execute("SELECT count(*) FROM library_document_wiki_v2 WHERE run_id = %s", (rid,))
                wiki = _v(await cur.fetchone())
                results["wiki_entries"] = wiki
                print(f"  Wiki entries: {wiki}")

                # 8. Query concepts
                print(f"\n  === Concept queries ===")
                concept_results = {}
                for concept in QUERY_CONCEPTS:
                    await cur.execute(
                        "SELECT cm.label, cm.page_number FROM library_concept_mentions_v2 cm WHERE cm.run_id = %s AND cm.normalized_label = %s LIMIT 5",
                        (rid, concept.lower()),
                    )
                    rows = await cur.fetchall()
                    pages_found = [_v(r, 1) for r in rows]
                    concept_results[concept] = {"found": len(rows) > 0, "pages": pages_found}
                    print(f"  {concept}: {'✓' if pages_found else '✗'} pages={pages_found[:5]}")

                # Also search pages_v2 text directly for concepts
                for concept in QUERY_CONCEPTS:
                    if not concept_results[concept]["found"]:
                        await cur.execute(
                            "SELECT p.page_number FROM library_pages_v2 p WHERE p.run_id = %s AND p.text ILIKE %s LIMIT 5",
                            (rid, f"%{concept}%"),
                        )
                        rows = await cur.fetchall()
                        direct_pages = [_v(r) for r in rows]
                        concept_results[concept]["direct_pages"] = direct_pages
                        print(f"  {concept} (direct text): pages={direct_pages}")
                results["concept_queries"] = concept_results

                # 9. Query relations
                print(f"\n  === Relation queries ===")
                relation_results = {}
                for ca, cb in QUERY_RELATIONS:
                    await cur.execute(
                        "SELECT page_start, page_end, snippet FROM library_internal_relations_v2 "
                        "WHERE run_id = %s AND concept_a = %s AND concept_b = %s LIMIT 3",
                        (rid, ca, cb),
                    )
                    rows = await cur.fetchall()
                    rel_pages = [(_v(r, 0), _v(r, 1)) for r in rows]
                    rel_snippets = [_v(r, 2)[:150] if _v(r, 2) else "" for r in rows]
                    relation_results[f"{ca}↔{cb}"] = {
                        "found": len(rows) > 0, "pages": rel_pages,
                        "snippets": rel_snippets,
                    }
                    print(f"  {ca} ↔ {cb}: {'✓' if rel_pages else '✗'} pages={rel_pages}")
                results["relation_queries"] = relation_results

                # 10. Overall
                errors = []
                if not pages_passed:
                    errors.append(f"pages: {pages}/512 total, {pages_with_text}/506 with text")
                if concepts == 0:
                    errors.append("no concepts")
                if src_refs == 0:
                    errors.append("no source refs")
                if rels == 0:
                    errors.append("no relations")
                if wiki == 0:
                    errors.append("no wiki")
                if status == "failed":
                    errors.append("run failed")

                if errors:
                    results["overall"] = "FAIL" if not pages_passed or status == "failed" else "WARN"
                else:
                    results["overall"] = "PASS"
                print(f"\n  OVERALL: {results['overall']}")
                if errors:
                    for e in errors:
                        print(f"    - {e}")

    finally:
        await close_pool(pool)

    (report_dir / "query_validation.json").write_text(json.dumps(results, indent=2, default=str, ensure_ascii=False))
    return 0 if results.get("overall") != "FAIL" else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
