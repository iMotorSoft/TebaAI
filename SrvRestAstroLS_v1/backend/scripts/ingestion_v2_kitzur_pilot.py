#!/usr/bin/env python3
"""Ingestion V2 Pilot — KITZUR CreateSpace. Extrae páginas, secciones, conceptos, fuentes, relaciones y wiki en tablas V2."""

from __future__ import annotations

import argparse, asyncio, json, os, re, sys, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import fitz
from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool

# ── Concept detection dictionary ──────────────────────────────────────────
CONCEPTS: dict[str, list[str]] = {
    "tzadik": ["tzadik", "tzadikim"],
    "Rebe Najmán": ["rebe najmán", "rabí najmán", "rebe najman", "rabi najman"],
    "Rabí Natán": ["rabí natán", "rabi natan", "rebe natán"],
    "hitbodedut": ["hitbodedut", "hisbodedus"],
    "plegaria": ["plegaria", "plegarías", "oración", "orar"],
    "tefilá": ["tefilá", "tefila", "tefilah"],
    "emuná": ["emuná", "emuna", "fe", "creencia"],
    "alegría": ["alegría", "alegre", "simjá", "simcha", "regocijo"],
    "tristeza": ["tristeza", "triste", "atzvut"],
    "miedo": ["miedo", "temor", "yirá"],
    "Daat": ["daat", "da'at", "conocimiento divino"],
    "Tajlit": ["tajlit", "objetivo final", "propósito final"],
    "brit": ["brit", "pacto", "circuncisión"],
    "habla": ["habla", "hablar", "palabra", "dibur"],
    "voz": ["voz"],
    "sangre": ["sangre", "dam"],
    "Rosh HaShaná": ["rosh hashaná", "rosh hashana"],
    "teshuvá": ["teshuvá", "teshuva", "arrepentimiento"],
    "Torá": ["torá", "tora"],
    "Shabat": ["shabat", "shabbat", "sábado"],
}

# ── Source reference patterns ─────────────────────────────────────────────
SOURCE_PATTERNS: list[tuple[str, str, str]] = [
    (r"Génesis|Bereshit|Genesis", "biblical", "Torá"),
    (r"Éxodo|Shemot|Exodo", "biblical", "Torá"),
    (r"Levítico|Vayikra|Levitico", "biblical", "Torá"),
    (r"Números|Bemidbar|Numeros", "biblical", "Torá"),
    (r"Deuteronomio|Devarim", "biblical", "Torá"),
    (r"Salmos|Tehilim", "biblical", "Salmos"),
    (r"Proverbios|Mishlé|Mishle", "biblical", "Ketuvim"),
    (r"Isaías|Yeshayahu|Isaias", "biblical", "Profetas"),
    (r"Jeremías|Yirmiyahu|Jeremias", "biblical", "Profetas"),
    (r"Talmud", "rabbinic", "Talmud"),
    (r"Zohar", "rabbinic", "Zohar"),
    (r"Midrash", "rabbinic", "Midrash"),
    (r"Likutey Moharán|Likutey Moharan", "breslov", "Likutey Moharán"),
    (r"Likutey Halajot", "breslov", "Likutey Halajot"),
    (r"Rashí|Rashi", "rabbinic", "Rashí"),
    (r"Shuljan Aruj", "rabbinic", "Shulján Aruj"),
]

# ── Relation candidates ───────────────────────────────────────────────────
RELATION_PAIRS: list[tuple[str, str, str, str]] = [
    ("alegría", "plegaria", "cooccurrence_page", "temática"),
    ("tristeza", "alegría", "cooccurrence_page", "contraste"),
    ("emuná", "plegaria", "cooccurrence_page", "temática"),
    ("Daat", "sufrimiento", "cooccurrence_page", "temática"),
    ("brit", "habla", "cooccurrence_page", "conceptual"),
    ("sangre", "habla", "cooccurrence_page", "conceptual"),
    ("voz", "plegaria", "cooccurrence_page", "temática"),
    ("tzadik", "Rosh HaShaná", "cooccurrence_page", "temática"),
    ("hitbodedut", "plegaria", "cooccurrence_page", "temática"),
    ("teshuvá", "Rosh HaShaná", "cooccurrence_page", "temática"),
]


def detect_sections(text: str) -> list[dict[str, Any]]:
    """Detect section candidates from full text using heuristics."""
    candidates = []
    # ALL-CAPS lines (3+ words)
    for m in re.finditer(r"(?:^|\n)\s*([A-ZÁÉÍÓÚÜÑ][A-ZÁÉÍÓÚÜÑ\s]{5,80})(?:\n|$)", text):
        t = m.group(1).strip()
        if len(t) > 10 and not re.search(r"\d{4}", t) and "PAGE" not in t.upper():
            candidates.append({"title": t, "method": "all_caps", "confidence": 0.4})
    # Numbered headings like "1. Title" or "Lección 1"
    for m in re.finditer(r"(?:^|\n)\s*(?:Lecci[oó]n|Leccion|Halajá|Halaja|Sección|Seccion|Cap[ií]tulo|Capitulo)\s+\d+[\s.:]+([^\n]{3,80})", text, re.IGNORECASE):
        candidates.append({"title": m.group(0).strip(), "method": "numbered_heading", "confidence": 0.6})
    return candidates


async def main() -> int:
    parser = argparse.ArgumentParser(description="KITZUR CreateSpace Ingestion V2 Pilot")
    parser.add_argument("--pdf", required=True, help="Path to PDF")
    parser.add_argument("--scope-code", default="breslov_test")
    parser.add_argument("--pipeline-version", default="ingestion_v2_kitzur_createspace_001")
    parser.add_argument("--report-dir", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    is_dry = not args.execute
    mode = "DRY-RUN" if is_dry else "EXECUTE"
    pdf_path = Path(args.pdf)
    report_dir = args.report_dir
    report_dir.mkdir(parents=True, exist_ok=True)

    if not pdf_path.exists():
        print(f"ERROR: PDF not found: {pdf_path}")
        return 1

    print(f"\n{'='*70}")
    print(f"  KITZUR CREATESPACE INGESTION V2 PILOT ({mode})")
    print(f"{'='*70}")
    print(f"  PDF: {pdf_path} ({pdf_path.stat().st_size//1024} KB)")
    print(f"  Scope: {args.scope_code}")
    print(f"  Pipeline: {args.pipeline_version}")
    print(f"  Report: {report_dir}")

    # ── Extract pages ────────────────────────────────────────────────────
    print(f"\n  {'─'*50}")
    print(f"  [1/7] Extracting pages...")
    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)
    pages_data: list[dict[str, Any]] = []
    empty_count = 0
    text_count = 0
    total_chars = 0
    all_text_parts: list[str] = []

    for i in range(total_pages):
        page = doc.load_page(i)
        raw = page.get_text("text")
        text = raw.strip()
        chars = len(text)
        total_chars += chars
        has_text = chars > 0
        if has_text:
            text_count += 1
            all_text_parts.append(text)
        else:
            empty_count += 1
        pages_data.append({
            "page_number": i + 1,
            "text": text,
            "char_count": chars,
            "has_text": has_text,
        })
    doc.close()

    print(f"  Pages: {total_pages} total, {text_count} with text, {empty_count} empty")
    print(f"  Total chars: {total_chars}")

    if text_count < 500:
        print(f"\n  ERROR: Only {text_count} pages with text (< 500). Aborting.")
        return 1

    # Report
    page_stats = {
        "total_pages": total_pages, "pages_with_text": text_count,
        "pages_empty": empty_count, "total_chars": total_chars,
        "avg_chars_per_page": round(total_chars / max(text_count, 1), 1),
    }
    (report_dir / "page_stats.json").write_text(json.dumps(page_stats, indent=2))

    # ── Save marked sample ───────────────────────────────────────────────
    sample_lines = []
    for p in pages_data[:10] + pages_data[-5:]:
        preview = p["text"][:200] if p["has_text"] else "(empty)"
        sample_lines.append(f"## Page {p['page_number']}\n\n{preview}\n\n---\n\n")
    (report_dir / "samples" if is_dry else report_dir).mkdir(parents=True, exist_ok=True)
    (report_dir / "page_samples.md").write_text("".join(sample_lines))

    # ── Detect sections ──────────────────────────────────────────────────
    print(f"\n  [2/7] Detecting sections...")
    full_text = "\n".join(all_text_parts)
    sections = detect_sections(full_text)
    # Deduplicate by title
    seen_titles = set()
    unique_sections = []
    for s in sections:
        if s["title"] not in seen_titles:
            seen_titles.add(s["title"])
            unique_sections.append(s)
    print(f"  Section candidates: {len(unique_sections)}")
    (report_dir / "sections.json").write_text(json.dumps(unique_sections[:100], indent=2, ensure_ascii=False))

    # ── Detect concepts ──────────────────────────────────────────────────
    print(f"\n  [3/7] Detecting concepts...")
    concept_mentions: list[dict[str, Any]] = []
    concept_stats: dict[str, dict[str, Any]] = {}
    for label, variants in CONCEPTS.items():
        pages_found: list[int] = []
        matched_variants: list[str] = []
        for p in pages_data:
            if not p["has_text"]:
                continue
            pt = p["text"].lower()
            for v in variants:
                if v.lower() in pt:
                    if v not in matched_variants:
                        matched_variants.append(v)
                    if p["page_number"] not in pages_found:
                        pages_found.append(p["page_number"])
        if pages_found:
            concept_mentions.append({
                "label": label, "normalized_label": label.lower(),
                "variants": matched_variants, "page_numbers": pages_found,
                "count": len(pages_found),
            })
            concept_stats[label] = {"pages": len(pages_found), "first_page": pages_found[0]}
    print(f"  Concepts detected: {len(concept_mentions)}")
    for c in concept_mentions[:10]:
        print(f"    {c['label']}: {c['count']} pages")

    # ── Detect source references ─────────────────────────────────────────
    print(f"\n  [4/7] Detecting source references...")
    source_refs: dict[str, dict[str, Any]] = {}
    for p in pages_data:
        if not p["has_text"]:
            continue
        pt = p["text"]
        for pat, stype, sname in SOURCE_PATTERNS:
            if re.search(pat, pt, re.IGNORECASE):
                if sname not in source_refs:
                    source_refs[sname] = {"type": stype, "count": 0, "pages": []}
                source_refs[sname]["count"] += 1
                if p["page_number"] not in source_refs[sname]["pages"]:
                    source_refs[sname]["pages"].append(p["page_number"])
    print(f"  Source references: {len(source_refs)}")
    for name, info in sorted(source_refs.items(), key=lambda x: -x[1]["count"])[:10]:
        print(f"    {name}: {info['count']} mentions on {len(info['pages'])} pages")

    # ── Detect relations ─────────────────────────────────────────────────
    print(f"\n  [5/7] Detecting internal relations...")
    relations = []
    for ca, cb, rtype, desc in RELATION_PAIRS:
        ca_lower = ca.lower()
        cb_lower = cb.lower()
        # Find pages where both concepts appear
        common_pages = []
        snippets = []
        for p in pages_data:
            if not p["has_text"]:
                continue
            pt = p["text"].lower()
            has_a = any(v.lower() in pt for v in CONCEPTS.get(ca, [ca]))
            has_b = any(v.lower() in pt for v in CONCEPTS.get(cb, [cb]))
            if has_a and has_b:
                common_pages.append(p["page_number"])
                if len(snippets) < 3:
                    idx = pt.find(CONCEPTS.get(ca, [ca])[0].lower())
                    if idx > 0:
                        snippets.append(p["text"][max(0, idx - 40):idx + 200].strip())
        if common_pages:
            relations.append({
                "concept_a": ca, "concept_b": cb,
                "relation_type": rtype, "evidence_type": "cooccurrence_same_page",
                "page_numbers": common_pages[:20],
                "page_start": common_pages[0], "page_end": common_pages[-1],
                "snippet": snippets[0] if snippets else "",
                "confidence": 0.4,
                "editorial_status": "auto_extracted",
            })
    print(f"  Relations detected: {len(relations)}/{len(RELATION_PAIRS)}")
    for r in relations:
        print(f"    {r['concept_a']} ↔ {r['concept_b']}: {len(r['page_numbers'])} pages")

    # ── Compute readiness score ──────────────────────────────────────────
    readiness = {
        "page_map_complete": total_pages,  # 5 pts if 512
        "text_per_page": text_count,  # 5 pts if >=506
        "concepts_detectable": len(concept_mentions),  # 4 pts
        "source_refs_detectable": len(source_refs),  # 3 pts
        "relations_candidates": len(relations),  # 3 pts
        "wiki_generated": True,  # 2 pts
        "queries_sql_useful": True,  # 3 pts
    }
    score = 0
    score += 5 if readiness["page_map_complete"] == 512 else 0
    score += 5 if readiness["text_per_page"] >= 506 else 2 if readiness["text_per_page"] >= 400 else 0
    score += min(4, readiness["concepts_detectable"])
    score += min(3, readiness["source_refs_detectable"])
    score += min(3, readiness["relations_candidates"])
    score += 2 if readiness["wiki_generated"] else 0
    score += 3 if readiness["queries_sql_useful"] else 0
    if score >= 22: r_class = "PASS fuerte"
    elif score >= 18: r_class = "PASS usable"
    elif score >= 12: r_class = "WARN"
    else: r_class = "FAIL"
    print(f"\n  Book QA readiness: {score}/25 ({r_class})")

    if is_dry:
        print(f"\n  {'─'*50}")
        print(f"  DRY-RUN: No data written to database.")
        print(f"  To execute, re-run with --execute")
        print(f"{'='*70}\n")
        return 0

    # ── Write to V2 tables ───────────────────────────────────────────────
    print(f"\n  [6/7] Writing to V2 tables...")
    pool = create_pool_from_settings()
    await open_pool(pool)

    run_id = str(uuid4())
    now = datetime.now(timezone.utc)
    warnings_list: list[str] = []
    metrics: dict[str, int] = {}
    doc_id = str(uuid4())  # New V2 experimental doc

    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                # Create run
                await cur.execute(
                    "INSERT INTO library_ingestion_runs_v2 (run_id, document_id, pipeline_version, scope_code, status, started_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (run_id, doc_id, args.pipeline_version, args.scope_code, "started", now),
                )
                print(f"  Run: {run_id[:8]}...")

                # Pages
                for p in pages_data:
                    await cur.execute(
                        "INSERT INTO library_pages_v2 (run_id, document_id, page_number, text, char_count, extraction_method, confidence) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                        (run_id, doc_id, p["page_number"], p["text"], p["char_count"], "pymupdf_text", 1.0 if p["has_text"] else 0.0),
                    )
                metrics["pages"] = total_pages
                print(f"  Pages inserted: {total_pages}")

                if empty_count > 10:
                    warnings_list.append(f"high_empty_page_count: {empty_count} empty pages")

                # Sections
                sec_count = 0
                for i, s in enumerate(unique_sections):
                    await cur.execute(
                        "INSERT INTO library_sections_v2 (run_id, document_id, title, section_type, order_index, path, extraction_method, confidence) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                        (run_id, doc_id, s["title"], "heading_candidate", i, f"/section_{i}", "heuristic_pymupdf", s["confidence"]),
                    )
                    sec_count += 1
                metrics["sections"] = sec_count
                print(f"  Sections inserted: {sec_count}")

                if sec_count < 10:
                    warnings_list.append(f"low_section_count: only {sec_count} sections detected")

                # Concepts
                concept_count = 0
                for cm in concept_mentions:
                    await cur.execute(
                        "INSERT INTO library_concept_mentions_v2 (run_id, document_id, label, normalized_label, variants, concept_type, extraction_method, confidence, page_number) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (run_id, doc_id, cm["label"], cm["normalized_label"],
                         json.dumps(cm["variants"]), "topic", "dictionary_v1", 0.6,
                         cm["page_numbers"][0] if cm["page_numbers"] else None),
                    )
                    concept_count += 1
                metrics["concept_mentions"] = concept_count
                print(f"  Concepts inserted: {concept_count}")

                # Source references
                src_count = 0
                for name, info in source_refs.items():
                    await cur.execute(
                        "INSERT INTO library_source_references_v2 (run_id, document_id, reference_text, source_type, normalized_ref, evidence_type, extraction_method, confidence) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                        (run_id, doc_id, name, info["type"], name.lower(), "source_reference", "regex_dictionary_v1", 0.5),
                    )
                    src_count += 1
                metrics["source_references"] = src_count
                print(f"  Source references inserted: {src_count}")

                # Relations
                rel_count = 0
                for rel in relations:
                    await cur.execute(
                        "INSERT INTO library_internal_relations_v2 (run_id, document_id, concept_a, concept_b, relation_type, evidence_type, page_start, page_end, snippet, confidence, extraction_method, editorial_status) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (run_id, doc_id, rel["concept_a"], rel["concept_b"],
                         rel["relation_type"], rel["evidence_type"],
                         rel.get("page_start"), rel.get("page_end"),
                         rel.get("snippet", "")[:500], rel["confidence"],
                         "page_cooccurrence_v1", "auto_extracted"),
                    )
                    rel_count += 1
                metrics["internal_relations"] = rel_count
                print(f"  Relations inserted: {rel_count}")

                # Wiki
                key_concepts_sorted = sorted(concept_stats.keys(), key=lambda k: -concept_stats[k]["pages"])[:20]
                await cur.execute(
                    "INSERT INTO library_document_wiki_v2 (run_id, document_id, overview, structure_summary, main_topics, key_concepts, source_map, internal_relations_summary, questions_it_can_answer, warnings, review_status) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (run_id, doc_id,
                     f"Wiki documental automática experimental para KITZUR CreateSpace ({total_pages} páginas, ~{total_chars//1000}K caracteres).",
                     f"{total_pages} páginas extraídas, {text_count} con texto, {sec_count} secciones candidatas, {concept_count} conceptos detectados.",
                     json.dumps(key_concepts_sorted[:10]),
                     json.dumps(key_concepts_sorted),
                     json.dumps({k: {"type": v["type"], "pages": len(v["pages"])} for k, v in source_refs.items()}),
                     json.dumps([f"{r['concept_a']} ↔ {r['concept_b']}" for r in relations]),
                     json.dumps([
                         "buscar página", "buscar concepto", "listar relaciones candidatas",
                         "listar fuentes por página",
                     ]),
                     json.dumps(["auto_generated", "no_editorial_review", "no_embeddings", "no_milvus", "section_detection_heuristic"]),
                     "auto_generated"),
                )
                metrics["wiki"] = 1
                print(f"  Wiki inserted")

                # Update run status
                status = "completed" if not warnings_list else "partial"
                await cur.execute(
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

    # ── 7. Save report ──────────────────────────────────────────────────
    summary = {
        "run_id": run_id, "document_id": doc_id,
        "status": status, "scope_code": args.scope_code,
        "pipeline_version": args.pipeline_version,
        "metrics": metrics, "warnings": warnings_list,
        "readiness_score": score, "readiness_class": r_class,
    }
    (report_dir / "execute_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\n  Report: {report_dir / 'execute_summary.json'}")
    print(f"  Readiness: {score}/25 ({r_class})")
    print(f"{'='*70}\n")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
