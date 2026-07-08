#!/usr/bin/env python3
"""
Likutey Halajot layout-aware parser.

Reads the PDF with PyMuPDF get_text('dict') and classifies each text
block into layout-aware types (page_header, source_hebrew, section_marker,
main_explanation_es, marginal_source, footnote, composite_page_context, unknown).

Usage (standalone, no PG/Milvus):
    uv run python -m scripts.likutey_layout_parser \\
        --pdf-path /path/to/pdf \\
        --pages 23,32,37 \\
        --output-dir /tmp/layout_blocks

    uv run python -m scripts.likutey_layout_parser \\
        --pdf-path /path/to/pdf \\
        --pages 1-284 \\
        --output-dir /tmp/layout_blocks \\
        --json

The parser can also be imported and used programmatically.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PAGE_W = 496.0
PAGE_H = 694.0

VALID_BLOCK_TYPES = frozenset({
    "page_header",
    "source_hebrew",
    "section_marker",
    "main_explanation_es",
    "marginal_source",
    "footnote",
    "internal_cross_reference",
    "composite_page_context",
    "unknown",
})

VALID_BLOCK_SUBTYPES = frozenset({
    "biblical_citation",
    "rabbinic_reference",
    "halachic_reference",
    "breslov_teaching",
    "theological_explanation",
    "bibliographic_note",
    "translator_editor_note",
    "cross_page_note",
    "halachic_derash",
})

VALID_EVIDENCE_ROLES = frozenset({
    "source_text",
    "commentary",
    "direct_quote",
    "marginal_citation",
    "bibliographic_note",
    "halachic_derash",
    "thematic_context",
    "composite_for_retrieval",
})

# ── Regex patterns ──────────────────────────────────────────────────────

SECTION_MARKER_RE = re.compile(r"Likutey[\s]*Halajot[\s]*Explicado|/LNXWH|LNXWH")
NOTES_MARKER_RE = re.compile(r"Notas[\s]*y[\s]*Fuentes|1RWHV")
HEADER_HE_RE = re.compile(
    b"\\x98\\x83\\x89\\x8a\\x82 \\x87\\x86\\x83\\x95\\x87\\x8a".decode("latin-1")
)
HEADER_ES_RE = re.compile(r"DISCURSO SOBRE|HALAJA|HALAJÁ")
HALACHA_RE = re.compile(r"HALAJ[ÁA]\s+(\d+)[:.](\d+)")

# Source reference patterns
SOURCE_PATTERNS: dict[str, re.Pattern] = {
    "Salmos": re.compile(r"Salmos?\s+\d+:\d+", re.IGNORECASE),
    "Tehilim": re.compile(r"Tehilim\s+\d+:\d+", re.IGNORECASE),
    "Avot": re.compile(r"Avot\s+\d+:\d+", re.IGNORECASE),
    "Rosh HaShaná": re.compile(r"Rosh\s+HaShan[áa]\s+\d+[ab]", re.IGNORECASE),
    "Likutei Moharán": re.compile(r"Likutei?\s*Mohar[áa]n", re.IGNORECASE),
    "Likutey Halajot": re.compile(r"Likutey\s+Halajot", re.IGNORECASE),
    "Shuljan Aruj": re.compile(r"Shuljan\s+Aruj", re.IGNORECASE),
    "Remá": re.compile(r"Rem[áa]", re.IGNORECASE),
    "Zohar": re.compile(r"Zohar", re.IGNORECASE),
    "Saba diMishpatim": re.compile(r"Saba\s+diMishpatim", re.IGNORECASE),
    "Beit Hilel": re.compile(r"Beit\s+Hilel", re.IGNORECASE),
    "Mija": re.compile(r"Mija\s+\d+:\d+", re.IGNORECASE),
    "Proverbios": re.compile(r"Proverbios\s+\d+:\d+", re.IGNORECASE),
}

CROSSREF_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"ver\s+nota\s+\d+", re.IGNORECASE), "note_ref"),
    (re.compile(r"nota\s+\d+", re.IGNORECASE), "note_ref"),
    (re.compile(r"más\s+adelante", re.IGNORECASE), "forward_ref"),
    (re.compile(r"como\s+se\s+explic[óo]\s+anteriormente", re.IGNORECASE), "backward_ref"),
    (re.compile(r"ver\s+m[áa]s\s+arriba", re.IGNORECASE), "backward_ref"),
    (re.compile(r"ib[ií]d\.", re.IGNORECASE), "ibid"),
    (re.compile(r"secci[óo]n\s+siguiente", re.IGNORECASE), "forward_ref"),
    (re.compile(r"§\s*\d+", re.IGNORECASE), "section_ref"),
    (re.compile(r"ver\s+tambi[ée]n", re.IGNORECASE), "see_also"),
]

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class LayoutBlock:
    block_index: int
    block_type: str
    block_subtype: str | None = None
    evidence_role: str | None = None
    language: str = "unknown"
    content: str = ""
    content_sha256: str = ""
    content_length: int = 0
    page_number: int = 0  # 1-indexed PDF page number → stored as page_start in PG
    physical_page: int = 0
    printed_page_label: str | None = None
    bbox: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    node_path: str | None = None
    section_title_he: str | None = None
    section_title_es: str | None = None
    halacha_ref: str | None = None
    source_refs: list[dict] = field(default_factory=list)
    source_ref_as_printed: list[str] = field(default_factory=list)
    needs_reference_review: bool = False
    review_note: str | None = None
    internal_cross_refs: list[dict] = field(default_factory=list)
    citable: bool = True
    layout_confidence: float = 1.0
    hebrew_decoder: str = ""
    hebrew_decoder_applied: bool = False
    needs_hebrew_review: bool = False
    topics: list[str] = field(default_factory=list)
    extraction_method: str = "pymupdf_dict_layout_aware"
    ingestion_profile: str = "layout_aware_likutey_halajot"
    spans: list[dict] = field(default_factory=list)

    @property
    def metadata(self) -> dict[str, Any]:
        d = {
            "block_type": self.block_type,
            "block_subtype": self.block_subtype,
            "evidence_role": self.evidence_role,
            "language": self.language,
            "page_number": self.page_number,
            "physical_page": self.physical_page,
            "printed_page_label": self.printed_page_label,
            "node_path": self.node_path,
            "citable": self.citable,
            "layout_confidence": self.layout_confidence,
            "ingestion_profile": self.ingestion_profile,
            "extraction_method": self.extraction_method,
            "source_refs": self.source_refs,
            "source_ref_as_printed": self.source_ref_as_printed,
            "needs_reference_review": self.needs_reference_review,
            "review_note": self.review_note,
            "internal_cross_refs": self.internal_cross_refs,
            "hebrew_decoder": self.hebrew_decoder,
            "hebrew_decoder_applied": self.hebrew_decoder_applied,
            "needs_hebrew_review": self.needs_hebrew_review,
        }
        return {k: v for k, v in d.items() if v is not None and v != [] and v != {}}

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Hebrew decoder wrapper
# ---------------------------------------------------------------------------


def decode_hebrew_if_needed(text: str) -> tuple[str, str, float, bool]:
    """Apply hebrew_tex_decoder if SI-960 encoding is detected.

    Returns (decoded_text, decoder_used, confidence, needs_review).
    """
    # Detect SI-960 encoded Hebrew: high-byte chars that aren't Unicode Hebrew
    si960_count = sum(1 for c in text if ord(c) >= 128 and ord(c) < 256)
    he_count = sum(1 for c in text if "\u0590" <= c <= "\u05FF")
    total_alpha = sum(1 for c in text if c.isalpha())

    if he_count > 0 and he_count > total_alpha * 0.1:
        return text, "unicode_direct", 1.0, False

    if si960_count > max(len(text) * 0.02, 2):
        try:
            from modules.library.hebrew_tex_decoder import decode_hebrew_text, is_likely_si960_encoded

            if not is_likely_si960_encoded(text, min_chars=5):
                return text, "", 1.0, False
            decoded = decode_hebrew_text(text)
            decoder_used = "hebrew_tex_decoder"
            confidence = 0.9 if len(decoded) > len(text) * 0.5 else 0.5
            needs_review = confidence < 0.8
            return decoded, decoder_used, confidence, needs_review
        except Exception:
            return text, "hebrew_tex_decoder_errored", 0.0, True

    return text, "", 1.0, False


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------


def detect_language(text: str) -> str:
    if not text.strip():
        return "unknown"
    he_count = sum(1 for c in text if "\u0590" <= c <= "\u05FF")
    si960_count = sum(1 for c in text if ord(c) >= 128 and ord(c) < 256 and not (32 <= ord(c) <= 126))
    es_chars = sum(1 for c in text if c.isalpha())
    total = he_count + si960_count + es_chars
    if total == 0:
        return "unknown"
    he_ratio = (he_count + si960_count) / total
    if he_ratio > 0.3:
        return "he"
    if he_ratio > 0.05:
        return "mixed"
    return "es"


# ---------------------------------------------------------------------------
# Block classification
# ---------------------------------------------------------------------------


def classify_block(
    x0: float, y0: float, x1: float, y1: float,
    text: str, language: str,
    spans: list[dict] | None = None,
) -> str:
    """Heuristic block type based on position, content, and language."""
    rel_y0 = y0 / PAGE_H
    rel_x0 = x0 / PAGE_W
    rel_x1 = x1 / PAGE_W
    block_w = (x1 - x0) / PAGE_W

    # Priority 1: Section marker
    if SECTION_MARKER_RE.search(text):
        return "section_marker"

    # Priority 2: Notes marker → start of footnote zone
    if NOTES_MARKER_RE.search(text):
        return "footnote"

    # Priority 3: Page header (top 9%)
    if rel_y0 < 0.09:
        return "page_header"

    # Priority 4: Marginal source (right 30%, narrow)
    if rel_x0 > 0.70 and block_w < 0.25:
        return "marginal_source"

    if rel_x0 > 0.65 and rel_x1 > 0.85 and block_w < 0.20:
        return "marginal_source"

    # Priority 5: Footnote area (bottom 18%, below notes marker)
    if rel_y0 > 0.82:
        return "footnote"

    # Priority 6: Hebrew source (upper-mid area)
    if 0.09 <= rel_y0 < 0.34 and language in ("he", "mixed"):
        # Check if it's actually Spanish misclassified
        es_ratio = sum(1 for c in text if c.isascii() and c.isalpha()) / max(len(text), 1)
        if es_ratio > 0.6:
            return "main_explanation_es"
        return "source_hebrew"

    # Default: main explanation
    return "main_explanation_es"


# ---------------------------------------------------------------------------
# Source reference extraction
# ---------------------------------------------------------------------------


def find_sources(text: str) -> tuple[list[dict], list[str], bool]:
    sources: list[dict] = []
    printed_refs: list[str] = []
    needs_review = False

    for name, pattern in SOURCE_PATTERNS.items():
        for m in pattern.finditer(text):
            sources.append({
                "source_type": name,
                "matched_text": m.group(),
                "position": m.start(),
            })
            printed_refs.append(m.group())

    return sources, printed_refs, needs_review


def find_crossrefs(text: str) -> list[dict]:
    refs: list[dict] = []
    for pattern, ref_type in CROSSREF_PATTERNS:
        for m in pattern.finditer(text):
            refs.append({
                "type": ref_type,
                "label": m.group(),
                "position": m.start(),
            })
    return refs


# ---------------------------------------------------------------------------
# Node path extraction
# ---------------------------------------------------------------------------


def extract_node_path_from_header(header_text: str) -> dict[str, Any]:
    path: dict[str, Any] = {
        "work_title": "Likutey Halajot",
        "section_title_he": None,
        "section_title_es": None,
        "halacha_ref": None,
        "node_path": None,
        "printed_page": None,
        "confidence": 0.0,
    }

    if HEADER_HE_RE.search(header_text):
        path["section_title_he"] = "השכמת הבוקר"
        path["confidence"] += 0.3

    if HEADER_ES_RE.search(header_text):
        path["section_title_es"] = "Discurso sobre el levantarse"
        path["confidence"] += 0.3

    m = HALACHA_RE.search(header_text)
    if m:
        path["halacha_ref"] = f"Halajá {m.group(1)}:{m.group(2)}"
        path["confidence"] += 0.4

    # Extract printed page from header
    # Try "NN LIKUTEY HALAJOT" pattern first (Spanish even pages)
    m_num = re.search(r"(\d+)\s+LIKUTEY HALAJOT", header_text)
    if m_num:
        n = int(m_num.group(1))
        if 1 <= n <= 500:
            path["printed_page"] = n
    else:
        # Try Hebrew SI-960 header: require ≥3 consecutive high-byte chars
        m_num = re.search(r"[\x80-\xff]{3,}\s+(\d+)", header_text)
        if m_num:
            n = int(m_num.group(1))
            if 1 <= n <= 500:
                path["printed_page"] = n
        else:
            # Try number near pipe separator
            m_num = re.search(r"(\d+)\s*[|]", header_text)
            if m_num:
                n = int(m_num.group(1))
                if 1 <= n <= 500:
                    path["printed_page"] = n

    parts = [path["work_title"]]
    if path["section_title_he"] or path["section_title_es"]:
        parts.append(path["section_title_es"] or path["section_title_he"] or "")
    if path["halacha_ref"]:
        parts.append(path["halacha_ref"])
    path["node_path"] = " > ".join(p for p in parts if p)

    return path


def compute_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Page parser
# ---------------------------------------------------------------------------


def parse_page(
    doc: Any,
    pdf_page_number: int,
    printed_page_label: str | None = None,
) -> tuple[list[LayoutBlock], dict[str, Any]]:
    """Parse a single page into LayoutBlocks.

    Returns (blocks, page_metadata).
    """
    page = doc[pdf_page_number]
    page_meta: dict[str, Any] = {
        "pdf_page_number": pdf_page_number,
        "printed_page_label": printed_page_label,
        "page_width": page.rect.width,
        "page_height": page.rect.height,
    }

    try:
        # Primary: get_text('dict') for granular spans
        raw_dict = page.get_text("dict")
        dict_spans = []
        for block in raw_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    dict_spans.append({
                        "text": span.get("text", ""),
                        "bbox": span.get("bbox", (0, 0, 0, 0)),
                        "font": span.get("font", ""),
                        "size": span.get("size", 0),
                        "flags": span.get("flags", 0),
                        "color": span.get("color", 0),
                    })
        page_meta["dict_spans_count"] = len(dict_spans)
    except Exception:
        dict_spans = []
        page_meta["dict_spans_count"] = 0
        page_meta["dict_error"] = True

    # Blocks-based text extraction (always available)
    raw_blocks = page.get_text("blocks", sort=True)
    full_text = page.get_text("text")

    # Extract header for node_path
    header_text = ""
    for b in raw_blocks:
        if b[1] < 60:
            header_text += str(b[4]) + "\n"

    node_path_data = extract_node_path_from_header(header_text)
    page_meta["node_path_data"] = node_path_data
    page_meta["full_text_length"] = len(full_text)

    blocks: list[LayoutBlock] = []
    for i, b in enumerate(raw_blocks):
        x0, y0, x1, y1 = b[0], b[1], b[2], b[3]
        text = str(b[4]) if b[4] else ""
        text = text.replace("\x00", "").strip()

        if not text.strip():
            continue

        # Decode Hebrew if SI-960
        decoded_text, decoder, dec_conf, needs_he_review = decode_hebrew_if_needed(text)
        decoded_text = decoded_text.replace("\x00", "")

        lang = detect_language(decoded_text)
        block_type = classify_block(x0, y0, x1, y1, decoded_text, lang)
        sources, printed_refs, needs_ref_review = find_sources(decoded_text)
        crossrefs = find_crossrefs(decoded_text)

        # Associate dict spans that overlap this block
        block_spans = []
        for s in dict_spans:
            sb = s["bbox"]
            if (sb[0] >= x0 - 5 and sb[1] >= y0 - 5 and
                    sb[2] <= x1 + 5 and sb[3] <= y1 + 5):
                block_spans.append(s)

        # Confidence: deducir de claridad de clasificación
        confidence = 1.0
        if block_type == "unknown":
            confidence = 0.0
        elif block_type == "marginal_source" and lang == "es":
            confidence = 0.8
        elif block_type == "source_hebrew" and decoder == "hebrew_tex_decoder":
            confidence = dec_conf
        elif block_type == "main_explanation_es" and lang not in ("es", "mixed"):
            confidence = 0.7

        # Evidence role
        evidence_role: str | None = None
        if block_type == "source_hebrew":
            evidence_role = "source_text"
        elif block_type == "main_explanation_es":
            evidence_role = "commentary"
        elif block_type == "marginal_source":
            evidence_role = "marginal_citation"
        elif block_type == "footnote":
            evidence_role = "bibliographic_note"

        citable = block_type in (
            "source_hebrew", "main_explanation_es",
            "marginal_source", "footnote",
        )

        # Subtype guess for sources
        block_subtype: str | None = None
        if sources:
            stypes = {s["source_type"] for s in sources}
            if "Salmos" in stypes or "Tehilim" in stypes:
                block_subtype = "biblical_citation"
            elif "Avot" in stypes or "Rosh HaShaná" in stypes:
                block_subtype = "rabbinic_reference"
            elif "Shuljan Aruj" in stypes or "Remá" in stypes:
                block_subtype = "halachic_reference"
            elif "Likutei Moharán" in stypes or "Likutey Halajot" in stypes:
                block_subtype = "breslov_teaching"
            elif "Zohar" in stypes or "Saba diMishpatim" in stypes:
                block_subtype = "rabbinic_reference"

        block = LayoutBlock(
            block_index=i,
            block_type=block_type,
            block_subtype=block_subtype,
            evidence_role=evidence_role,
            language=lang,
            content=decoded_text,
            content_sha256=compute_sha256(decoded_text),
            content_length=len(decoded_text),
            page_number=pdf_page_number + 1,
            physical_page=pdf_page_number,
            printed_page_label=printed_page_label,
            bbox=(x0, y0, x1, y1),
            node_path=node_path_data["node_path"],
            section_title_he=node_path_data["section_title_he"],
            section_title_es=node_path_data["section_title_es"],
            halacha_ref=node_path_data["halacha_ref"],
            source_refs=sources,
            source_ref_as_printed=printed_refs,
            needs_reference_review=needs_ref_review,
            internal_cross_refs=crossrefs,
            citable=citable,
            layout_confidence=confidence,
            hebrew_decoder=decoder,
            hebrew_decoder_applied=bool(decoder and decoder != "unicode_direct"),
            needs_hebrew_review=needs_he_review,
            spans=block_spans,
        )
        blocks.append(block)

    return blocks, page_meta


# ---------------------------------------------------------------------------
# Composite page context
# ---------------------------------------------------------------------------


def build_composite_page_context(
    blocks: list[LayoutBlock],
    page_number: int,
    printed_page_label: str | None = None,
) -> LayoutBlock | None:
    """Build a composite_page_context block from all atomic blocks on a page.

    This is optional. The composite is marked citable=False.
    """
    texts = [b.content for b in blocks if b.content.strip()]
    if not texts:
        return None

    composite_text = "\n\n".join(texts)
    # Build source refs summary
    all_refs: list[dict] = []
    seen_refs: set[str] = set()
    for b in blocks:
        for r in b.source_refs:
            if r["matched_text"] not in seen_refs:
                all_refs.append(r)
                seen_refs.add(r["matched_text"])

    return LayoutBlock(
        block_index=-1,
        block_type="composite_page_context",
        evidence_role="composite_for_retrieval",
        language="mixed",
        content=composite_text,
        content_sha256=compute_sha256(composite_text),
        content_length=len(composite_text),
        page_number=page_number,
        physical_page=page_number - 1,
        printed_page_label=printed_page_label,
        node_path=blocks[0].node_path if blocks else None,
        source_refs=all_refs,
        source_ref_as_printed=[r["matched_text"] for r in all_refs],
        citable=False,
        layout_confidence=0.7,
        extraction_method="pymupdf_dict_layout_aware_composite",
        ingestion_profile="layout_aware_likutey_halajot",
    )


# ---------------------------------------------------------------------------
# PDF parser (full)
# ---------------------------------------------------------------------------


def parse_pdf(
    pdf_path: str,
    pages: list[int] | None = None,
    include_composites: bool = False,
) -> dict[int, list[LayoutBlock]]:
    """Parse a PDF into layout blocks per page.

    Args:
        pdf_path: Path to the PDF.
        pages: List of 0-indexed page numbers to parse (None = all).
        include_composites: Whether to also generate composite_page_context blocks.

    Returns:
        Dict mapping page_number (1-indexed) → list of LayoutBlock.
    """
    import fitz

    doc = fitz.open(pdf_path)
    total = doc.page_count

    if pages is None:
        pages = list(range(total))
    else:
        pages = [p for p in pages if 0 <= p < total]

    # Attempt to create a printed→PDF mapping
    mapping: dict[int, int] = {}
    for pg in range(total):
        page = doc[pg]
        hdr_text = ""
        hdr_blocks = page.get_text("blocks")
        for b in hdr_blocks:
            if b[1] < 60:
                hdr_text += str(b[4]) + "\n"
        # Try "NN LIKUTEY HALAJOT" pattern first (Spanish even pages)
        m = re.search(r"(\d+)\s+LIKUTEY HALAJOT", hdr_text)
        if not m:
            # Try Hebrew SI-960 header: require ≥3 consecutive high-byte chars
            m = re.search(r"[\x80-\xff]{3,}\s+(\d+)", hdr_text)
        if not m:
            # Try number near pipe separator
            m = re.search(r"(\d+)\s*[|]", hdr_text)
        if m:
            n = int(m.group(1))
            if 1 <= n <= 500:
                mapping[n] = pg

    pdf_to_printed: dict[int, int] = {v: k for k, v in mapping.items()}

    result: dict[int, list[LayoutBlock]] = {}
    for pg_idx in pages:
        printed_label = str(pdf_to_printed.get(pg_idx, ""))
        blocks, page_meta = parse_page(doc, pg_idx, printed_label)

        if include_composites and blocks:
            composite = build_composite_page_context(
                blocks, pg_idx + 1, printed_label,
            )
            if composite:
                blocks.append(composite)

        result[pg_idx + 1] = blocks

    doc.close()
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_pages_arg(arg: str) -> list[int]:
    """Parse --pages argument: '23,32,37' or '1-284' or '1-284,300,310'."""
    indices: list[int] = []
    for part in arg.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            indices.extend(range(int(a.strip()), int(b.strip()) + 1))
        else:
            indices.append(int(part))
    return [i - 1 for i in indices]  # convert 1-indexed → 0-indexed


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Likutey Halajot layout-aware parser (standalone)",
    )
    parser.add_argument("--pdf-path", default=None,
                        help="Path to PDF (default: probe PDF)")
    parser.add_argument("--pages", default=None,
                        help="Pages to parse: '23,32,37' or '1-284'")
    parser.add_argument("--output-dir", default="/tmp/layout_blocks",
                        help="Output directory for JSON blocks")
    parser.add_argument("--json", action="store_true",
                        help="Save per-page JSON files")
    parser.add_argument("--composites", action="store_true",
                        help="Also generate composite_page_context blocks")
    parser.add_argument("--summary", action="store_true",
                        help="Print summary table")

    args = parser.parse_args()

    pdf_path = args.pdf_path or "/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf"
    pages: list[int] | None = None
    if args.pages:
        pages = _parse_pages_arg(args.pages)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Parsing PDF: {pdf_path}")
    print(f"Pages: {args.pages or 'ALL'}")
    print()

    parsed = parse_pdf(pdf_path, pages=pages, include_composites=args.composites)

    total_blocks = 0
    type_counts: dict[str, int] = {}
    for page_blocks in parsed.values():
        total_blocks += len(page_blocks)
        for b in page_blocks:
            type_counts[b.block_type] = type_counts.get(b.block_type, 0) + 1

    print(f"Parsed {len(parsed)} pages, {total_blocks} blocks")
    print(f"\nBlock types:")
    for t, c in sorted(type_counts.items()):
        print(f"  {t:30s}: {c:5d}")

    if args.json:
        for pg, blocks in parsed.items():
            data = {
                "page_number": pg,
                "blocks": [b.to_dict() for b in blocks],
            }
            out_path = output_dir / f"page_{pg:04d}_blocks.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"\nJSON saved to {output_dir}")

    if args.summary:
        print(f"\n{'Page':>6s} | {'Blocks':>6s} | {'Types':>50s}")
        print("-" * 70)
        for pg in sorted(parsed):
            blocks = parsed[pg]
            t_counts: dict[str, int] = {}
            for b in blocks:
                t_counts[b.block_type] = t_counts.get(b.block_type, 0) + 1
            t_str = ", ".join(f"{k}={v}" for k, v in sorted(t_counts.items()))
            print(f"{pg:6d} | {len(blocks):6d} | {t_str[:50]}")


if __name__ == "__main__":
    main()
