"""Page-first evidence contract V1.

Resolves retrieval hits to canonical pages, locates evidence within pages,
identifies containing sections/headings, and produces structured evidence
locations with exact quotes, offsets, and context.

Architecture:
    Document
    └── CanonicalPage  (assembled from chunks sharing page_start)
        ├── StructuralHeading  (section_title or content-derived)
        ├── StructuralBlock
        ├── Paragraph
        ├── SemanticChunk
        └── EvidenceLocation  (exact quote + offsets + page refs)
"""

from __future__ import annotations

import hashlib
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# -- Precompile patterns -------------------------------------------------

_PAGE_MARKER = re.compile(r"(?:##\s*)?[Pp]ágina\s*(\d+)", re.UNICODE)
_PAGE_MARKER_EN = re.compile(r"(?:##\s*)?[Pp]age\s*(\d+)", re.UNICODE)
_PAGE_MARKERS = re.compile(
    r"(?:##\s*)?(?:[Pp]ágina|[Pp]age|PDF\s*p\.)\s*(\d+)", re.UNICODE
)
_HEADING_MARKER = re.compile(
    r"^#{1,6}\s+.*$|^\d+\s*[.■]\s+.*$|^[A-ZÁÉÍÓÚÜÑ][A-ZÁÉÍÓÚÜÑ\s]+\S*$",
    re.MULTILINE | re.UNICODE,
)
_RUNNING_HEADER = re.compile(
    r"^\d+\s*$"  # standalone page number
    r"|^\d+\s+[A-ZÁÉÍÓÚÜÑ]"  # page number + uppercase text (folio)
    r"|[A-ZÁÉÍÓÚÜÑ\s]+\s+\d+$"  # uppercase text + page number
    r"|^(?:BRESLOV RESEARCH|LIKUTEY|EL ALMA|TZADIK|SIJOT|KOKHAVEY)",  # book titles as headers
    re.UNICODE,
)


# -- Domain types --------------------------------------------------------


@dataclass(frozen=True)
class PageReference:
    """Reference to a canonical page."""
    page_id: str | None
    pdf_page: int | None
    printed_page: int | None
    document_id: str
    document_title: str
    source_layer: str = "canonical_page"
    resolution_method: str = "chunk_page_start"
    confidence: float = 1.0
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CanonicalPage:
    """Full canonical text for a page."""
    page_id: str | None
    document_id: str
    pdf_page: int | None
    printed_page: int | None
    text: str
    chunks_used: list[str] = field(default_factory=list)
    source: str = "assembled_from_chunks"


@dataclass(frozen=True)
class EvidenceLocation:
    """Precise location of evidence within a canonical page."""
    exact_quote: str | None
    start_offset: int | None
    end_offset: int | None
    location_precision: str  # "exact" | "normalized_exact" | "token_span" | "block_level" | "approximate" | "unresolved"
    block_id: str | None = None
    paragraph_index: int | None = None
    matched_variant: str | None = None


@dataclass(frozen=True)
class SectionReference:
    """Containing editorial section or heading."""
    section_path: list[str] = field(default_factory=list)
    heading_text: str | None = None
    heading_level: int | None = None
    heading_original: str | None = None
    heading_source: str = "section_title"
    heading_confidence: float = 1.0
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EvidenceCandidate:
    """Combined evidence location with page, section, and quote."""
    evidence_id: str
    document_id: str
    document_title: str
    page: PageReference
    section: SectionReference
    location: EvidenceLocation
    context_before: str | None = None
    context_after: str | None = None
    chunk_id: str | None = None
    heading_chunk_id: str | None = None
    body_chunk_id: str | None = None


# -- Page resolution ----------------------------------------------------


def resolve_page_for_retrieval_hit(
    chunk: dict[str, Any],
) -> PageReference:
    """Resolve a canonical page reference from any retrieval hit.

    Order of preference:
    1. Explicit page_id foreign key
    2. page_anchor reference
    3. Chunk page_start as pdf_page
    4. printed_page_label
    5. Infer from page markers in markdown content
    """
    document_id = str(chunk.get("document_id", ""))
    document_title = str(chunk.get("work") or chunk.get("title") or "")

    # Direct page_id from chunk metadata
    page_id = chunk.get("page_id") or chunk.get("canonical_page_id")
    if not page_id and chunk.get("content_node_id"):
        # Content nodes have page_anchor_id -> pages_v2
        page_id = chunk.get("page_id")

    # Page numbers
    pdf_page = _resolve_pdf_page(chunk)
    printed_page = _resolve_printed_page(chunk)

    # Determine resolution method
    if page_id:
        method = "explicit_page_id"
    elif chunk.get("page_anchor_id"):
        method = "page_anchor"
    elif chunk.get("pdf_page") is not None:
        method = "chunk_page_start"
    else:
        method = "page_marker_inference"

    warnings_list: list[str] = []
    if method == "page_marker_inference" and pdf_page is None:
        warnings_list.append("could not resolve page number")

    return PageReference(
        page_id=str(page_id) if page_id else None,
        pdf_page=pdf_page,
        printed_page=printed_page,
        document_id=document_id,
        document_title=document_title,
        resolution_method=method,
        confidence=0.7 if method == "page_marker_inference" else 1.0,
        warnings=warnings_list,
    )


def _resolve_pdf_page(chunk: dict[str, Any]) -> int | None:
    """Extract PDF page number from chunk data.

    Priority: pdf_page (post-local-resolution) > canonical_pdf_page_start
    > page_start > page_marker_inference.
    """
    for key in ("pdf_page", "canonical_pdf_page_start", "page_start"):
        val = chunk.get(key)
        if val is not None:
            try:
                return int(val)
            except (ValueError, TypeError):
                pass
    return None


def _resolve_printed_page(chunk: dict[str, Any]) -> int | None:
    """Extract printed page number."""
    label = chunk.get("printed_page") or chunk.get("printed_page_label")
    if label is not None:
        try:
            return int(label)
        except (ValueError, TypeError):
            pass
    return None


def page_key(chunk: dict[str, Any]) -> tuple[str, int | None]:
    """Return a stable page key (document_id, pdf_page) for grouping chunks."""
    doc = str(chunk.get("document_id", ""))
    page = _resolve_pdf_page(chunk)
    return (doc, page)


# -- Canonical page assembly --------------------------------------------


def assemble_page_text(
    page_ref: PageReference,
    chunks: list[dict[str, Any]],
) -> CanonicalPage:
    """Assemble canonical page text from all chunks on the same page.

    Combines chunk content ordered by chunk_index, deduplicating
    structural headings that appear in both section_title and content.
    """
    if not chunks:
        return CanonicalPage(
            page_id=page_ref.page_id,
            document_id=page_ref.document_id,
            pdf_page=page_ref.pdf_page,
            printed_page=page_ref.printed_page,
            text="",
            source="empty",
        )

    # Sort by chunk_index
    sorted_chunks = sorted(chunks, key=lambda c: c.get("chunk_index", 0) or 0)

    parts: list[str] = []
    seen_texts: set[str] = set()
    chunk_ids: list[str] = []

    for c in sorted_chunks:
        content = str(c.get("markdown") or c.get("content") or "").strip()
        if not content:
            continue

        # Deduplicate: skip if content is identical to last
        if content in seen_texts:
            continue
        seen_texts.add(content)

        parts.append(content)
        cid = str(c.get("chunk_id") or c.get("id") or "")
        if cid:
            chunk_ids.append(cid)

    text = "\n\n".join(parts)

    return CanonicalPage(
        page_id=page_ref.page_id,
        document_id=page_ref.document_id,
        pdf_page=page_ref.pdf_page,
        printed_page=page_ref.printed_page,
        text=text,
        chunks_used=chunk_ids,
        source="assembled_from_chunks",
    )


# -- Evidence localization ----------------------------------------------


def locate_evidence_within_page(
    query: str,
    canonical_page: CanonicalPage,
    candidate_chunk: dict[str, Any],
    heading_candidates: list[dict[str, Any]] | None = None,
    language: str = "es",
) -> EvidenceLocation:
    """Locate evidence within canonical page text.

    Precision order:
    1. exact match
    2. normalized match (NFKC, casefold)
    3. token_span (ordered tokens)
    4. block_level (whole chunk content within page)
    5. approximate (page-level)
    """
    page_text = canonical_page.text
    if not page_text:
        return EvidenceLocation(
            exact_quote=None,
            start_offset=None,
            end_offset=None,
            location_precision="unresolved",
        )

    # Primary search text: from chunk content
    chunk_text = str(
        candidate_chunk.get("markdown")
        or candidate_chunk.get("content")
        or ""
    ).strip()

    # Also use the matched_variant if available
    matched_variant = str(candidate_chunk.get("matched_variant") or "").strip()

    # Try exact match first
    for search_text in [matched_variant, chunk_text, query]:
        if not search_text:
            continue
        result = _find_in_text(search_text, page_text, exact=True)
        if result:
            return EvidenceLocation(
                exact_quote=result["quote"],
                start_offset=result["start"],
                end_offset=result["end"],
                location_precision="exact",
                matched_variant=search_text,
            )

    # Try normalized match
    for search_text in [matched_variant, chunk_text, query]:
        if not search_text:
            continue
        result = _find_in_text(search_text, page_text, exact=False)
        if result:
            return EvidenceLocation(
                exact_quote=result["quote"],
                start_offset=result["start"],
                end_offset=result["end"],
                location_precision="normalized_exact",
                matched_variant=search_text,
            )

    # Token span: match ordered tokens within a sliding window
    for search_text in [chunk_text, query]:
        if not search_text:
            continue
        result = _find_token_span(search_text, page_text)
        if result:
            return EvidenceLocation(
                exact_quote=result["quote"],
                start_offset=result["start"],
                end_offset=result["end"],
                location_precision="token_span",
                matched_variant=search_text,
            )

    # Block level: use the chunk text itself (it's already within the page)
    if chunk_text:
        return EvidenceLocation(
            exact_quote=chunk_text[:500],
            start_offset=None,
            end_offset=None,
            location_precision="block_level",
            block_id=str(candidate_chunk.get("chunk_id") or candidate_chunk.get("id") or ""),
        )

    return EvidenceLocation(
        exact_quote=None,
        start_offset=None,
        end_offset=None,
        location_precision="unresolved",
    )


def _find_in_text(
    needle: str, haystack: str, exact: bool = True
) -> dict[str, Any] | None:
    """Find a string within text, returning quote and offsets."""
    if not needle or not haystack:
        return None

    if exact:
        idx = haystack.find(needle)
        if idx >= 0:
            return {
                "quote": needle,
                "start": idx,
                "end": idx + len(needle),
            }
    else:
        # Normalized: NFKC + casefold
        norm_needle = unicodedata.normalize("NFKC", needle).casefold()
        norm_haystack = unicodedata.normalize("NFKC", haystack).casefold()
        idx = norm_haystack.find(norm_needle)
        if idx >= 0:
            # Return original text (from haystack) for the quote
            original_quote = haystack[idx : idx + len(needle)]
            return {
                "quote": original_quote,
                "start": idx,
                "end": idx + len(needle),
            }

        # Try without accents
        unaccented_needle = _unaccent(norm_needle)
        unaccented_haystack = _unaccent(norm_haystack)
        idx = unaccented_haystack.find(unaccented_needle)
        if idx >= 0:
            original_quote = haystack[idx : idx + len(needle)]
            return {
                "quote": original_quote,
                "start": idx,
                "end": idx + len(needle),
            }

    return None


def _unaccent(text: str) -> str:
    """Remove common diacritics/accents."""
    return (
        unicodedata.normalize("NFKD", text)
        .encode("ascii", "ignore")
        .decode("ascii")
    )


def _find_token_span(needle: str, haystack: str) -> dict[str, Any] | None:
    """Match ordered tokens within a sliding window."""
    tokens = re.findall(r"\S+", needle.casefold())
    if len(tokens) < 2:
        return None

    haystack_lower = haystack.casefold()
    haystack_tokens = re.findall(r"\S+", haystack_lower)

    # Sliding window
    window_size = len(tokens) + 2  # allow 2 extra tokens
    for i in range(len(haystack_tokens) - len(tokens) + 1):
        window = haystack_tokens[i : i + len(tokens)]
        if window == tokens:
            # Found ordered match - calculate offsets
            start = haystack_lower.find(haystack_tokens[i])
            end = haystack_lower.find(haystack_tokens[i + len(tokens) - 1])
            if end >= 0:
                end += len(haystack_tokens[i + len(tokens) - 1])
                quote = haystack[start:end]
                return {"quote": quote, "start": start, "end": end}

    return None


# -- Context extraction -------------------------------------------------


def extract_context(
    canonical_page: CanonicalPage,
    location: EvidenceLocation,
    context_chars: int = 200,
) -> tuple[str | None, str | None]:
    """Extract context_before and context_after for a location."""
    if location.start_offset is None or location.end_offset is None:
        return (None, None)

    text = canonical_page.text
    before_start = max(0, location.start_offset - context_chars)
    after_end = min(len(text), location.end_offset + context_chars)

    context_before = text[before_start : location.start_offset].strip() or None
    context_after = text[location.end_offset : after_end].strip() or None

    return (context_before, context_after)


# -- Heading / section resolution ---------------------------------------


def resolve_containing_section(
    page: PageReference,
    canonical_page: CanonicalPage,
    candidate_chunk: dict[str, Any],
    heading_candidates: list[dict[str, Any]] | None = None,
) -> SectionReference:
    """Identify the editorial heading/section containing the evidence.

    Sources (in priority order):
    1. section_title from the chunk
    2. structural heading candidate from heading search
    3. Markdown heading parser within the page text
    4. Previous chunk's heading
    5. Page-level classification
    """
    warnings_list: list[str] = []

    # 1. section_title
    section_title = str(candidate_chunk.get("section_title") or "").strip()
    if section_title:
        heading = section_title
        heading_original = candidate_chunk.get("heading_original") or heading
        return SectionReference(
            section_path=[heading],
            heading_text=heading,
            heading_original=heading_original,
            heading_source="section_title",
        )

    # 2. structural heading candidate
    heading_original = candidate_chunk.get("heading_original") or ""
    heading_normalized = candidate_chunk.get("heading_normalized") or ""
    if heading_original:
        return SectionReference(
            section_path=[heading_original],
            heading_text=heading_original,
            heading_original=heading_original,
            heading_source="structural_heading_candidate",
        )

    # 3. Parse page text for markdown headings before the chunk position
    if canonical_page.text and candidate_chunk.get("chunk_index") is not None:
        heading = _find_preceding_heading(
            canonical_page.text, candidate_chunk
        )
        if heading:
            return SectionReference(
                section_path=[heading],
                heading_text=heading,
                heading_original=heading,
                heading_source="markdown_heading_before",
                heading_confidence=0.6,
            )

    # 4. Check if heading_candidates were provided
    if heading_candidates:
        for hc in heading_candidates:
            h_text = str(hc.get("heading_original") or hc.get("section_title") or "")
            if h_text:
                return SectionReference(
                    section_path=[h_text],
                    heading_text=h_text,
                    heading_original=hc.get("heading_original"),
                    heading_source="heading_candidates_list",
                    heading_confidence=0.5,
                )

    # No heading found
    warnings_list.append("no_heading_found")
    return SectionReference(
        section_path=[],
        heading_text=None,
        heading_level=None,
        heading_original=None,
        heading_source="none",
        heading_confidence=0.0,
        warnings=warnings_list,
    )


def _find_preceding_heading(
    page_text: str, chunk: dict[str, Any]
) -> str | None:
    """Find the nearest editorial heading before the chunk position."""
    lines = page_text.split("\n")
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        # Skip running headers and page numbers
        if _RUNNING_HEADER.match(line):
            continue
        # Check if it's a heading
        if _HEADING_MARKER.match(line):
            return line
    return None


# -- Stable evidence ID -------------------------------------------------


def make_evidence_id(
    document_id: str,
    page_ref: PageReference,
    location: EvidenceLocation,
    chunk_id: str = "",
) -> str:
    """Generate a stable evidence ID from canonical elements.

    Does NOT depend on rank, timestamp, or AI output.
    """
    parts = [
        document_id,
        str(page_ref.pdf_page or ""),
        str(page_ref.printed_page or ""),
        chunk_id,
    ]
    raw = "|".join(parts)
    return f"ev-{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


def make_claim_id(evidence_id: str, claim_index: int = 0) -> str:
    """Generate a stable claim ID from an evidence ID."""
    raw = f"{evidence_id}|claim|{claim_index}"
    return f"claim-{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


# -- Evidence V1 builder ------------------------------------------------


def build_evidence_v1(
    query: str,
    chunk: dict[str, Any],
    heading_candidates: list[dict[str, Any]] | None = None,
    same_page_chunks: list[dict[str, Any]] | None = None,
    language: str = "es",
) -> dict[str, Any] | None:
    """Build a page-first evidence V1 entry from a retrieval hit.

    Returns enriched evidence dict with page-first fields, or None
    if the hit cannot be resolved.

    This function is designed to be called from the simple_rag pipeline
    AFTER chunk selection, enriching each selected chunk with
    page-first evidence location data.
    """
    # 1. Resolve page
    page_ref = resolve_page_for_retrieval_hit(chunk)
    if page_ref.pdf_page is None and not page_ref.page_id:
        return None  # Cannot resolve page

    # 2. Assemble canonical page
    if same_page_chunks:
        canonical = assemble_page_text(page_ref, same_page_chunks)
    else:
        canonical = assemble_page_text(page_ref, [chunk])

    # 3. Locate evidence
    location = locate_evidence_within_page(
        query=query,
        canonical_page=canonical,
        candidate_chunk=chunk,
        heading_candidates=heading_candidates,
        language=language,
    )

    # 4. Resolve heading
    section = resolve_containing_section(
        page=page_ref,
        canonical_page=canonical,
        candidate_chunk=chunk,
        heading_candidates=heading_candidates,
    )

    # 5. Extract context
    context_before, context_after = extract_context(canonical, location)

    # 6. Generate stable evidence ID
    chunk_id = str(chunk.get("chunk_id") or chunk.get("id") or "")
    evidence_id = chunk.get("evidence_id") or make_evidence_id(
        document_id=page_ref.document_id,
        page_ref=page_ref,
        location=location,
        chunk_id=chunk_id,
    )

    # 7. Build enriched evidence dict
    v1_evidence = {
        # Page-first fields (new)
        "page_id": page_ref.page_id,
        "pdf_page": page_ref.pdf_page,
        "printed_page": page_ref.printed_page,
        "heading_text": section.heading_text,
        "heading_level": section.heading_level,
        "heading_source": section.heading_source,
        "section_path": section.section_path,
        "exact_quote": location.exact_quote,
        "context_before": context_before,
        "context_after": context_after,
        "start_offset": location.start_offset,
        "end_offset": location.end_offset,
        "location_precision": location.location_precision,
        "block_id": location.block_id,
        "paragraph_index": location.paragraph_index,
        "matched_variant": location.matched_variant,
        "canonical_page_source": canonical.source,
        "page_resolution_method": page_ref.resolution_method,
        "page_resolution_confidence": page_ref.confidence,
    }

    # Merge with existing evidence fields (backward compatible)
    existing = {
        "evidence_id": evidence_id,
        "chunk_id": chunk_id,
        "document_id": page_ref.document_id,
        "work": chunk.get("work"),
        "title": chunk.get("title") or chunk.get("work"),
        "pdf_page": page_ref.pdf_page,
        "printed_page": page_ref.printed_page,
        "section": section.heading_text or chunk.get("section"),
        "language": chunk.get("language", language),
        "markdown": chunk.get("markdown"),
        "source_layer": chunk.get("source_layer", "canonical_page"),
        "attribution_status": chunk.get("attribution_status", "not_confirmed"),
        "semantic_score": chunk.get("semantic_score"),
        "literal_score": chunk.get("literal_score"),
        "combined_score": chunk.get("combined_score"),
        "retrieval_sources": chunk.get("retrieval_sources"),
        "literal_match_type": chunk.get("literal_match_type", "semantic_only"),
        "associated_chunk_id": chunk.get("associated_chunk_id"),
        "heading_original": section.heading_original or chunk.get("heading_original"),
        "heading_normalized": chunk.get("heading_normalized"),
        "content_node_id": chunk.get("content_node_id"),
        # Page-first V1 fields
        **v1_evidence,
    }

    return existing


# -- Forward-compatible hint for frontend -------------------------------


def frontend_hint_v1() -> dict[str, Any]:
    """Return fields the frontend can expect in page-first V1."""
    return {
        "page_id": None,
        "pdf_page": None,
        "printed_page": None,
        "heading_text": None,
        "heading_level": None,
        "section_path": [],
        "exact_quote": None,
        "context_before": None,
        "context_after": None,
        "start_offset": None,
        "end_offset": None,
        "location_precision": None,
        "source_layer": "canonical_page",
    }
