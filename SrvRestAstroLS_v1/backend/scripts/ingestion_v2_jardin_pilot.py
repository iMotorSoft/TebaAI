#!/usr/bin/env python3
"""
Ingestion V2 Pilot — El Jardín de las Almas.

Reconstruye páginas, secciones, conceptos, fuentes, relaciones y wiki
en tablas V2. No toca corpus productivo.

Uso:
    uv run python scripts/ingestion_v2_jardin_pilot.py --dry-run
    uv run python scripts/ingestion_v2_jardin_pilot.py --execute
    uv run python scripts/ingestion_v2_jardin_pilot.py --dry-run --document-id ... --scope-code breslov_test
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from infrastructure.postgres.pool import (
    create_pool_from_settings,
    open_pool,
    close_pool,
)

HOST = os.environ.get("TEBAAI_BACKEND_HOST", "127.0.0.1")
PORT = os.environ.get("TEBAAI_BACKEND_PORT", "7008")
BASE = f"http://{HOST}:{PORT}"

DOCUMENT_ID = "76f2adbc-b79a-4432-9ea5-521a337a5502"
SCOPE_CODE = "breslov_test"
REPORT_BASE = Path(__file__).resolve().parent.parent.parent.parent / "data/reports/breslov/2026-07-09-ingestion-v2-jardin-sql-pilot"

# Concept detection lists
CONCEPTS_TO_FIND: dict[str, list[str]] = {
    "alma": ["alma", "almas", "neshamá", "neshama"],
    "tzadik": ["tzadik", "tzadikim", "justo"],
    "plegaria": ["plegaria", "plegarías", "oración", "orar"],
    "tefilá": ["tefilá", "tefila", "tefilah", "תפילה"],
    "Daat": ["daat", "da'at", "conocimiento divino", "comprensión divina"],
    "dolor": ["dolor", "dolores", "sufrimiento"],
    "Tajlit": ["tajlit", "objetivo final", "propósito final"],
    "Señor del Campo": ["señor del campo", "Señor del Campo"],
    "Canción del Futuro": ["canción del futuro", "Canción del Futuro", "melodía del futuro"],
    "Hebra de Bondad": ["hebra de bondad", "Hebra de Bondad", "jut shel jesed", "Jut shel Jesed"],
    "Otro Lado": ["otro lado", "Otro Lado", "sitra ájara", "Sitra Ájara"],
    "voz": ["voz"],
    "jardín": ["jardín", "jardín del edén", "Jardín del Edén"],
    "perfumes": ["perfumes", "aroma", "aroma placentero"],
    "temores": ["temores", "temor"],
    "Rosh HaShaná": ["rosh hashaná", "Rosh HaShaná", "Rosh Hashaná"],
    "Adam": ["adam", "Adán"],
    "Shlomo Efraim": ["shlomo efraim", "Shlomo Efraim"],
    "ekev": ["ekev", "talón"],
    "bitul": ["bitul", "anulación", "anular"],
    "emuná": ["emuná", "emuna", "fe", "creencia"],
    "simjá": ["simjá", "simcha", "alegría"],
    "tikún": ["tikún", "tikun", "rectificación"],
    "Shevirat HaKeilim": ["shevirat hakeilim", "rotura de los recipientes"],
    "vecino": ["vecino", "agregado de un vecino"],
    "curación": ["curación", "curar", "sanar"],
    "perdón": ["perdón", "perdonado", "expiación"],
}

# Source reference patterns
SOURCE_PATTERNS: list[tuple[str, str]] = [
    (r"Salmos?\s+\d+", "Salmos"),
    (r"Tehilim\s+\d+", "Salmos"),
    (r"Zohar", "Zohar"),
    (r"Talmud", "Talmud"),
    (r"Midrash", "Midrash"),
    (r"Bereshit|Génesis|Genesis", "Torá"),
    (r"Éxodo|Exodo|Shemot", "Torá"),
    (r"Deuteronomio|Devarim", "Torá"),
    (r"Isaías|Isaiah|Yeshayahu", "Profetas"),
    (r"Proverbios|Mishlé|Proverbs", "Ketuvim"),
    (r"Likutey Moharán|Likutey Moharan", "Likutey Moharán"),
    (r"Tikuney Zohar", "Zohar"),
    (r"Avot|Pirkei", "Mishná"),
    (r"Rashí|Rashi", "Rashí"),
    (r"Taanit", "Talmud"),
]

# Relation candidates for acid test
RELATION_CANDIDATES: list[tuple[str, str, str, str, str, str]] = [
    ("Daat", "dolor", "explicit_relation", "thematic_relation", "El sufrimiento se debe a que se retiró el Daat", "42"),
    ("Señor del Campo", "plegaria", "explicit_relation", "thematic_relation", "El Señor del Campo restaura almas y la plegaria alcanza perfección", "39"),
    ("voz", "jardín", "explicit_relation", "thematic_relation", "La voz riega el jardín", "384"),
    ("voz", "perfumes", "explicit_relation", "thematic_relation", "La voz riega el jardín donde crecen perfumes", "384"),
    ("voz", "temores", "cooccurrence", "thematic_relation", "Perfumes y temores crecen en el jardín que riega la voz", "384"),
    ("Canción del Futuro", "Hebra de Bondad", "explicit_relation", "thematic_relation", "Hebra de Bondad son cuerdas para la Canción del Futuro", "389"),
    ("tefilá bibejinat din", "Otro Lado", "explicit_relation", "thematic_relation", "El Otro Lado traga la plegaria en aspecto de juicio", "408"),
    ("vecino", "curación", "explicit_relation", "thematic_relation", "Agregar un vecino trae curación y perdón", "437-438"),
    ("vecino", "perdón", "explicit_relation", "thematic_relation", "El vecino multiplica la plegaria y trae perdón", "437-438"),
    ("Tajlit", "dolor", "explicit_relation", "thematic_relation", "El objetivo final es completamente bueno, el dolor se anula al contemplarlo", "42"),
    ("Rosh HaShaná", "Adam", "explicit_relation", "thematic_relation", "Rosh HaShaná es cuando Adam fue creado y transgredió", "280"),
]


def detect_section_headers(text: str) -> list[dict[str, Any]]:
    """Detect section headers from snippet text."""
    headers = []
    markers = re.findall(r"(?:^|\n)\s*[*]{2}([^*]{3,80})[*]{2}\s*(?:\n|$)", text)
    for i, m in enumerate(markers):
        if not m.startswith("Page") and not m.startswith("page"):
            headers.append({"title": m.strip(), "order_index": i, "method": "bold_header"})
    numbered = re.findall(r"(?:^|\n)\s*(?:\d+[.)]\s*)([A-Z][^*\n]{3,60})", text)
    for i, m in enumerate(numbered):
        headers.append({"title": m.strip(), "order_index": len(headers), "method": "numbered"})
    return headers


async def main() -> int:
    parser = argparse.ArgumentParser(description="Ingestion V2 Pilot — El Jardín de las Almas")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Dry run (default)")
    parser.add_argument("--execute", action="store_true", help="Execute (write to DB)")
    parser.add_argument("--document-id", default=DOCUMENT_ID, help="Document UUID")
    parser.add_argument("--scope-code", default=SCOPE_CODE, help="Knowledge scope code for the run")
    parser.add_argument("--report-dir", type=Path, default=REPORT_BASE, help="Report output directory")
    parser.add_argument("--top-k", type=int, default=50, help="Sources to retrieve (max 50)")
    args = parser.parse_args()

    is_dry_run = not args.execute
    mode_str = "DRY-RUN" if is_dry_run else "EXECUTE"
    doc_id = args.document_id
    report_dir = args.report_dir
    report_dir.mkdir(parents=True, exist_ok=True)

    email = os.environ.get("TEBAAI_E2E_ADMIN_EMAIL", "")
    password = os.environ.get("TEBAAI_E2E_ADMIN_PASSWORD", "")
    if not email or not password:
        print("ERROR: TEBAAI_E2E_ADMIN_EMAIL/PASSWORD required")
        return 1

    print(f"\n{'='*70}")
    print(f"  INGESTION V2 PILOT — El Jardín de las Almas ({mode_str})")
    print(f"{'='*70}")
    print(f"  Document ID: {doc_id}")
    print(f"  Scope: {args.scope_code}")
    print(f"  Report: {report_dir}")

    # ── 1. Retrieve document data via Relation QA ──────────────────────────
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{BASE}/auth/login", json={"email": email, "password": password}, timeout=10)
        if r.status_code != 201:
            print(f"Auth failed: {r.status_code}"); return 1
        token = r.json()["access_token"]

        r = await client.post(
            f"{BASE}/library/relation-qa",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "question": "El Jardín de las Almas detailed analysis full text",
                "concept_a": "Jardín", "concept_b": "Almas",
                "top_k": args.top_k, "use_ai": True,
                "knowledge_scope_code": "breslov_primary",
                "evidence_depth": "full",
            },
            timeout=120,
        )
        if r.status_code != 200:
            print(f"Relation QA failed: {r.status_code}"); return 1
        data = r.json()

    sources = data.get("sources", []) or data.get("source_map", [])
    jardin = [s for s in sources if "jardín" in (s.get("document_title") or "").lower()]

    if not jardin:
        print(f"\nERROR: No sources found for document {doc_id}")
        print("Cannot proceed with pilot. Relation QA did not return sources for El Jardín de las Almas.")
        return 1

    doc_title = jardin[0]["document_title"]
    print(f"\n  Document: {doc_title}")
    print(f"  Sources retrieved: {len(jardin)}")
    print(f"  AI synthesis: {data.get('method', {}).get('synthesis_mode', '?')}")
    print(f"  Milvus available: {data.get('method', {}).get('used_milvus', '?')}")

    # ── 2. Collect data ──────────────────────────────────────────────────
    # Snippets combined for section detection
    all_text = " ".join(s.get("snippet", "") or "" for s in jardin)

    # Pages
    pages_found = sorted(set(s.get("page_number") for s in jardin if s.get("page_number") is not None))
    page_range = (min(pages_found) if pages_found else None, max(pages_found) if pages_found else None)
    has_page_mapping = len(pages_found) > 0
    print(f"\n  Pages found: {len(pages_found)} ({page_range[0]}-{page_range[1]})" if has_page_mapping else "\n  Pages found: NONE (no page mapping)")

    # Sections from headers
    section_headers = detect_section_headers(all_text)
    print(f"  Section candidates: {len(section_headers)}")

    # Concepts
    concept_counts: dict[str, dict[str, Any]] = {}
    for label, variants in CONCEPTS_TO_FIND.items():
        count = 0
        matched_variants = []
        pages: set[int] = set()
        for v in variants:
            for s in jardin:
                snip = (s.get("snippet") or "").lower()
                if v.lower() in snip:
                    count += 1
                    if v not in matched_variants:
                        matched_variants.append(v)
                    if s.get("page_number"):
                        pages.add(s["page_number"])
        if count > 0:
            concept_counts[label] = {
                "count": count,
                "variants": matched_variants,
                "pages": sorted(pages),
                "method": "literal_search",
            }
    print(f"  Concepts detected: {len(concept_counts)}")

    # Source references
    src_refs: dict[str, int] = {}
    for pat, name in SOURCE_PATTERNS:
        count = sum(1 for s in jardin if re.search(pat, s.get("snippet") or "", re.IGNORECASE))
        if count > 0:
            src_refs[name] = src_refs.get(name, 0) + count
    print(f"  Source references: {len(src_refs)}")

    # Relations
    relations = []
    for ca, cb, rtype, ev_type, snippet_str, expected_page in RELATION_CANDIDATES:
        found_a = sum(1 for s in jardin if ca.lower() in (s.get("snippet") or "").lower())
        found_b = sum(1 for s in jardin if cb.lower() in (s.get("snippet") or "").lower())
        if found_a > 0 and found_b > 0:
            relations.append({
                "concept_a": ca, "concept_b": cb, "relation_type": rtype,
                "evidence_type": ev_type, "snippet": snippet_str,
                "expected_page": expected_page,
                "found_a_count": found_a, "found_b_count": found_b,
            })
    print(f"  Relations detected: {len(relations)}/{len(RELATION_CANDIDATES)}")

    # Acid pages check
    acid_pages = [36, 42, 280, 384, 389, 408, 437, 438]
    found_acid = [p for p in acid_pages if p in pages_found]
    missing_acid = [p for p in acid_pages if p not in pages_found]
    print(f"  Acid pages found: {len(found_acid)}/{len(acid_pages)} ({found_acid})")
    if missing_acid:
        print(f"  Acid pages missing: {missing_acid}")

    if is_dry_run:
        print(f"\n  {'─'*50}")
        print(f"  DRY-RUN: No data written to database.")
        print(f"  To execute, re-run with --execute")
        print(f"{'='*70}\n")
        return 0

    # ── 3. Write to V2 tables ─────────────────────────────────────────────
    print(f"\n  {'─'*50}")
    print(f"  EXECUTING: Writing to V2 tables...")

    pool = create_pool_from_settings()
    await open_pool(pool)

    run_id = str(uuid4())
    now = datetime.now(timezone.utc)
    warnings_list: list[str] = []
    metrics: dict[str, int] = {}

    try:
        async with pool.connection() as conn:
            # Create run
            await conn.execute(
                "INSERT INTO library_ingestion_runs_v2 (run_id, document_id, pipeline_version, scope_code, status, started_at) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (run_id, doc_id, "v2-pilot-001", args.scope_code, "started", now),
            )
            print(f"  Run created: {run_id[:8]}...")

            # ── Pages ──
            page_count = 0
            for pg in pages_found:
                # Find a snippet for this page
                snippet = ""
                for s in jardin:
                    if s.get("page_number") == pg:
                        snippet = s.get("snippet") or ""
                        break
                await conn.execute(
                    "INSERT INTO library_pages_v2 (run_id, document_id, page_number, text, char_count, extraction_method, confidence) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (run_id, doc_id, pg, snippet, len(snippet), "reconstructed", 0.7),
                )
                page_count += 1
            metrics["pages"] = page_count
            print(f"  Pages inserted: {page_count}")

            if not has_page_mapping:
                warnings_list.append("page_mapping_incomplete: no page_start/page_end in original chunks")

            # ── Sections ──
            sec_count = 0
            for i, hdr in enumerate(section_headers):
                await conn.execute(
                    "INSERT INTO library_sections_v2 (run_id, document_id, title, section_type, order_index, path, extraction_method, confidence) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (run_id, doc_id, hdr["title"], "section", hdr["order_index"], f"/{hdr['order_index']}", "heuristic", 0.5),
                )
                sec_count += 1
            metrics["sections"] = sec_count
            print(f"  Sections inserted: {sec_count}")

            # ── Concepts ──
            concept_count = 0
            for label, info in concept_counts.items():
                await conn.execute(
                    "INSERT INTO library_concept_mentions_v2 (run_id, document_id, label, normalized_label, variants, concept_type, extraction_method, confidence, page_number) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (run_id, doc_id, label, label.lower(), json.dumps(info["variants"]), "topic", "auto", 0.6, info["pages"][0] if info["pages"] else None),
                )
                concept_count += 1
            metrics["concept_mentions"] = concept_count
            print(f"  Concepts inserted: {concept_count}")

            # ── Source References ──
            src_count = 0
            for name, count in src_refs.items():
                await conn.execute(
                    "INSERT INTO library_source_references_v2 (run_id, document_id, reference_text, source_type, normalized_ref, evidence_type, extraction_method, confidence) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (run_id, doc_id, name, name, name.lower(), "source_reference", "auto", 0.6),
                )
                src_count += 1
            metrics["source_references"] = src_count
            print(f"  Source references inserted: {src_count}")

            # ── Relations ──
            rel_count = 0
            for rel in relations:
                await conn.execute(
                    "INSERT INTO library_internal_relations_v2 (run_id, document_id, concept_a, concept_b, relation_type, evidence_type, snippet, extraction_method, editorial_status, confidence) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (run_id, doc_id, rel["concept_a"], rel["concept_b"], rel["relation_type"],
                     rel["evidence_type"], rel["snippet"], "auto", "auto_extracted", 0.5),
                )
                rel_count += 1
            metrics["internal_relations"] = rel_count
            print(f"  Relations inserted: {rel_count}")

            if rel_count < 5:
                warnings_list.append(f"low_relation_count: only {rel_count}/11 relation candidates found")

            # ── Wiki ──
            key_concepts_list = sorted(concept_counts.keys())
            main_topics = list(set(c.lower() for c in key_concepts_list[:10]))
            questions = [
                "¿Qué dice el libro sobre el Daat y el dolor?",
                "¿Dónde se menciona al Señor del Campo?",
                "¿Qué relación hay entre la voz y el jardín?",
                "¿Qué es la Canción del Futuro?",
                "¿Qué es la Hebra de Bondad?",
                "¿Cómo actúa el Otro Lado frente a la plegaria en aspecto de juicio?",
            ]
            wiki_warnings = warnings_list.copy()
            await conn.execute(
                "INSERT INTO library_document_wiki_v2 (run_id, document_id, overview, structure_summary, main_topics, key_concepts, source_map, internal_relations_summary, questions_it_can_answer, warnings, review_status) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (run_id, doc_id,
                 f"El Jardín de las Almas — enseñanzas del Rebe Najmán sobre el alma, el daat, la plegaria y el objetivo final.",
                 f"Se detectaron {sec_count} secciones candidatas y {len(pages_found)} páginas.",
                 json.dumps(main_topics),
                 json.dumps(key_concepts_list),
                 json.dumps(src_refs),
                 json.dumps([f"{r['concept_a']} ↔ {r['concept_b']}" for r in relations]),
                 json.dumps(questions),
                 json.dumps(wiki_warnings),
                 "auto_generated"),
            )
            metrics["wiki"] = 1
            print(f"  Wiki inserted")

            # ── Update run status ──
            status = "completed" if not warnings_list else "partial"
            await conn.execute(
                "UPDATE library_ingestion_runs_v2 SET status = %s, finished_at = %s, metrics_json = %s, warnings_json = %s WHERE run_id = %s",
                (status, datetime.now(timezone.utc), json.dumps(metrics), json.dumps(warnings_list), run_id),
            )
            print(f"  Run status: {status}")

    except Exception as exc:
        print(f"\n  ERROR: {exc}")
        try:
            async with pool.connection() as conn:
                await conn.execute(
                    "UPDATE library_ingestion_runs_v2 SET status = 'failed', finished_at = %s, warnings_json = %s WHERE run_id = %s",
                    (datetime.now(timezone.utc), json.dumps([str(exc)]), run_id),
                )
        except Exception:
            pass
        return 1
    finally:
        await close_pool(pool)

    # ── 4. Save report ────────────────────────────────────────────────────
    summary = {
        "run_id": run_id,
        "document_id": doc_id,
        "mode": "execute",
        "status": status,
        "metrics": metrics,
        "warnings": warnings_list,
        "pages_found_count": len(pages_found),
        "pages_range": list(page_range) if page_range else None,
        "acid_pages_found": found_acid,
        "acid_pages_missing": missing_acid,
        "sections_count": sec_count,
        "concepts_count": concept_count,
        "source_refs_count": src_count,
        "relations_count": rel_count,
        "relations_total_candidates": len(RELATION_CANDIDATES),
    }
    (report_dir / "execute_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\n  Report: {report_dir / 'execute_summary.json'}")
    print(f"{'='*70}\n")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
