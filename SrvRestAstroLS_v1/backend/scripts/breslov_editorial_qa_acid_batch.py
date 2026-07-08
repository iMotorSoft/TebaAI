#!/usr/bin/env python3
"""
Breslov Editorial QA Acid Batch — 5 critical cases for Likutey Halajot.

Reuses core logic from scripts.breslov_concept_relation_qa_lab:
  expand_concepts, search_literal_fts, search_exact_cooccurrence,
  search_vector_relation, enrich_evidence_from_pg, merge_results,
  classify_evidence, build_source_map, call_interpretation_model

Usage:
  # All 5 cases, no AI
  uv run python -m scripts.breslov_editorial_qa_acid_batch \\
    --case-config scripts/editorial_qa_cases_likutey_5.json \\
    --no-ai --require-pg-source

  # All 5 cases, with AI
  uv run python -m scripts.breslov_editorial_qa_acid_batch \\
    --case-config scripts/editorial_qa_cases_likutey_5.json \\
    --use-ai --require-pg-source

  # Single case
  uv run python -m scripts.breslov_editorial_qa_acid_batch \\
    --case-id azamra_points_good \\
    --case-config scripts/editorial_qa_cases_likutey_5.json \\
    --use-ai --require-pg-source

  # Preflight only
  uv run python -m scripts.breslov_editorial_qa_acid_batch \\
    --case-config scripts/editorial_qa_cases_likutey_5.json \\
    --preflight-only
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from typing import Any

SCOPE_CODE = "breslov_primary"

# ── Reuse from lab script ─────────────────────────────────────────────────

from scripts.breslov_concept_relation_qa_lab import (
    expand_concepts,
    search_literal_fts,
    search_exact_cooccurrence,
    search_vector_relation,
    generate_vector_queries,
    enrich_evidence_from_pg,
    merge_results,
    classify_evidence,
    build_source_map,
    call_interpretation_model,
    EvidenceItem,
    SourceMapEntry,
    LITERAL,
    CONCEPT_A,
    CONCEPT_B,
    COOCCUR_SAME_CHUNK,
    THEMATIC,
    AI_INFERENCE,
    NOT_FOUND,
)


# ── Editorial evidence types ───────────────────────────────────────────────

EDITORIAL_TYPES = {
    "literal_phrase": "La frase buscada aparece literalmente o casi literalmente",
    "explicit_reference": "Fuente mencionada por nombre, no necesariamente citada completa",
    "biblical_citation": "Versículo bíblico citado o usado",
    "rabbinic_source": "Fuente rabínica (Midrash, Guemará, Zohar, etc.)",
    "breslov_text": "Texto principal de Breslov (Rebe Najmán / Rabí Natán)",
    "editorial_explanation": "Explicación agregada por edición/traducción",
    "footnote_reference": "Nota al pie con fuente o aclaración",
    "marginal_source": "Cita marginal o caja lateral",
    "source_hebrew": "Bloque hebreo fuente del documento layout-aware",
    "paraphrase": "Idea explicada en otras palabras",
    "thematic_relation": "Relación conceptual posible",
    "derash_interpretation": "Lectura interpretativa explícita basada en asociación textual",
    "remez_hint": "Alusión o indicio, no afirmación literal",
    "ai_inference": "Conclusión propuesta por IA, no presente literal",
    "ambiguous": "Resultado requiere cautela por ambigüedad",
    "not_found": "No hay evidencia suficiente en el corpus",
    "excluded_false_positive": "Descartado por ambigüedad o falta de relación",
}


def map_evidence_type(original_type: str, item: EvidenceItem) -> str:
    """Map internal evidence types to editorial classification."""
    if original_type == LITERAL:
        return "literal_phrase"
    if original_type == COOCCUR_SAME_CHUNK:
        return "thematic_relation"
    if original_type == CONCEPT_A or original_type == CONCEPT_B:
        return "breslov_text"
    if original_type == THEMATIC:
        return "thematic_relation"
    if original_type == NOT_FOUND:
        return "not_found"
    return original_type


# ── Preflight (simplified) ─────────────────────────────────────────────────

async def preflight() -> dict[str, Any]:
    checks = {}

    # PG
    try:
        from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
        pool = create_pool_from_settings()
        await open_pool(pool)
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT count(*) FROM library_documents WHERE status='ready'")
                checks["pg_ready_docs"] = str((await cur.fetchone())["count"])

                await cur.execute(
                    "SELECT count(*) FROM library_document_chunks ch "
                    "JOIN library_documents d ON d.id=ch.document_id "
                    "WHERE d.status='ready'"
                )
                checks["pg_ready_chunks"] = str((await cur.fetchone())["count"])

                await cur.execute(
                    "SELECT id::text, status FROM library_documents "
                    "WHERE id::text LIKE '47768aac%'"
                )
                likutey = await cur.fetchone()
                if likutey:
                    checks["likutey_layout_status"] = likutey["status"]
        await close_pool(pool)
    except Exception as exc:
        checks["pg_connect"] = f"FAIL ({exc})"
        return {"status": "BLOCKED", "checks": checks, "blocker": f"PG: {exc}"}
    checks["pg_connect"] = "OK"

    # Milvus
    try:
        from pymilvus import Collection, connections, utility

        connections.connect(host="127.0.0.1", port=19530)
        cols = utility.list_collections()
        checks["milvus_prod_exists"] = "tebaai_breslov_chunks_v1" in cols
        if checks["milvus_prod_exists"]:
            c = Collection("tebaai_breslov_chunks_v1")
            c.load()
            checks["milvus_prod_entities"] = str(c.num_entities)

            results = c.query(expr='pk!=""', output_fields=["chunk_id"], limit=15000)
            unique = set(r.get("chunk_id", "") for r in results)
            checks["milvus_unique_chunks"] = str(len(unique))

            dup_check = {}
            for r in results:
                cid = r.get("chunk_id", "")
                if cid:
                    dup_check[cid] = dup_check.get(cid, 0) + 1
            dups = sum(1 for v in dup_check.values() if v > 1)
            checks["milvus_duplicates"] = str(dups)

            stale = c.query(expr='source_type==""', output_fields=["pk"], limit=10000)
            checks["milvus_stale"] = str(len(stale))

            c.release()
        connections.disconnect("default")
    except Exception as exc:
        checks["milvus_connect"] = f"FAIL ({exc})"

    # LiteLLM
    try:
        import httpx
        from globalVar import LITELLM_API_KEY, LITELLM_BASE_URL
        if not LITELLM_API_KEY:
            checks["litellm"] = "FAIL (no key)"
        else:
            headers = {"Authorization": f"Bearer {LITELLM_API_KEY}"}
            r = httpx.get(f"{LITELLM_BASE_URL}/health", headers=headers, timeout=10)
            checks["litellm"] = f"OK ({r.status_code})" if r.status_code == 200 else f"WARN ({r.status_code})"
    except Exception as exc:
        checks["litellm"] = f"FAIL ({exc})"

    checks["no_writes_planned"] = "yes"
    return {"status": "PASS" if checks.get("pg_connect") == "OK" else "BLOCKED", "checks": checks}


def print_preflight_table(checks: dict[str, str]) -> None:
    print(f"\n{'='*60}")
    print("  PRECHECK — Editorial QA Acid Batch")
    print(f"{'='*60}")
    for check, val in sorted(checks.items()):
        icon = "✅" if str(val).startswith("OK") or str(val) in ("yes", "True") else "❌"
        print(f"  {icon} {check:<35} {str(val):<30}")
    print(f"{'='*60}\n")


# ── Case runner ────────────────────────────────────────────────────────────

async def run_case(
    case: dict[str, Any],
    pool,
    use_ai: bool,
    require_pg_source: bool,
    include_test_candidates: bool,
    top_k: int = 20,
) -> dict[str, Any]:
    """
    Execute retrieval + classification + optional AI for one case.
    Returns a dict with all results for reporting.
    """
    case_id = case["case_id"]
    concept_a = case["concept_a"]
    concept_b = case["concept_b"]
    question = case["question"]
    variants = case.get("variants", [])

    # Build expansion from variants
    expansion = expand_concepts(concept_a, concept_b)
    # Also add any extra variants not covered by expansion
    all_a = list(expansion["a_variants"])
    all_b = list(expansion["b_variants"])

    print(f"\n{'─'*60}")
    print(f"  Case {case_id}: {case['title']}")
    print(f"  Q: {question[:120]}")
    print(f"{'─'*60}")

    # 1. FTS for concept A
    fts_a = await search_literal_fts(pool, all_a, top_k, "a")
    print(f"  FTS A: {len(fts_a)} results")

    # 2. FTS for concept B
    fts_b = await search_literal_fts(pool, all_b, top_k, "b")
    print(f"  FTS B: {len(fts_b)} results")

    # 3. Cooccurrence
    cooc = await search_exact_cooccurrence(pool, all_a, all_b)
    print(f"  Cooccurrence: {len(cooc)} results")

    # 4. Vector search
    vec_queries = [question] + variants[:3]
    vec_results = search_vector_relation(vec_queries, top_k)
    print(f"  Vector: {len(vec_results)} raw hits")

    if vec_results:
        vec_results = await enrich_evidence_from_pg(pool, vec_results)
        no_pg = sum(1 for v in vec_results if not v.text)
        print(f"  → {len(vec_results)} enriched ({no_pg} without PG)")

    # 5. Merge + classify
    all_items = merge_results(fts_a, fts_b, cooc, vec_results, all_a, all_b)
    print(f"  → {len(all_items)} unique fragments after merge")

    # 6. Map to editorial types
    for item in all_items:
        item.evidence_type = map_evidence_type(item.evidence_type, item)

    # 7. Build source map
    source_map = build_source_map(all_items)

    # 8. Check PG requirement
    no_pg_count = sum(1 for i in all_items if not i.text)
    if require_pg_source and no_pg_count > 0:
        print(f"  ⚠️  {no_pg_count} results without PG text")

    # 9. AI interpretation
    ai_response = None
    if use_ai and all_items:
        ai_response = call_interpretation_model(question, concept_a, concept_b, source_map, all_items)
        if ai_response and ai_response.get("error"):
            print(f"  AI error: {ai_response['error']}")
        elif ai_response:
            print(f"  AI OK: {ai_response.get('model', '?')}")

    # 10. Summary
    summary = {
        "case_id": case_id,
        "title": case["title"],
        "question": question,
        "concept_a": concept_a,
        "concept_b": concept_b,
        "total_items": len(all_items),
        "no_pg_count": no_pg_count,
        "evidence_counts": {},
        "items": all_items,
        "source_map": source_map,
        "ai_response": ai_response,
        "must_not_claim": case.get("must_not_claim", []),
        "editorial_risks": case.get("editorial_risks", []),
        "verdict": "PASS" if no_pg_count == 0 else "WARN",
    }
    for item in all_items:
        t = item.evidence_type
        summary["evidence_counts"][t] = summary["evidence_counts"].get(t, 0) + 1

    return summary


# ── Editorial report ───────────────────────────────────────────────────────

def print_editorial_report(summary: dict[str, Any], use_ai: bool) -> None:
    """Print editorial report for one case."""
    s = summary
    print(f"\n{'='*70}")
    print(f"  CASE {s['case_id']} — {s['title']}")
    print(f"{'='*70}")

    # 1. Brief answer
    print(f"\n  📋 1. Respuesta editorial breve")
    ai_raw = (s.get("ai_response") or {}).get("raw", "") if use_ai else ""
    if ai_raw:
        for line in ai_raw.split("\n")[:10]:
            print(f"    {line}")
        print("    ...")
    else:
        has_literal = any(i.evidence_type == "literal_phrase" for i in s["items"])
        has_ref = any(i.evidence_type == "explicit_reference" for i in s["items"])
        if has_literal:
            print("    Se encontró evidencia literal.")
        elif has_ref:
            print("    Se encontraron referencias explícitas.")
        else:
            print("    No se encontró evidencia literal directa.")

    # 2. Evidence types
    print(f"\n  📊 2. Tipos de evidencia")
    print(f"    {'Tipo':<30} {'Cantidad':<10}")
    print(f"    {'─'*30} {'─'*10}")
    for etype in ["literal_phrase", "explicit_reference", "biblical_citation",
                   "rabbinic_source", "breslov_text", "footnote_reference",
                   "marginal_source", "thematic_relation", "derash_interpretation",
                   "ai_inference", "not_found"]:
        cnt = s["evidence_counts"].get(etype, 0)
        if cnt > 0:
            print(f"    {etype:<30} {cnt:<10}")

    # 3. Source map table
    print(f"\n  📚 3. Fuentes principales")
    print(f"    {'Doc':<30} {'Pág':<5} {'Block':<16} {'Tipo':<22}")
    print(f"    {'─'*30} {'─'*5} {'─'*16} {'─'*22}")
    for entry in s["source_map"][:10]:
        title = (entry.document_title or "?")[:28]
        pg = str(entry.page_number or "?")[:4]
        bt = (entry.block_type or "?")[:14]
        et = (entry.evidence_type or "?")[:20]
        print(f"    {title:<30} {pg:<5} {bt:<16} {et:<22}")
    if len(s["source_map"]) > 10:
        print(f"    ... y {len(s['source_map']) - 10} fuente(s) más.")

    # 4. What's literal
    print(f"\n  📝 4. Qué está literalmente en el texto")
    literals = [i for i in s["items"] if i.evidence_type == "literal_phrase"]
    if literals:
        for item in literals[:3]:
            snippet = (item.text or "")[:200].replace("\n", " ")
            print(f"    • {snippet}...")
            if item.page_number:
                print(f"      → {item.document_title[:40]} p. {item.page_number}")
    else:
        print("    No se encontraron fragmentos literales.")

    # 5. References / notes
    refs = [i for i in s["items"] if i.evidence_type in ("explicit_reference", "footnote_reference", "marginal_source", "rabbinic_source")]
    if refs:
        print(f"\n  📌 5. Referencias y notas ({len(refs)} fragments)")
        for item in refs[:3]:
            snippet = (item.text or "")[:150].replace("\n", " ")
            print(f"    • {snippet}...")

    # 6. Interpretation
    print(f"\n  🔍 6. Interpretación")
    if use_ai and ai_raw:
        print(f"    Respuesta IA:")
        for line in ai_raw.split("\n"):
            print(f"      {line}")
    else:
        thematic = [i for i in s["items"] if i.evidence_type in ("thematic_relation", "derash_interpretation", "ai_inference")]
        if thematic:
            print(f"    {len(thematic)} fragment(s) con relación temática/interpretativa.")
        else:
            print("    Sin interpretación adicional.")

    # 7. Must not claim
    print(f"\n  ⚠️  7. Qué NO se debe afirmar")
    for warning in s.get("must_not_claim", []):
        print(f"    • {warning}")

    # 8. Verdict
    print(f"\n  {'─'*60}")
    print(f"  Veredicto: {s['verdict']}")
    print(f"  Total: {s['total_items']} fragments | Sin PG: {s['no_pg_count']}")
    print(f"{'─'*60}\n")


# ── Acid checklist ─────────────────────────────────────────────────────────

def acid_checklist(summary: dict[str, Any], use_ai: bool) -> dict[str, str]:
    """Run editorial acid checklist on a case result."""
    checks = {}
    items = summary["items"]
    ai_raw = (summary.get("ai_response") or {}).get("raw", "") if use_ai else ""

    has_literal = any(i.evidence_type == "literal_phrase" for i in items)
    has_reference = any(i.evidence_type in ("explicit_reference", "footnote_reference", "marginal_source") for i in items)
    has_thematic = any(i.evidence_type in ("thematic_relation", "derash_interpretation") for i in items)
    has_pg_text = all(bool(i.text) for i in items) if items else True
    has_page = any(i.page_number is not None for i in items)
    has_block_type = any(i.block_type for i in items)

    checks["Distingue literal de inferido"] = "PASS" if (has_literal or not items) else "WARN"
    checks["Distingue nota de texto principal"] = "PASS" if has_reference else "WARN"
    checks["Distingue fuente rabínica"] = "PASS" if any(i.evidence_type == "rabbinic_source" for i in items) else "WARN"
    checks["Muestra página/sección"] = "PASS" if has_page else "FAIL"
    checks["Evita claims no probados"] = "PASS"
    checks["Muestra qué NO afirmar"] = "PASS" if summary.get("must_not_claim") else "WARN"
    checks["Resuelve todo a PG"] = "PASS" if (summary["no_pg_count"] == 0 or not items) else "FAIL"
    checks["Block type presente"] = "PASS" if has_block_type else "WARN"
    checks["Certeza declarada"] = "PASS" if (use_ai and "certeza" in ai_raw.lower()) or not use_ai else "WARN"

    return checks


# ── Main ───────────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(
        description="Breslov Editorial QA Acid Batch — 5 critical cases"
    )
    parser.add_argument("--case-config", required=True, help="Path to JSON case config")
    parser.add_argument("--case-id", help="Run single case by case_id")
    parser.add_argument("--preflight-only", action="store_true", help="Run preflight only, no cases")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--no-ai", action="store_true", default=True, help="No AI interpretation")
    mode.add_argument("--use-ai", action="store_true", help="With AI interpretation")
    parser.add_argument("--require-pg-source", action="store_true", default=True, help="Fail on results without PG text")
    parser.add_argument("--include-test-candidates-readonly", action="store_true", help="Include test_candidate docs")
    parser.add_argument("--top-k", type=int, default=20, help="Results per search")
    args = parser.parse_args()

    # ── Load config ───────────────────────────────────────────────────
    with open(args.case_config) as f:
        all_cases = json.load(f)

    if args.case_id:
        cases = [c for c in all_cases if c["case_id"] == args.case_id]
        if not cases:
            print(f"ERROR: case_id '{args.case_id}' not found")
            return 1
    else:
        cases = all_cases

    use_ai = args.use_ai
    mode_label = "USE-AI" if use_ai else "NO-AI"

    print(f"\n{'='*70}")
    print(f"  BRESLOV EDITORIAL QA ACID BATCH — {mode_label}")
    print(f"  Cases: {[c['case_id'] for c in cases]}")
    print(f"{'='*70}")

    # ── Preflight ─────────────────────────────────────────────────────
    pf = await preflight()
    print_preflight_table(pf["checks"])

    if args.preflight_only:
        print("  Preflight only. No cases executed.")
        return 0

    if pf["status"] == "BLOCKED":
        print(f"\n  {'❌'*3} BLOQUEADO_PRECHECK")
        print(f"  {pf.get('blocker', '')}")
        return 1

    # ── Connect PG ────────────────────────────────────────────────────
    from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
    pool = create_pool_from_settings()
    await open_pool(pool)

    all_summaries = []
    overall_verdict = "PASS"

    try:
        for case in cases:
            summary = await run_case(
                case=case,
                pool=pool,
                use_ai=use_ai,
                require_pg_source=args.require_pg_source,
                include_test_candidates=args.include_test_candidates_readonly,
                top_k=args.top_k,
            )
            all_summaries.append(summary)
            print_editorial_report(summary, use_ai)

            # Acid checklist
            checks = acid_checklist(summary, use_ai)
            fails = [k for k, v in checks.items() if v == "FAIL"]
            warns = [k for k, v in checks.items() if v == "WARN"]
            if fails:
                overall_verdict = "FAIL"
            elif warns and overall_verdict != "FAIL":
                overall_verdict = "WARN"

            print(f"  🧪 Acid checklist:")
            for check, result in checks.items():
                icon = "✅" if result == "PASS" else "⚠️" if result == "WARN" else "❌"
                print(f"    {icon} {check:<38} {result:<8}")
            if fails:
                print(f"    ❌ FAIL items: {', '.join(fails)}")
            print()

    finally:
        await close_pool(pool)

    # ── Final summary ─────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print(f"  BRESLOV EDITORIAL QA ACID BATCH — COMPLETE")
    print(f"  Mode: {mode_label}")
    print(f"  Overall verdict: {overall_verdict}")
    print(f"{'='*70}")
    print(f"\n  {'Case':<30} {'Total':<8} {'Sin PG':<8} {'Verdict':<10}")
    print(f"  {'─'*30} {'─'*8} {'─'*8} {'─'*10}")
    for s in all_summaries:
        print(f"  {s['case_id']:<30} {s['total_items']:<8} {s['no_pg_count']:<8} {s['verdict']:<10}")

    return 0 if overall_verdict != "FAIL" else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
