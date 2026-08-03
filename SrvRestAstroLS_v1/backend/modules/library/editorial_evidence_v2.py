"""Editorial Evidence V2 — headings, references, footnotes with editorial anchoring.

Extends Page-First Evidence Contract V1 with:
- Editorial block role classification
- Printed reference detection and normalization
- Footnote body and marker resolution
- Intermediate heading tracking
- Heading→body association
"""

from __future__ import annotations

import hashlib
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# -- Editorial block roles -------------------------------------------------


class EditorialBlockRole(str, Enum):
    MAIN_BODY = "main_body"
    SECTION_HEADING = "section_heading"
    SUBSECTION_HEADING = "subsection_heading"
    MARGINAL_REFERENCE = "marginal_reference"
    FOOTNOTE_MARKER = "footnote_marker"
    FOOTNOTE_BODY = "footnote_body"
    NOTES_HEADING = "notes_heading"
    RUNNING_HEADER = "running_header"
    PAGE_NUMBER = "page_number"
    FOOTER = "footer"
    DECORATIVE_LABEL = "decorative_label"
    HEBREW_SOURCE = "hebrew_source"
    UNKNOWN = "unknown"


class ReferenceStatus(str, Enum):
    PRINTED_ONLY = "printed_reference_only"
    CONFIRMED = "confirmed"
    POSSIBLE_DISCREPANCY = "possible_editorial_discrepancy"
    UNRESOLVED = "unresolved"


# -- Editorial data models -------------------------------------------------


@dataclass(frozen=True)
class EditorialContext:
    """Editorial context for an evidence fragment."""
    block_role: EditorialBlockRole = EditorialBlockRole.UNKNOWN
    block_role_confidence: float = 1.0
    block_role_method: str = "block_type"
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PrintedReference:
    """A printed reference found in the text."""
    surface: str | None = None
    normalized: str | None = None
    reference_type: str = "biblical"
    source_layer: str = "marginal_reference"
    block_id: str | None = None
    page: int | None = None
    confidence: float = 1.0


@dataclass(frozen=True)
class CanonicalReference:
    """Canonical reference candidate when different from printed."""
    candidate: str | None = None
    status: ReferenceStatus = ReferenceStatus.PRINTED_ONLY
    warning: str | None = None


@dataclass(frozen=True)
class FootnoteInfo:
    """Footnote resolution data."""
    number: int | None = None
    body_text: str | None = None
    body_block_id: str | None = None
    page: int | None = None
    source_layer: str = "footnote"


@dataclass(frozen=True)
class FootnoteMarker:
    """Footnote marker resolution data."""
    marker_text: str | None = None
    marker_block_id: str | None = None
    marker_offset: int | None = None
    anchor_text: str | None = None
    anchor_block_id: str | None = None
    anchor_section: str | None = None
    anchor_section_path: list[str] = field(default_factory=list)
    next_heading: str | None = None
    next_heading_block_id: str | None = None
    resolution_method: str = "unresolved"
    confidence: float = 0.0
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class HeadingBodyAssociation:
    """Association between a heading and its body."""
    heading_text: str | None = None
    heading_block_id: str | None = None
    body_text: str | None = None
    body_block_id: str | None = None
    association_method: str = "adjacent_chunk"
    confidence: float = 1.0


# -- Editorial block classifier -------------------------------------------

_BLOCK_ROLE_MAP: dict[str, EditorialBlockRole] = {
    "page_header": EditorialBlockRole.PAGE_NUMBER,
    "source_hebrew": EditorialBlockRole.HEBREW_SOURCE,
    "section_marker": EditorialBlockRole.DECORATIVE_LABEL,
    "main_explanation_es": EditorialBlockRole.MAIN_BODY,
    "marginal_source": EditorialBlockRole.MARGINAL_REFERENCE,
    "footnote": EditorialBlockRole.FOOTNOTE_BODY,
}

_HEADING_PATTERN = re.compile(
    r"^\d+\s*[■▪•]\s*[A-ZÁÉÍÓÚÜÑ][A-ZÁÉÍÓÚÜÑ\sáéíóúüñ]+",
    re.UNICODE | re.MULTILINE,
)

_FOOTNOTE_MARKER_PATTERN = re.compile(r"\.(\d{1,2})(?:\s|$|\))")
_FOOTNOTE_NUMBER_PATTERN = re.compile(r"^(\d{1,2})\s")


def classify_editorial_block(
    chunk: dict[str, Any],
    page_chunks: list[dict[str, Any]] | None = None,
) -> EditorialContext:
    """Classify the editorial role of a chunk based on available metadata.

    Uses block_type, evidence_role, content analysis, and neighbor context.
    """
    block_type = str(chunk.get("block_type") or "")
    evidence_role = str(chunk.get("evidence_role") or "")
    content = str(chunk.get("markdown") or chunk.get("content") or "")
    content_stripped = content.strip()

    # 1. Content-based heading detection (before block_type, since headings can have any block_type)
    # Use the first line only for pattern matching (markdown may contain heading + body)
    first_line = content_stripped.split(chr(10))[0].strip() if content_stripped else ""
    if first_line and _HEADING_PATTERN.match(first_line):
        return EditorialContext(
            block_role=EditorialBlockRole.SECTION_HEADING,
            block_role_confidence=0.95,
            block_role_method="heading_pattern",
        )

    # 2. Notes heading
    if content_stripped in ("Notas y Fuentes", "Notas y Fuentes:", "Notes and Sources") or "1RWHV" in content:
        return EditorialContext(
            block_role=EditorialBlockRole.NOTES_HEADING,
            block_role_confidence=0.8,
            block_role_method="notes_heading_text",
        )

    # 3. Evidence role heuristics (before block_type, for cross-cutting roles)
    if evidence_role == "marginal_citation":
        return EditorialContext(
            block_role=EditorialBlockRole.MARGINAL_REFERENCE,
            block_role_confidence=0.85,
            block_role_method="evidence_role:marginal_citation",
        )

    # 4. Direct block_type mapping (only if still unclassified)
    if block_type in _BLOCK_ROLE_MAP:
        role = _BLOCK_ROLE_MAP[block_type]
        return EditorialContext(
            block_role=role,
            block_role_confidence=0.9,
            block_role_method=f"block_type:{block_type}",
        )

    # 5. Running header detection (short all-caps, page-like)
    if (
        block_type == "page_header"
        or content_stripped.startswith("LIKUTEY")
        or (content_stripped.isupper() and len(content_stripped) > 10 and len(content_stripped) < 60)
    ):
        return EditorialContext(
            block_role=EditorialBlockRole.RUNNING_HEADER,
            block_role_confidence=0.6,
            block_role_method="running_header_heuristic",
        )

    # 6. Default to main body
    return EditorialContext(
        block_role=EditorialBlockRole.MAIN_BODY,
        block_role_confidence=0.5,
        block_role_method="default_main_body",
    )


# -- Printed reference detection -------------------------------------------

_BIBLICAL_REFERENCE = re.compile(
    r"\(?\s*(Salmos|Salmo|Tehilim|Éxodo|Génesis|Levítico|Números|Deuteronomio|"
    r"Isaías|Jeremías|Ezequiel|Oseas|Joel|Amós|Abdías|Jonás|Miqueas|Nahúm|"
    r"Habacuc|Sofonías|Hageo|Zacarías|Malaquías|Proverbios|Proverbio|Job|Cantar|Rut|Lamentaciones|Eclesiastés|Ester|Daniel|Esdras|Nehemías|Crónicas|"
    r"Mateo|Marcos|Lucas|Juan|Hechos|Romanos|Corintios|Gálatas|Efesios|Filipenses|Colosenses|Tesalonicenses|"
    r"Timoteo|Tito|Filemón|Hebreos|Santiago|Pedro|Judas|Apocalipsis)"
    r"\s+"  # book name followed by whitespace
    r"(\d+)\s*[.:]\s*(\d+(?:[–-]\d+)?)"  # chapter:verse
    r"(?!\d)"  # never a prefix of a longer verse (16:1 must not match 16:10)
    r"\s*\)?",
    re.I,
)

_REFERENCE_WITH_BOOK = re.compile(
    r"\(?([A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+(?:\s+[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)?)"
    r"\s+(\d+)\s*[.:]\s*(\d+[-\d]*)\s*\)?",
    re.I,
)


def detect_printed_references(content: str) -> list[PrintedReference]:
    """Detect printed references (biblical or bibliographic) in text."""
    refs: list[PrintedReference] = []

    for match in _BIBLICAL_REFERENCE.finditer(content):
        book = match.group(1).strip()
        chapter = match.group(2)
        verse = match.group(3)
        surface = f"{book} {chapter}:{verse}"
        normalized = surface.lower().strip().replace("  ", " ")
        refs.append(PrintedReference(
            surface=surface,
            normalized=normalized,
            reference_type="biblical",
            confidence=0.95,
        ))

    return refs


# -- Footnote detection ----------------------------------------------------


def detect_footnote_number(content: str) -> int | None:
    """Extract footnote number from beginning of footnote block."""
    m = _FOOTNOTE_NUMBER_PATTERN.match(content.strip())
    if m:
        return int(m.group(1))
    return None


def detect_footnote_marker(content: str) -> list[tuple[int, int]]:
    """Detect footnote markers like '.35' or ' 35' in body text.

    Returns list of (number, end_position).
    """
    markers: list[tuple[int, int]] = []
    for m in _FOOTNOTE_MARKER_PATTERN.finditer(content):
        num = int(m.group(1))
        markers.append((num, m.end()))
    return markers


# -- Section timeline builder ----------------------------------------------


def build_section_timeline(
    page_chunks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build a timeline of sections for a page.

    Returns list of heading entries with their chunk ranges:
    [
        {"heading": "5 ■ INCLINADO...", "start_idx": 381, "end_idx": 411},
        {"heading": "6 ■ MELODÍAS...", "start_idx": 412, "end_idx": ...},
    ]
    """
    timeline: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    sorted_chunks = sorted(page_chunks, key=lambda c: c.get("chunk_index", 0) or 0)

    for chunk in sorted_chunks:
        content = str(chunk.get("markdown") or chunk.get("content") or "").strip()
        idx = chunk.get("chunk_index", 0)

        if content and _HEADING_PATTERN.match(content):
            if current:
                current["end_idx"] = idx - 1
                timeline.append(current)
            current = {
                "heading": content,
                "heading_chunk_id": str(chunk.get("chunk_id") or chunk.get("id") or ""),
                "start_idx": idx,
                "end_idx": idx,
                "heading_page": chunk.get("pdf_page") or chunk.get("page_start"),
            }
        elif current and current["start_idx"] <= idx:
            current["end_idx"] = idx

    if current:
        timeline.append(current)

    return timeline


def resolve_containing_section_for_chunk(
    chunk: dict[str, Any],
    page_chunks: list[dict[str, Any]],
) -> tuple[str | None, str | None, str | None]:
    """Resolve containing and next headings for a chunk using section timeline.

    Returns (containing_heading, next_heading, containing_section_path).
    """
    timeline = build_section_timeline(page_chunks)
    chunk_idx = chunk.get("chunk_index", 0) or 0

    containing: str | None = None
    next_h: str | None = None

    for i, entry in enumerate(timeline):
        if entry["start_idx"] <= chunk_idx <= entry["end_idx"]:
            containing = entry["heading"]
            if i + 1 < len(timeline):
                next_h = timeline[i + 1]["heading"]
            break
        elif entry["start_idx"] > chunk_idx:
            next_h = entry["heading"]
            break

    # If chunk is before first heading, no containing section
    if containing is None and timeline:
        next_h = timeline[0]["heading"]

    return (containing, next_h, [containing] if containing else [])


# -- Footnote resolver -----------------------------------------------------


def resolve_footnote_body(
    footnote_chunks: list[dict[str, Any]],
) -> FootnoteInfo:
    """Resolve footnote body from footnote chunks."""
    if not footnote_chunks:
        return FootnoteInfo()

    first = footnote_chunks[0]
    content = str(first.get("markdown") or first.get("content") or "").strip()

    number = detect_footnote_number(content)

    # Clean the footnote content (remove the number prefix)
    body_text = content
    if number is not None:
        body_text = re.sub(rf"^{number}\s*", "", content, count=1).strip()

    # Combine with continuation chunks
    for c in footnote_chunks[1:]:
        extra = str(c.get("markdown") or c.get("content") or "").strip()
        if extra:
            # Check if it's a new footnote (different number)
            next_num = detect_footnote_number(extra)
            if next_num is not None and next_num != number:
                break
            # Remove number prefix if it has one
            extra_clean = re.sub(rf"^{next_num}\s*" if next_num else r"^\d+\s*", "", extra, count=1).strip()
            body_text += " " + extra_clean

    return FootnoteInfo(
        number=number,
        body_text=body_text,
        body_block_id=str(first.get("chunk_id") or first.get("id") or ""),
        page=first.get("pdf_page") or first.get("page_start"),
    )


def find_footnote_marker(
    footnote_number: int,
    page_chunks: list[dict[str, Any]],
    timeline: list[dict[str, Any]] | None = None,
) -> FootnoteMarker:
    """Find the marker for a footnote number in page chunks.

    Resolution order:
    1. Explicit marker text in chunk metadata
    2. Footnote number at end of paragraph (e.g. '.35')
    3. Matching control
    """
    sorted_chunks = sorted(page_chunks, key=lambda c: c.get("chunk_index", 0) or 0)
    marker_str = str(footnote_number)

    for chunk in reversed(sorted_chunks):
        block_type = str(chunk.get("block_type") or "")
        if block_type == "footnote":
            continue  # skip footnote blocks, look in body text
        content = str(chunk.get("markdown") or chunk.get("content") or "").strip()
        markers = detect_footnote_marker(content)

        for num, end_pos in markers:
            if num == footnote_number:
                # Extract anchor text (the text before the marker)
                before = content[:end_pos - len(marker_str) - 1]
                sentences = re.split(r'[.?!]\s+', before)
                anchor = sentences[-1] if sentences else before

                # Resolve section
                if timeline is None:
                    timeline = build_section_timeline(page_chunks)
                containing, next_h, section_path = resolve_containing_section_for_chunk(chunk, page_chunks)

                return FootnoteMarker(
                    marker_text=marker_str,
                    marker_block_id=str(chunk.get("chunk_id") or chunk.get("id") or ""),
                    marker_offset=end_pos,
                    anchor_text=anchor.strip(),
                    anchor_block_id=str(chunk.get("chunk_id") or chunk.get("id") or ""),
                    anchor_section=containing,
                    anchor_section_path=section_path,
                    next_heading=next_h,
                    next_heading_block_id=None,
                    resolution_method="textual_marker",
                    confidence=0.9,
                )

    return FootnoteMarker(
        resolution_method="unresolved",
        confidence=0.0,
        warnings=["footnote_marker_not_found"],
    )


# -- Heading-body association ----------------------------------------------


def associate_heading_with_body(
    heading_chunk: dict[str, Any],
    all_chunks: list[dict[str, Any]],
    max_lookahead: int = 5,
) -> HeadingBodyAssociation:
    """Associate a heading chunk with its body chunk."""
    heading_idx = heading_chunk.get("chunk_index", 0) or 0
    heading_text = str(heading_chunk.get("markdown") or heading_chunk.get("content") or "").strip()

    sorted_chunks = sorted(all_chunks, key=lambda c: c.get("chunk_index", 0) or 0)

    found = False
    body_chunk = None
    body_text = None

    for chunk in sorted_chunks:
        idx = chunk.get("chunk_index", 0) or 0
        if idx <= heading_idx:
            continue
        content = str(chunk.get("markdown") or chunk.get("content") or "").strip()
        if not content:
            continue
        # Skip if it's another heading
        if _HEADING_PATTERN.match(content):
            break
        # Skip footnotes
        if str(chunk.get("block_type") or "") == "footnote":
            continue
        body_chunk = chunk
        body_text = content[:300]
        found = True
        break

    return HeadingBodyAssociation(
        heading_text=heading_text,
        heading_block_id=str(heading_chunk.get("chunk_id") or heading_chunk.get("id") or ""),
        body_text=body_text,
        body_block_id=str(body_chunk.get("chunk_id") or body_chunk.get("id") or "") if body_chunk else None,
        association_method="adjacent_chunk" if found else "not_found",
        confidence=0.9 if found else 0.0,
    )


# -- Stable evidence ID V2 -------------------------------------------------


def make_editorial_evidence_id(
    document_id: str,
    page: int | None,
    source_layer: str,
    block_id: str,
    extra: str = "",
) -> str:
    """Generate a stable V2 evidence ID including editorial context."""
    raw = f"edv2|{document_id}|{page}|{source_layer}|{block_id}|{extra}"
    return f"ev-{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


# -- Build V2 editorial dict ----------------------------------------------


def build_editorial_v2(
    chunk: dict[str, Any],
    page: dict[str, Any],
    page_chunks: list[dict[str, Any]],
    existing_v1: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the editorial V2 extension dict for a chunk.

    Returns only V2-specific fields (all optional, backward-compatible).
    """
    chunk_id = str(chunk.get("chunk_id") or chunk.get("id") or "")
    content = str(chunk.get("markdown") or chunk.get("content") or "")
    doc_id = str(chunk.get("document_id") or "")

    # 1. Classify editorial block
    ctx = classify_editorial_block(chunk, page_chunks)

    # 2. Detect printed references
    refs = detect_printed_references(content)

    # 3. Detect footnote number
    fn_num = detect_footnote_number(content)
    fn_body_text = None
    if fn_num is not None:
        fn_body_text = re.sub(rf"^{fn_num}\s*", "", content, count=1).strip()
        # Combine with continuation
        for other in page_chunks:
            if str(other.get("id") or other.get("chunk_id") or "") == chunk_id:
                continue
            if str(other.get("block_type") or "") == "footnote":
                if str(other.get("chunk_index", 0)) == str(chunk.get("chunk_index", 0)):
                    continue
                extra_content = str(other.get("markdown") or other.get("content") or "").strip()
                other_num = detect_footnote_number(extra_content)
                if other_num is None:
                    fn_body_text += " " + extra_content

    # 4. Build section timeline
    timeline = build_section_timeline(page_chunks)
    containing, next_h, section_path = resolve_containing_section_for_chunk(chunk, page_chunks)

    # 5. Find footnote marker if applicable
    marker: FootnoteMarker | None = None
    if ctx.block_role == EditorialBlockRole.FOOTNOTE_BODY and fn_num is not None:
        marker = find_footnote_marker(fn_num, page_chunks, timeline)
    elif ctx.block_role == EditorialBlockRole.MAIN_BODY:
        # Check for footnote markers in main body
        markers_found = detect_footnote_marker(content)
        if markers_found:
            for num, _ in markers_found:
                marker = find_footnote_marker(num, page_chunks, timeline)
                if marker.confidence > 0 and marker.resolution_method != "unresolved":
                    break

    # 6. Heading-body association if this is a heading
    heading_body: HeadingBodyAssociation | None = None
    if ctx.block_role == EditorialBlockRole.SECTION_HEADING:
        heading_body = associate_heading_with_body(chunk, page_chunks)

    # 7. Build reference info
    printed_ref = refs[0] if refs else None
    canonical_ref = None

    # Build V2 dict
    v2: dict[str, Any] = {
        "editorial": {
            "block_role": ctx.block_role.value,
            "block_role_confidence": ctx.block_role_confidence,
            "block_role_method": ctx.block_role_method,
        }
    }

    # Add reference fields
    if printed_ref:
        v2["editorial"]["printed_reference"] = printed_ref.surface
        v2["editorial"]["reference_normalized"] = printed_ref.normalized
        v2["editorial"]["canonical_reference_candidate"] = None
        v2["editorial"]["reference_status"] = ReferenceStatus.PRINTED_ONLY.value

    # Add footnote fields
    if ctx.block_role == EditorialBlockRole.FOOTNOTE_BODY and fn_num is not None:
        v2["editorial"]["block_role"] = "footnote"
        v2["editorial"]["footnote_number"] = str(fn_num)
        v2["editorial"]["footnote_marker"] = str(fn_num)
        if marker:
            v2["editorial"]["footnote_anchor_text"] = marker.anchor_text
            v2["editorial"]["anchor_block_id"] = marker.anchor_block_id
            v2["editorial"]["anchor_section_path"] = marker.anchor_section_path
            v2["editorial"]["next_heading"] = next_h
            v2["editorial"]["marker_resolution"] = marker.resolution_method
        if next_h and not marker:
            v2["editorial"]["next_heading"] = next_h

    # Add section info
    if containing:
        v2["editorial"]["containing_heading"] = containing
    if next_h and ctx.block_role != EditorialBlockRole.FOOTNOTE_BODY:
        v2["editorial"]["next_heading"] = next_h

    # Add heading-body association
    if heading_body and heading_body.body_text:
        v2["editorial"]["associated_body_text"] = heading_body.body_text
        v2["editorial"]["associated_body_block_id"] = heading_body.body_block_id

    # Add warnings
    if ctx.warnings:
        v2["editorial"]["warnings"] = ctx.warnings

    return v2


# -- Integration helper ----------------------------------------------------


def enrich_evidence_with_v2(
    evidence: dict[str, Any],
    chunk: dict[str, Any],
    page_chunks: list[dict[str, Any]],
    existing_v1: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Enrich an existing V1 evidence dict with V2 editorial fields."""
    v2 = build_editorial_v2(chunk, {}, page_chunks, existing_v1)
    evidence["editorial"] = v2.get("editorial")
    return evidence


def build_full_evidence_v2(
    chunk: dict[str, Any],
    page_chunks: list[dict[str, Any]],
    query: str = "",
) -> dict[str, Any] | None:
    """Build a complete evidence entry with V1 + V2 editorial fields."""
    from modules.library.page_first_evidence import build_evidence_v1

    # First build V1 evidence
    v1 = build_evidence_v1(query=query, chunk=chunk, same_page_chunks=page_chunks)
    if v1 is None:
        return None

    # Add V2 editorial fields
    v2 = build_editorial_v2(chunk, {}, page_chunks)
    v1["editorial"] = v2.get("editorial")

    return v1
