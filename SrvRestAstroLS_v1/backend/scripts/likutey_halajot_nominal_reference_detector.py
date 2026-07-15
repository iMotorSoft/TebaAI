"""Persist only quote-verified, literal nominal-reference metadata for Likutey Halajot."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg
from psycopg.rows import dict_row

from globalVar import POSTGRES_DSN
from modules.library.likutey_halajot_nominal_reference_catalog import catalog_matches

SOURCE_RUN = "likutey_halajot_page_first_v1"
STRUCTURAL_RUN = "likutey_halajot_structural_detector_v1_20260714"
FINE_ZONE_RUN = "likutey_halajot_fine_zone_detector_v1_20260714"
NOTE_SOURCE_RUN = "likutey_halajot_note_source_detector_v1_20260714"


@dataclass(frozen=True)
class Candidate:
    surface_form: str
    normalized_reference_name: str | None
    reference_kind: str
    char_start: int
    char_end: int
    confidence: float
    validation_status: str
    detection_method: str
    ambiguous: bool = False


def classify_script(value: str) -> tuple[str, str]:
    if re.search(r"[\u0590-\u05ff]", value):
        return "he", "hebrew"
    return "es", "latin"


def generic_matches(text: str) -> list[Candidate]:
    """Find a narrowly-scoped citation after an explicit literal citation marker.

    Generic candidates intentionally remain unnormalised and need editorial review.
    """
    candidates: list[Candidate] = []
    marker = re.compile(r"(?i)\b(?:ver|véase|citado en|cf\.)\s+([A-ZÁÉÍÓÚÑ][^\n.;:]{2,80})")
    for match in marker.finditer(text):
        value = match.group(1).strip().rstrip(",")
        # A lone honorific/common noun is not a nominal source.
        if re.fullmatch(r"(?i)(?:rebe|rav|rabí|rabino|torá)", value):
            continue
        start = match.start(1) + (len(match.group(1)) - len(match.group(1).lstrip()))
        candidates.append(Candidate(value, None, "generic_source", start, start + len(value), .70,
                                    "ambiguous_surface_form", "generic_literal_marker", True))
    return candidates


def find_candidates(text: str) -> list[Candidate]:
    result: list[Candidate] = []
    covered: set[tuple[int, int]] = set()
    for match, entry, canonical in catalog_matches(text):
        covered.add((match.start(), match.end()))
        result.append(Candidate(match.group(0), entry.canonical_name, entry.reference_kind,
                                match.start(), match.end(), .95 if canonical else .85,
                                "validated", "catalog_literal", not canonical))
    for candidate in generic_matches(text):
        if not any(candidate.char_start < end and candidate.char_end > start for start, end in covered):
            result.append(candidate)
    return result


def quote_context(text: str, start: int, end: int, radius: int = 120) -> str:
    return text[max(0, start - radius):min(len(text), end + radius)].strip()


async def fetch_parents(cur: psycopg.AsyncCursor[Any]) -> list[dict[str, Any]]:
    await cur.execute("""
        SELECT n.id AS parent_note_source_unit_id, NULL::uuid AS parent_fine_zone_id,
               n.document_id, n.pdf_page, a.printed_page_number AS printed_page, n.page_anchor_id, n.visible_note_number,
               n.halakhah_header_hint, n.unit_type AS parent_zone_type, n.unit_type,
               n.text_quote AS parent_literal, p.literal_text AS page_literal
        FROM library_likutey_halajot_note_source_units_v1 n
        JOIN library_page_anchors_v2 a ON a.page_anchor_id=n.page_anchor_id
        JOIN library_content_nodes_v2 p ON p.page_anchor_id=n.page_anchor_id
          AND p.metadata_json->>'source_run_id'=%s
        WHERE n.note_source_run_id=%s
        UNION ALL
        SELECT NULL::uuid, z.id, z.document_id, z.pdf_page, a.printed_page_number, z.page_anchor_id,
               z.visible_note_number, NULL, z.zone_type, z.zone_type, z.text_quote, p.literal_text
        FROM library_likutey_halajot_fine_zones_v1 z
        JOIN library_page_anchors_v2 a ON a.page_anchor_id=z.page_anchor_id
        JOIN library_content_nodes_v2 p ON p.page_anchor_id=z.page_anchor_id
          AND p.metadata_json->>'source_run_id'=%s
        WHERE z.fine_zone_run_id=%s
          AND z.zone_type IN ('glossary_entry','hebrew_quote','notes_sources_block')
        ORDER BY pdf_page
    """, (SOURCE_RUN, NOTE_SOURCE_RUN, SOURCE_RUN, FINE_ZONE_RUN))
    return await cur.fetchall()


async def detect(*, run_id: str, apply: bool) -> dict[str, Any]:
    summary = {"run": run_id, "apply": apply, "parents": 0, "candidates": 0, "inserted": 0,
               "rejected": 0, "ai": "ai_not_required_for_v1", "by_kind": {}}
    async with await psycopg.AsyncConnection.connect(POSTGRES_DSN, row_factory=dict_row) as conn:
        async with conn.cursor() as cur:
            parents = await fetch_parents(cur)
            summary["parents"] = len(parents)
            seen: set[tuple[str, str, int, int]] = set()
            for parent in parents:
                parent_literal = parent["parent_literal"] or ""
                page_literal = parent["page_literal"] or ""
                for candidate in find_candidates(parent_literal):
                    key = (str(parent["parent_note_source_unit_id"] or parent["parent_fine_zone_id"]), candidate.surface_form, candidate.char_start, candidate.char_end)
                    if key in seen:
                        continue
                    seen.add(key)
                    summary["candidates"] += 1
                    context = quote_context(parent_literal, candidate.char_start, candidate.char_end)
                    valid = (candidate.surface_form in parent_literal and context in parent_literal and context in page_literal)
                    if not valid:
                        summary["rejected"] += 1
                        continue
                    language, script = classify_script(candidate.surface_form)
                    summary["by_kind"][candidate.reference_kind] = summary["by_kind"].get(candidate.reference_kind, 0) + 1
                    if apply:
                        raw = {"candidate": asdict(candidate), "surface_in_parent": True,
                               "quote_in_parent": True, "quote_in_page_first": True,
                               "ai": "ai_not_required_for_v1"}
                        await cur.execute("""
                            INSERT INTO library_likutey_halajot_nominal_references_v1 (
                              document_id,document_code,pdf_page,printed_page,page_anchor_id,source_run_id,
                              structural_detector_run_id,fine_zone_run_id,note_source_run_id,nominal_reference_run_id,
                              parent_note_source_unit_id,parent_fine_zone_id,parent_zone_type,visible_note_number,
                              halakhah_header_hint,surface_form,normalized_reference_name,reference_kind,
                              reference_language,reference_script,marker_kind,marker_value,text_quote,text_start_quote,text_end_quote,
                              quote_hash,char_start,char_end,confidence,evidence_origin,detection_origin,
                              detection_method,validation_status,review_status,warnings,raw_detection)
                            VALUES (
                              %s,(SELECT document_code FROM library_documents WHERE id=%s),%s,
                              (SELECT printed_page_number FROM library_page_anchors_v2 WHERE page_anchor_id=%s),%s,%s,%s,%s,%s,%s,
                              %s,%s,%s,%s,%s,
                              %s,%s,%s,
                              %s,%s,%s,%s,
                              %s,%s,%s,%s,%s,%s,%s,
                              'literal_parent_and_page_first','deterministic',%s,%s,%s,
                              CASE WHEN %s THEN '["surface_variant"]'::jsonb ELSE '[]'::jsonb END,%s::jsonb)
                            ON CONFLICT (nominal_reference_run_id,parent_note_source_unit_id,parent_fine_zone_id,surface_form,char_start,char_end) DO NOTHING
                        """, (parent["document_id"], parent["document_id"], parent["pdf_page"], parent["page_anchor_id"], parent["page_anchor_id"], SOURCE_RUN, STRUCTURAL_RUN, FINE_ZONE_RUN, NOTE_SOURCE_RUN, run_id,
                              parent["parent_note_source_unit_id"], parent["parent_fine_zone_id"], parent["parent_zone_type"], parent["visible_note_number"], parent["halakhah_header_hint"], candidate.surface_form, candidate.normalized_reference_name, candidate.reference_kind,
                              language, script, candidate.detection_method, candidate.surface_form, context, parent_literal[:candidate.char_start], parent_literal[candidate.char_end:], hashlib.sha256(context.encode()).hexdigest(), candidate.char_start, candidate.char_end, candidate.confidence,
                              candidate.detection_method, candidate.validation_status, "needs_review" if candidate.ambiguous else "not_required", candidate.ambiguous, json.dumps(raw)))
                        summary["inserted"] += cur.rowcount
            if apply:
                await conn.commit()
    return summary


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default=f"likutey_halajot_nominal_reference_detector_v1_{date.today():%Y%m%d}")
    parser.add_argument("--apply", action="store_true", help="persist validated/ambiguous literal candidates")
    args = parser.parse_args()
    print(json.dumps(await detect(run_id=args.run_id, apply=args.apply), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
