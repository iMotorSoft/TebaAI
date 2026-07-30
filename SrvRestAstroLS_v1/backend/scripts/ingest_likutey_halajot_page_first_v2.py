"""
Ingestion V2 — Likutey Halajot page-first with editorial structure.

PDF: LIKUTEY HALAJOT (Interior Final).pdf SHA256:440d4fd3...
- Stores full pages in library_pages_v2
- Extracts editorial zones
- Generates search chunks with normalized text
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

import fitz
import psycopg
from psycopg.rows import dict_row

from globalVar import POSTGRES_DSN

# ── Configuration ─────────────────────────────────────────────────────────
SOURCE = Path("/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf")
DOCUMENT_CODE = "likutey_halajot_interior_final_v2"
PIPELINE_VERSION = "likutey_halajot_page_first_v2"
EDITION_ID = "likutey_halajot_interior_final_v2"
EXPECTED_SHA256 = "440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a"

# ── Patterns ──────────────────────────────────────────────────────────────
_HEADING_RE = re.compile(
    r"^(\d+)\s*[■▪•]\s*([A-ZÁÉÍÓÚÜÑ][A-ZÁÉÍÓÚÜÑ\sáéíóúüñ]+)",
    re.MULTILINE | re.UNICODE,
)
_PRINTED_PAGE_RE = re.compile(r"^\s*(\d+)\s*$", re.MULTILINE)
_NOTES_HEADER_RE = re.compile(r"Notas\s*y\s*Fuentes", re.UNICODE)
_FOOTNOTE_MARKER_RE = re.compile(r"\.(\d{1,2})(?:\s|$|\))")
_FOOTNOTE_START_RE = re.compile(r"^(\d{1,2})\s")
_HEBREW_BASE_RE = re.compile(r"[\u05d0-\u05ea]")


def stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def get_page_text(page: fitz.Page) -> str:
    """Extract and clean text from a PDF page."""
    return page.get_text("text").replace("\x00", "").strip()


def detect_language(text: str) -> str:
    """Detect if text is predominantly Hebrew, mixed, or Spanish."""
    heb_chars = len(_HEBREW_BASE_RE.findall(text))
    total = len(text.strip())
    if total == 0:
        return "und"
    ratio = heb_chars / total
    if ratio > 0.15:
        return "he" if ratio > 0.4 else "mixed"
    return "es"


def extract_printed_page(full_text: str) -> int | None:
    """Extract printed page number from first line."""
    lines = full_text.split("\n")
    for line in lines[:5]:
        line = line.strip()
        m = _PRINTED_PAGE_RE.match(line)
        if m:
            return int(m.group(1))
    return None


def detect_headings(full_text: str) -> list[dict[str, Any]]:
    """Detect section headings in page text."""
    headings = []
    for m in _HEADING_RE.finditer(full_text):
        headings.append({
            "number": int(m.group(1)),
            "title": m.group(2).strip(),
            "full": m.group(0).strip(),
            "position": m.start(),
        })
    return headings


def detect_footnote_zone(full_text: str) -> list[dict[str, Any]]:
    """Detect footnote area and individual footnotes."""
    notes = []
    lines = full_text.split("\n")
    in_notes = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if _NOTES_HEADER_RE.search(stripped):
            in_notes = True
            continue
        if in_notes and stripped:
            m = _FOOTNOTE_START_RE.match(stripped)
            if m:
                notes.append({
                    "number": int(m.group(1)),
                    "text": stripped,
                    "line": i,
                })
    return notes


def detect_footnote_markers(full_text: str) -> list[tuple[int, int]]:
    """Find footnote markers like .35 in body text."""
    markers = []
    for m in _FOOTNOTE_MARKER_RE.finditer(full_text):
        markers.append((int(m.group(1)), m.start()))
    return markers


def page_footnote_text(notes: list[dict[str, Any]], number: int) -> str:
    """Assemble footnote text for a given number."""
    parts = []
    for note in notes:
        if note["number"] == number:
            # Remove leading number
            text = re.sub(rf"^{number}\s*", "", note["text"], count=1).strip()
            parts.append(text)
    return " ".join(parts)


async def main() -> None:
    start = time.perf_counter()
    
    # ── Validate PDF ──────────────────────────────────────────────────
    if not SOURCE.is_file():
        raise SystemExit(f"Source PDF unavailable: {SOURCE}")
    source_sha = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    if source_sha != EXPECTED_SHA256:
        raise SystemExit(f"SHA mismatch: expected {EXPECTED_SHA256}, got {source_sha}")
    print(f"PDF verified: {SOURCE.name} ({SOURCE.stat().st_size} bytes, {EXPECTED_SHA256[:16]}...)")

    document = fitz.open(SOURCE)
    total_pages = len(document)
    print(f"Opening PDF: {total_pages} pages")

    # ── Connect ───────────────────────────────────────────────────────
    async with await psycopg.AsyncConnection.connect(POSTGRES_DSN, row_factory=dict_row) as conn:
        async with conn.cursor() as cur:
            # ── Create document record ────────────────────────────────
            template = await cur.execute(
                """SELECT collection_id, knowledge_scope_id, organization_id, workspace_id, project_id
                   FROM library_documents WHERE document_code = 'likutey_moharan_ii_spanish_bri'"""
            )
            base = await template.fetchone()
            if not base:
                raise RuntimeError("Template document unavailable")

            doc_id = str(uuid4())
            await cur.execute(
                """INSERT INTO library_documents(
                       id, collection_id, title, language, source_type, source_path, source_filename,
                       source_mime_type, source_size_bytes, source_sha256, status, metadata,
                       bibliographic_metadata, organization_id, workspace_id, project_id,
                       knowledge_scope_id, document_code, canonical_text_role)
                   VALUES(%s, %s, 'Likutey Halajot — Interior Final', 'es', 'pdf', %s, %s,
                       'application/pdf', %s, %s, 'test_candidate', %s::jsonb, %s::jsonb,
                       %s, %s, %s, %s, %s, 'candidate') RETURNING id""",
                (
                    doc_id, base["collection_id"],
                    str(SOURCE), SOURCE.name, SOURCE.stat().st_size, source_sha,
                    json.dumps({"pipeline": PIPELINE_VERSION, "physical_pages": total_pages}),
                    json.dumps({"edition": "Interior Final", "physical_file_verified": True}),
                    base["organization_id"], base["workspace_id"], base["project_id"],
                    base["knowledge_scope_id"], DOCUMENT_CODE,
                ),
            )
            print(f"Document ID: {doc_id}")

            # ── Ingestion run ─────────────────────────────────────────
            run_id = str(uuid4())
            await cur.execute(
                """INSERT INTO library_ingestion_runs_v2(
                       run_id, document_id, pipeline_version, scope_code, status, started_at)
                   VALUES(%s, %s, %s, 'breslov_research', 'started', now())""",
                (run_id, doc_id, PIPELINE_VERSION),
            )

            # ── Document text record (required by chunk FK) ──────────
            doc_text_id = str(uuid4())
            await cur.execute(
                """INSERT INTO library_document_texts(
                       id, document_id, text_format, content, content_sha256, content_length,
                       extraction_method, page_count, text_role, page_markers_enabled)
                   VALUES(%s, %s, 'markdown', 'placeholder', %s, 0, 'page_first_v2', %s, 'canonical', false)""",
                (doc_text_id, doc_id, stable_hash('placeholder'), total_pages),
            )
            print(f"Document text ID: {doc_text_id}")

            # ── Work unit ─────────────────────────────────────────────
            await cur.execute(
                """INSERT INTO library_content_units_v2(
                       document_id, unit_type, canonical_ref, title, order_index,
                       language_original, is_breslov_primary_source, is_direct_rebbe_nachman,
                       source_run_id, metadata_json)
                   VALUES(%s, 'work', 'LH-V2', 'Likutey Halajot — Interior Final', 1,
                       'he', true, false, %s, %s::jsonb)
                   RETURNING content_unit_id""",
                (doc_id, run_id, json.dumps({"pipeline": PIPELINE_VERSION})),
            )
            work_unit_id = (await cur.fetchone())["content_unit_id"]

            # ── Process each page ─────────────────────────────────────
            textual_pages = 0
            current_heading = None
            
            for page_num in range(1, total_pages + 1):
                page = document[page_num - 1]
                full_text = get_page_text(page)
                
                # Page metadata
                printed_page = extract_printed_page(full_text)
                language = detect_language(full_text)
                headings = detect_headings(full_text)
                notes = detect_footnote_zone(full_text)
                markers = detect_footnote_markers(full_text)
                
                # Update current heading from detected headings
                for h in headings:
                    current_heading = h["full"]
                
                # ── Store page in library_pages_v2 ────────────────────
                await cur.execute(
                    """INSERT INTO library_pages_v2(
                           run_id, document_id, page_number, text, char_count,
                           extraction_method, confidence, layout_notes)
                       VALUES(%s, %s, %s, %s, %s, 'pymupdf_text_v2', 0.90, %s::jsonb)
                       RETURNING page_id""",
                    (run_id, doc_id, page_num, full_text, len(full_text),
                     json.dumps({
                         "sha256": stable_hash(full_text),
                         "printed_page": printed_page,
                         "language": language,
                         "heading": current_heading,
                         "headings_count": len(headings),
                         "footnotes_count": len(notes),
                         "markers_count": len(markers),
                     })),
                )
                legacy_page_id = (await cur.fetchone())["page_id"]

                # ── Page anchor ───────────────────────────────────────
                await cur.execute(
                    """INSERT INTO library_page_anchors_v2(
                           source_file_id, document_id, edition_id, pdf_page_number,
                           printed_page_number, page_label, section_page_label,
                           legacy_page_id, confidence, metadata_json)
                       VALUES(%s, %s, %s, %s, %s, %s, %s, %s, 0.99, %s::jsonb)
                       ON CONFLICT(document_id, pdf_page_number, edition_id)
                       DO UPDATE SET printed_page_number=EXCLUDED.printed_page_number,
                           section_page_label=EXCLUDED.section_page_label,
                           legacy_page_id=EXCLUDED.legacy_page_id
                       RETURNING page_anchor_id""",
                    (
                        doc_id, doc_id, EDITION_ID, page_num, printed_page,
                        str(printed_page) if printed_page else None,
                        current_heading, legacy_page_id,
                        json.dumps({"sha256": source_sha, "pipeline": PIPELINE_VERSION}),
                    ),
                )
                anchor_id = (await cur.fetchone())["page_anchor_id"]

                if not full_text.strip():
                    continue
                textual_pages += 1

                # ── Content Unit (page level) ─────────────────────────
                canonical_ref = f"LH-V2-PDF-{page_num:04d}"
                await cur.execute(
                    """INSERT INTO library_content_units_v2(
                           parent_content_unit_id, document_id, unit_type, canonical_ref,
                           title, order_index, language_original, is_breslov_primary_source,
                           is_direct_rebbe_nachman, source_run_id, metadata_json)
                       VALUES(%s, %s, 'page', %s, %s, %s, %s, true, false, %s, %s::jsonb)
                       ON CONFLICT(document_id, canonical_ref)
                       WHERE canonical_ref IS NOT NULL
                       DO UPDATE SET title=EXCLUDED.title
                       RETURNING content_unit_id""",
                    (work_unit_id, doc_id, canonical_ref, current_heading or f"PDF page {page_num}",
                     page_num, language, run_id,
                     json.dumps({"printed_page": printed_page, "heading": current_heading})),
                )
                page_unit_id = (await cur.fetchone())["content_unit_id"]

                # ── Normalize text for search ─────────────────────────
                normalized = full_text.casefold()
                literal_hash = stable_hash(full_text)

                # ── Content Node (page-level text) ────────────────────
                await cur.execute(
                    """INSERT INTO library_content_nodes_v2(
                           content_unit_id, node_role, content_type, relation_to_primary,
                           authority_level, language, script, literal_text, normalized_text,
                           literal_hash, page_anchor_id, node_order, citable, source_run_id,
                           metadata_json, link_status, review_status)
                       VALUES(%s, 'satellite', 'citable_page_text', 'same_page',
                           'secondary_explanatory', %s, 'mixed', %s, %s, %s, %s,
                           1, true, %s, %s::jsonb, 'linked', 'deterministic')
                       RETURNING content_node_id""",
                    (page_unit_id, language, full_text, normalized, literal_hash,
                     anchor_id, run_id,
                     json.dumps({
                         "pipeline": PIPELINE_VERSION,
                         "printed_page": printed_page,
                         "heading": current_heading,
                     })),
                )
                node_id = (await cur.fetchone())["content_node_id"]

                # ── Literal span ──────────────────────────────────────
                await cur.execute(
                    """INSERT INTO library_literal_spans_v2(
                           content_node_id, start_char, end_char, literal_text,
                           normalized_text, hash, metadata_json)
                       VALUES(%s, 0, %s, %s, %s, %s, %s::jsonb)""",
                    (node_id, len(full_text), full_text, normalized, literal_hash,
                     json.dumps({"normalizer": "casefold_v1"})),
                )

                # ── Semantic unit (chunk) ─────────────────────────────
                await cur.execute(
                    """INSERT INTO library_semantic_units_v2(
                           content_node_id, text, text_hash, chunk_order,
                           chunker_name, language, source_run_id, metadata_json)
                       VALUES(%s, %s, %s, 1, 'page_first_v2', %s, %s, %s::jsonb)
                       RETURNING semantic_unit_id""",
                    (node_id, full_text, literal_hash, language, run_id,
                     json.dumps({"vectorized": False})),
                )

                # ── ALSO populate library_document_chunks for search compatibility ──
                chunk_id = str(uuid4())
                content_sha = stable_hash(full_text)
                content_len = len(full_text)
                await cur.execute(
                    """INSERT INTO library_document_chunks(
                           id, document_id, document_text_id, collection_id,
                           chunk_index, chunk_uid, language, content,
                           content_sha256, content_length, page_start, page_end,
                           block_type, evidence_role, citable, search_text_normalized,
                           section_title, printed_page_label, metadata)
                       VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                           'page_first_v2', 'commentary', true, %s, %s, %s, %s::jsonb)""",
                    (chunk_id, doc_id, doc_text_id, base["collection_id"],
                     page_num, str(page_num), language, full_text,
                     content_sha, content_len, page_num, page_num,
                     normalized,
                     current_heading or "", str(printed_page) if printed_page else None,
                     json.dumps({
                         "pipeline": PIPELINE_VERSION,
                         "legacy_page_id": str(legacy_page_id),
                         "page_anchor_id": str(anchor_id),
                         "source": "page_first_v2",
                     })),
                )

                if page_num % 20 == 0:
                    print(f"  Page {page_num}/{total_pages}...")

            # ── Update run status ─────────────────────────────────────
            duration = round(time.perf_counter() - start, 2)
            await cur.execute(
                """UPDATE library_ingestion_runs_v2
                   SET status='completed', finished_at=now(),
                       metrics_json=%s::jsonb, warnings_json='[]'::jsonb
                   WHERE run_id=%s""",
                (json.dumps({
                    "physical_pages": total_pages,
                    "textual_pages": textual_pages,
                    "duration_sec": duration,
                    "sha256": source_sha,
                    "embeddings_generated": False,
                }), run_id),
            )

        await conn.commit()

    document.close()
    duration = round(time.perf_counter() - start, 2)
    print(f"\n=== INGESTION COMPLETE ===")
    print(f"  Document ID: {doc_id}")
    print(f"  Run ID: {run_id}")
    print(f"  Pages: {total_pages} (textual: {textual_pages})")
    print(f"  Duration: {duration}s")
    print(f"  Document code: {DOCUMENT_CODE}")
    print(f"  Status: test_candidate")


if __name__ == "__main__":
    asyncio.run(main())
