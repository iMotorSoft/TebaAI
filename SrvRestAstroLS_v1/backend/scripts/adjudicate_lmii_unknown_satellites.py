"""Re-adjudicate LM II citable fallback satellites through the audited AI flow.

Usage: ``uv run python scripts/adjudicate_lmii_unknown_satellites.py --limit 1``.
The default processes the current fallback cohort. It preserves a per-node history in
``metadata_json`` and emits machine-readable decision records to stdout.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from globalVar import POSTGRES_DSN
from modules.library.ai_note_continuity_analyzer import PROMPT_VERSION, analyze

DOCUMENT_CODE = "likutey_moharan_ii_spanish_bri"


def note_number(text: str) -> str | None:
    match = re.match(r"\s*(\d{1,3})[.)]", text or "")
    return match.group(1) if match else None


async def fetch_candidates(conn: psycopg.AsyncConnection[Any], limit: int | None = None, include_processed: bool = False) -> list[dict[str, Any]]:
    async with conn.cursor() as cur:
        await cur.execute(
            """SELECT n.content_node_id, n.content_unit_id, n.node_order, n.literal_text,
                      n.link_status, n.review_status, n.metadata_json, a.pdf_page_number,
                      u.canonical_ref, u.title
                 FROM library_content_nodes_v2 n
                 JOIN library_page_anchors_v2 a ON a.page_anchor_id=n.page_anchor_id
                 JOIN library_content_units_v2 u ON u.content_unit_id=n.content_unit_id
                WHERE u.document_id=(SELECT id FROM library_documents WHERE document_code=%s)
                  AND n.node_role='satellite'
                  AND n.citable=true
                  AND n.review_status='fallback_unlinked'
                ORDER BY a.pdf_page_number, n.node_order""",
            (DOCUMENT_CODE,),
        )
        candidates = await cur.fetchall()
        # A low-confidence result remains fallback_unlinked, but must not be called
        # repeatedly within the same prompt-version run.
        if not include_processed:
            candidates = [
                row for row in candidates
                if not any(
                    item.get("prompt_version") == PROMPT_VERSION
                    for item in (row["metadata_json"].get("ai_note_adjudication_history", []) if row["metadata_json"] else [])
                )
            ]
        if limit is not None:
            candidates = candidates[:limit]
        await cur.execute(
            """SELECT n.content_node_id, n.literal_text, n.node_order, a.pdf_page_number,
                      u.canonical_ref
                 FROM library_content_nodes_v2 n
                 JOIN library_page_anchors_v2 a ON a.page_anchor_id=n.page_anchor_id
                 JOIN library_content_units_v2 u ON u.content_unit_id=n.content_unit_id
                WHERE u.document_id=(SELECT id FROM library_documents WHERE document_code=%s)
                  AND n.content_type='numbered_footnote'
                ORDER BY a.pdf_page_number, n.node_order""",
            (DOCUMENT_CODE,),
        )
        notes = await cur.fetchall()
        await cur.execute(
            """SELECT a.pdf_page_number, n.literal_text
                 FROM library_content_nodes_v2 n
                 JOIN library_page_anchors_v2 a ON a.page_anchor_id=n.page_anchor_id
                 JOIN library_content_units_v2 u ON u.content_unit_id=n.content_unit_id
                WHERE u.document_id=(SELECT id FROM library_documents WHERE document_code=%s)
                  AND n.node_role='primary'
                ORDER BY a.pdf_page_number, n.node_order""",
            (DOCUMENT_CODE,),
        )
        primary_by_page = {row["pdf_page_number"]: row["literal_text"] for row in await cur.fetchall()}
    result: list[dict[str, Any]] = []
    for candidate in candidates:
        earlier = [note for note in notes if (note["pdf_page_number"], note["node_order"]) < (candidate["pdf_page_number"], candidate["node_order"])]
        later = [note for note in notes if (note["pdf_page_number"], note["node_order"]) > (candidate["pdf_page_number"], candidate["node_order"])]
        previous = earlier[-1] if earlier else None
        next_note = later[0] if later else None
        page = candidate["pdf_page_number"]
        lesson_match = re.search(r"(?:Lecci[oó]n|Lesson)\s*(\d+)", candidate["canonical_ref"] or "", re.I)
        result.append({
            **candidate,
            "previous_note": previous,
            "next_note": next_note,
            "payload": {
                "candidate_block_text": candidate["literal_text"],
                "candidate_physical_page": page,
                "candidate_geometry": candidate["metadata_json"].get("geometry") if candidate["metadata_json"] else None,
                "previous_numbered_note_text": previous["literal_text"] if previous else None,
                "previous_note_number": note_number(previous["literal_text"]) if previous else None,
                "previous_note_page": previous["pdf_page_number"] if previous else None,
                "next_numbered_note_text": next_note["literal_text"] if next_note else None,
                "same_page_primary_text": primary_by_page.get(page),
                "previous_page_primary_text": primary_by_page.get(page - 1),
                "next_page_primary_text": primary_by_page.get(page + 1),
                "lesson": lesson_match.group(1) if lesson_match else None,
                "section": candidate["canonical_ref"],
                "nearby_markers": [], "nearby_headers": [candidate["title"]],
                "layout_classification": "lower_unmarked_block",
                "deterministic_candidate_reasons": ["citable lower-page satellite without explicit marker"],
            },
        })
    return result


async def persist_decision(conn: psycopg.AsyncConnection[Any], candidate: dict[str, Any], decision: Any, run_id: str) -> dict[str, Any]:
    previous = candidate["previous_note"]
    linked = (
        decision.decision == "continuation_of_previous_note"
        and decision.confidence >= 0.85
        and previous is not None
        and decision.raw.get("target_note_number") == note_number(previous["literal_text"])
        and decision.raw.get("target_page") == previous["pdf_page_number"]
    )
    unmarked = decision.decision == "new_unmarked_note" and decision.confidence >= 0.85
    content_type = "numbered_footnote_continuation" if linked else "citable_unlinked_note"
    link_status = "linked_ai_verified" if linked else "unlinked_citable"
    review_status = "ai_verified" if (linked or unmarked) else ("needs_human_review" if decision.confidence >= .70 else "fallback_unlinked")
    raw_hash = hashlib.sha256(decision.raw_response.encode()).hexdigest() if decision.raw_response else None
    audit = {
        "adjudication_run_id": run_id, "previous_status": candidate["review_status"],
        "new_status": review_status, "prompt_version": PROMPT_VERSION,
        "model_name": decision.model_name, "raw_response_hash": raw_hash,
        "raw_request_json": decision.raw_request, "raw_response_text": decision.raw_response,
        "parsed_response_json": decision.raw, "parse_status": decision.parse_status,
        "decision": decision.decision, "confidence": decision.confidence,
        "rationale": decision.rationale, "fallback_reason": decision.fallback_reason,
    }
    async with conn.cursor() as cur:
        await cur.execute(
            """UPDATE library_content_nodes_v2
                  SET content_type=%s, authority_level='secondary_explanatory', citable=true,
                      link_status=%s, review_status=%s, ai_confidence=%s, ai_rationale=%s,
                      ai_prompt_version=%s,
                      metadata_json=metadata_json || jsonb_build_object(
                        'ai_note_adjudication_history',
                        COALESCE(metadata_json->'ai_note_adjudication_history', '[]'::jsonb) || jsonb_build_array(%s::jsonb))
                WHERE content_node_id=%s""",
            (content_type, link_status, review_status, decision.confidence, decision.rationale,
             PROMPT_VERSION, json.dumps(audit, ensure_ascii=False), candidate["content_node_id"]),
        )
        relation_created = False
        if linked:
            await cur.execute(
                """INSERT INTO library_content_relations_v2
                   (source_content_node_id,target_content_node_id,relation_type,evidence_type,confidence,
                    explanation,metadata_json,relation_origin,rationale,prompt_version,model_name)
                   SELECT %s,%s,'continuation_of','editorial_explanation',%s,%s,%s::jsonb,
                          'ai_interpreted',%s,%s,%s
                   WHERE NOT EXISTS (
                      SELECT 1 FROM library_content_relations_v2
                       WHERE source_content_node_id=%s AND target_content_node_id=%s AND relation_type='continuation_of')""",
                (candidate["content_node_id"], previous["content_node_id"], decision.confidence,
                 decision.rationale, json.dumps({"adjudication_run_id": run_id, "raw_response_hash": raw_hash}),
                 decision.rationale, PROMPT_VERSION, decision.model_name,
                 candidate["content_node_id"], previous["content_node_id"]),
            )
            relation_created = cur.rowcount == 1
    return {"candidate_id": str(candidate["content_node_id"]), "physical_page": candidate["pdf_page_number"],
            "lesson": candidate["payload"]["lesson"], "candidate_text": candidate["literal_text"],
            "previous_note_text": candidate["payload"]["previous_numbered_note_text"],
            "next_note_text": candidate["payload"]["next_numbered_note_text"], **audit,
            "relation_created": relation_created, "target_content_node_id": str(previous["content_node_id"]) if linked else None}


async def main(limit: int | None = None, dry_run: bool = False, output_path: Path | None = None) -> list[dict[str, Any]]:
    run_id = str(uuid.uuid4())
    async with await psycopg.AsyncConnection.connect(POSTGRES_DSN, row_factory=dict_row) as conn:
        candidates = await fetch_candidates(conn, limit)
        output = []
        for candidate in candidates:
            decision = await analyze(candidate["payload"])
            if dry_run:
                output.append({"candidate_id": str(candidate["content_node_id"]), "decision": decision.decision,
                               "confidence": decision.confidence, "parse_status": decision.parse_status})
            else:
                output.append(await persist_decision(conn, candidate, decision, run_id))
        if not dry_run:
            await conn.commit()
    rendered = json.dumps(output, ensure_ascii=False, default=str, indent=2)
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    asyncio.run(main(args.limit, args.dry_run, args.output))
