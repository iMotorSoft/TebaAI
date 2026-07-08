"""
Likutey Halajot Layout Probe — Common utilities.
Read-only analysis of PDF layout zones.
"""
import json, os, re
from pathlib import Path

OUT_DIR = Path("/media/issajar/DEVELOP/Projects/iMotorSoft/ai/dev/TebaAI/tmp/likutey_layout_probe")
PDF_PATH = "/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf"
PAGE_W = 496
PAGE_H = 694

# ── printed page → PDF index mapping ──
# Discovered by scanning headers
PRINTED_TO_PDF: dict[int, int] = {}
# PDF index → printed page
PDF_TO_PRINTED: dict[int, int] = {}

# Heuristic: given a page header text, extract printed page number
HEADER_RE = re.compile(r'^\d+')
HEBREW_PAGE_RE = re.compile(r'\x98\x83\x89\x8a\x82 \x87\x86\x83\x95\x87\x8a (\d+)')

def classify_block(x0, y0, x1, y1) -> str:
    """Heuristic block type based on position."""
    h = PAGE_H
    w = PAGE_W
    rel_y0 = y0 / h
    rel_y1 = y1 / h
    rel_x0 = x0 / w
    rel_x1 = x1 / w

    # Top zone: header
    if rel_y0 < 0.09:
        return "page_header"

    # Bottom zone: footnotes
    if rel_y0 > 0.82:
        return "footnote_area"

    # Right margin: marginal sources (x > 70% of page width, narrow)
    if rel_x0 > 0.70 and (rel_x1 - rel_x0) < 0.25:
        return "marginal_source"

    # Section marker zone (y ~0.30-0.33)
    if 0.28 < rel_y0 < 0.34 and 0.35 < rel_x0 < 0.65 and (rel_y1 - rel_y0) < 0.02:
        return "section_marker"

    # Hebrew source zone (upper-mid area on odd pages)
    if rel_y0 < 0.34:
        return "source_hebrew"

    # Main explanation
    return "main_explanation_es"

def detect_language(text: str) -> str:
    """Rough language detection."""
    if not text.strip():
        return "unknown"
    he_count = sum(1 for c in text if '\u0590' <= c <= '\u05FF')
    es_chars = sum(1 for c in text if c.isalpha())
    if he_count > es_chars * 0.3:
        return "he"
    # Check for SI-960 encoded Hebrew (bytes in range \x80-\x9F)
    si960_count = sum(1 for c in text if '\x80' <= c <= '\u02AF' and ord(c) < 256)
    if si960_count > len(text) * 0.1 and len(text) > 50:
        return "he_si960"
    return "es"

def is_section_marker(text: str) -> bool:
    return "Likutey Halajot Explicado" in text or "Likutey Halajot Explicado" in text \
        or "/LNXWH" in text or "LNXWH" in text

def is_notes_marker(text: str) -> bool:
    return "Notas y Fuentes" in text or "1RWHV" in text

def is_marginal_style(block_w: float, block_h: float, x0: float) -> bool:
    """Check if block looks like marginal source (narrow, right-side)."""
    return x0 > 350 and block_w < 95

def extract_page_number(text: str) -> int | None:
    m = HEBREW_PAGE_RE.search(text)
    if m:
        return int(m.group(1))
    # Try "NN LIKUTEY HALAJOT" pattern
    m2 = re.search(r'^(\d+)\s+LIKUTEY HALAJOT', text)
    if m2:
        return int(m2.group(1))
    # Try just number at start
    m3 = HEADER_RE.match(text.strip())
    if m3:
        n = int(m3.group())
        if 1 <= n <= 500:
            return n
    return None

def build_page_mapping(doc) -> dict:
    """Build printed→PDF page mapping by scanning headers."""
    mapping = {}
    for pg_idx in range(len(doc)):
        page = doc[pg_idx]
        text = page.get_text('text')
        # Check header blocks
        blocks = page.get_text('blocks')
        for b in blocks:
            x0, y0, x1, y1, btext, _, _ = b
            if y0 < 60:  # header zone
                pn = extract_page_number(btext)
                if pn:
                    mapping[pn] = pg_idx
                    break
    return mapping

def save_json(filename: str, data):
    path = OUT_DIR / filename
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  Saved {path}")
