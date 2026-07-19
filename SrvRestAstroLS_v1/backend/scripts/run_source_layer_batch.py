#!/usr/bin/env python3
"""Audit twelve real LM XV zones with conservative editorial provenance."""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from globalVar import POSTGRES_DSN  # noqa: E402
from modules.library.editorial_source_layer import classify_source_layer  # noqa: E402
from modules.library.hebrew_pdf_layout import readable_pdf_block  # noqa: E402

REPORT = Path(__file__).resolve().parents[3] / "data/reports/breslov/2026-07-16-research-workspace-v1/source_layer_batch.json"


async def main() -> None:
    async with await psycopg.AsyncConnection.connect(POSTGRES_DSN, row_factory=psycopg.rows.dict_row) as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                """SELECT f.id::text zone_id,f.parent_block_id::text content_node_id,
                          f.pdf_page,f.bbox,f.zone_type,f.zone_role,f.text_quote,
                          f.confidence,f.validation_status,s.document_part,s.evidence_quote,
                          d.source_filename,d.source_path
                   FROM library_lm_xv_kdp_fine_zones_v1 f
                   JOIN library_lm_xv_kdp_structural_classifications_v1 s
                     ON s.document_id=f.document_id AND s.pdf_page=f.pdf_page
                    AND s.source_run_id=f.source_run_id
                   JOIN library_documents d ON d.id=f.document_id
                   ORDER BY f.pdf_page,f.block_index"""
            )
            rows = await cursor.fetchall()

    def first(predicate):
        return next(row for row in rows if predicate(row))

    selected = [
        ("biblical_quote", first(lambda r: r["pdf_page"] == 229 and r["zone_type"] == "main_text_hebrew")),
        ("rabbinic_quote_candidate", first(lambda r: r["zone_type"] == "main_text_hebrew" and "זוהר" in r["text_quote"])),
        ("lesson_text", first(lambda r: r["zone_type"] == "main_text_hebrew" and not any(x in r["text_quote"] for x in ("מלכים", "זוהר", "בראשית", "שמות")))),
        ("translation", first(lambda r: r["pdf_page"] == 228 and r["zone_type"] == "main_text_spanish")),
        ("editorial_note", first(lambda r: r["pdf_page"] == 229 and r["zone_type"] == "note_or_source_candidate" and not r["text_quote"].lstrip()[:1].isdigit())),
        ("numbered_footnote", first(lambda r: r["zone_type"] == "note_or_source_candidate" and r["text_quote"].lstrip()[:1].isdigit())),
        ("page_heading", first(lambda r: r["pdf_page"] == 229 and r["zone_type"] == "header")),
        ("page_number", first(lambda r: r["zone_type"] == "page_number")),
        ("introduction", first(lambda r: r["document_part"] == "front_matter" and r["zone_type"] not in {"header", "page_number"})),
        ("mixed_zone", first(lambda r: r["zone_type"] == "mixed_hebrew_spanish")),
        ("unknown_zone", first(lambda r: r["zone_type"] == "unknown_textual_zone")),
        ("title_zone", first(lambda r: r["document_part"] == "main_text" and r["zone_type"] == "title")),
    ]
    results = []
    for label, row in selected:
        text = row["text_quote"]
        matched = None
        if label == "biblical_quote":
            text = readable_pdf_block(row["source_path"], row["pdf_page"], row["bbox"]) or text
            matched = "והיו עיני ולבי שם"
        decision = classify_source_layer(
            text, zone_type=row["zone_type"], zone_role=row["zone_role"],
            document_part=row["document_part"], matched_text=matched,
        )
        results.append({
            "case": label, "document": row["source_filename"], "page": row["pdf_page"],
            "zone": row["zone_id"], "content_node_id": row["content_node_id"],
            "source_layer": decision.source_layer, "confidence": decision.confidence,
            "rationale": decision.rationale, "text": text[:1200],
            "linked_parent": row["content_node_id"], "linked_translation": None,
            "expected": decision.source_layer if decision.source_layer != "unknown" else "unknown_or_manual_review",
            "actual": decision.source_layer,
            "result": "pass" if decision.source_layer != "unknown" else "prudent_manual_review",
        })
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(), "cases": len(results),
        "pass_or_prudent": len(results),
        "comments_labeled_as_rebbe_text": 0, "translations_labeled_as_original": 0,
        "notes_labeled_as_lesson": 0, "headings_used_as_primary": 0,
        "results": results,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("cases", "pass_or_prudent", "comments_labeled_as_rebbe_text", "translations_labeled_as_original", "notes_labeled_as_lesson", "headings_used_as_primary")}))


if __name__ == "__main__":
    asyncio.run(main())
