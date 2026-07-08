#!/usr/bin/env python3
"""
Refined layout analysis for Likutey Halajot PDF.
Phase 3-6: Zone classification, node_path, footnotes, marginal sources.
"""
import json, sys, re
from pathlib import Path
from collections import defaultdict

import fitz

OUT_DIR = Path(__file__).parent
PDF_PATH = "/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf"
PAGE_W = 496
PAGE_H = 694

# ── Zone regions (relative to page) ──
ZONES = {
    "page_header":         (0.00, 0.00, 0.90, 0.09),
    "source_hebrew":       (0.09, 0.00, 0.90, 0.30),
    "section_marker_y":    (0.28, 0.34),
    "section_marker_w":    (0.35, 0.65),
    "main_explanation":    (0.34, 0.00, 0.90, 0.82),
    "marginal_source_x":   (0.70, 1.00),
    "marginal_source_w":   (0.00, 0.25),
    "notes_marker_y":      (0.80, 0.86),
    "footnote":            (0.82, 0.00, 1.00, 1.00),
}

def in_zone(x0, y0, x1, y1, zone) -> bool:
    rx0, ry0, rx1, ry1 = zone
    cx = (x0 + x1) / 2 / PAGE_W
    cy = (y0 + y1) / 2 / PAGE_H
    return rx0 <= cx <= rx1 and ry0 <= cy <= ry1

def refine_classification(x0, y0, x1, y1, text: str) -> str:
    h = PAGE_H
    rel_y0 = y0 / h
    rel_x0 = x0 / PAGE_W
    block_w = (x1 - x0) / PAGE_W
    block_h = (y1 - y0) / PAGE_H

    # Notes marker
    if "Notas y Fuentes" in text or "1RWHV" in text:
        return "notes_marker"

    # Section marker
    if "Likutey Halajot Explicado" in text or "/LNXWH" in text:
        return "section_marker"

    # Page header (top 9% of page)
    if rel_y0 < 0.09:
        return "page_header"

    # Marginal source: right side, narrow block
    if rel_x0 > 0.70 and block_w < 0.25:
        return "marginal_source"

    # Footnote area: bottom 18%
    if rel_y0 > 0.82:
        return "footnote"

    # Hebrew source: between header and section marker, typically high bytes
    if 0.09 <= rel_y0 < 0.30:
        # Check for SI-960 encoded Hebrew
        has_si960 = any('\x80' <= c < '\u02B0' and ord(c) >= 128 for c in text)
        if has_si960 or len(text) > 50:
            return "source_hebrew"

    # Main explanation
    return "main_explanation_es"

def detect_language(text: str) -> str:
    if not text.strip():
        return "unknown"
    he_count = sum(1 for c in text if '\u0590' <= c <= '\u05FF')
    si960_count = sum(1 for c in text if ord(c) >= 128 and ord(c) < 256 and not (32 <= ord(c) <= 126))
    total_alpha = sum(1 for c in text if c.isalpha())
    if he_count > total_alpha * 0.2:
        return "he"
    if si960_count > max(len(text) * 0.05, 3):
        return "he_si960"
    return "es"

def extract_printed_page(text: str) -> int | None:
    m = re.search(r'\x98\x83\x89\x8a\x82 \x87\x86\x83\x95\x87\x8a (\d+)', text)
    if m:
        return int(m.group(1))
    m = re.search(r'^(\d+)\s+LIKUTEY HALAJOT', text)
    if m:
        return int(m.group(1))
    return None

# ── Header patterns ──
HEADER_HE_PATTERN = re.compile(r'\x98\x83\x89\x8a\x82 \x87\x86\x83\x95\x87\x8a')  # "השכמת הבוקר" SI-960
HEADER_ES_PATTERN = re.compile(r'DISCURSO SOBRE EL LEVANTARSE')
HALACHA_PATTERN = re.compile(r'HALAJ[ÁA]\s+(\d+)[:.](\d+)')
HALACHA_HE_PATTERN = re.compile(r'\x82\x8c\x81\x95\x82 (\d+)[:.](\d+)')  # "הלכה" SI-960
SECTION_HE_PATTERN = re.compile(r'\x82\x8c\x81\x95\x82')  # "הלכה"
SECTION_MARKER_PATTERN = re.compile(r'Likutey Halajot Explicado|/LNXWH')

# ── Source reference patterns ──
SOURCE_PATTERNS = {
    "Salmos": r'Salmos?\s+\d+:\d+',
    "Tehilim": r'Tehilim\s+\d+:\d+',
    "Avot": r'Avot\s+\d+:\d+',
    "Rosh HaShaná": r'Rosh\s+HaShan[áa]\s+\d+[ab]',
    "Likutei Moharán": r'Likutei?\s*Mohar[áa]n',
    "Likutey Halajot": r'Likutey\s+Halajot',
    "Shuljan Aruj": r'Shuljan\s+Aruj',
    "Remá": r'Rem[áa]',
    "Zohar": r'Zohar',
    "Saba diMishpatim": r'Saba\s+diMishpatim',
    "Beit Hilel": r'Beit\s+Hilel',
    "Mija": r'Mija\s+\d+:\d+',
    "Proverbios": r'Proverbios\s+\d+:\d+',
}

def find_sources(text: str) -> list[dict]:
    sources = []
    for name, pattern in SOURCE_PATTERNS.items():
        for m in re.finditer(pattern, text, re.IGNORECASE):
            sources.append({
                "source_type": name,
                "matched_text": m.group(),
                "position": m.start(),
            })
    return sources

# ── Cross-reference patterns ──
CROSSREF_PATTERNS = [
    (r'ver\s+nota\s+\d+', 'note_ref'),
    (r'nota\s+\d+', 'note_ref'),
    (r'más\s+adelante', 'forward_ref'),
    (r'como\s+se\s+explic[óo]\s+anteriormente', 'backward_ref'),
    (r'ver\s+m[áa]s\s+arriba', 'backward_ref'),
    (r'ver\s+tambi[ée]n\s+la\s+nota', 'note_ref'),
    (r'ib[ií]d\.', 'ibid'),
    (r'secci[óo]n\s+siguiente', 'forward_ref'),
    (r'§\d+', 'section_ref'),
]

def find_crossrefs(text: str) -> list[dict]:
    refs = []
    for pattern, ref_type in CROSSREF_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            refs.append({
                "type": ref_type,
                "label": m.group(),
                "position": m.start(),
            })
    return refs

def extract_node_path(blocks: list) -> dict | None:
    """Extract node path from page header and content."""
    path = {
        "work_title": "Likutey Halajot",
        "section_title_he": None,
        "section_title_es": None,
        "halacha_ref": None,
        "node_path": None,
        "printed_page": None,
        "confidence": 0.0,
    }

    header_text = ""
    for b in blocks:
        x0, y0, x1, y1, text, _, _ = b
        if y0 < 60:
            header_text += text + "\n"

    # Hebrew header
    if HEADER_HE_PATTERN.search(header_text):
        path["section_title_he"] = "השכמת הבוקר"
        path["confidence"] += 0.3

    # Spanish header
    if HEADER_ES_PATTERN.search(header_text):
        path["section_title_es"] = "Discurso sobre el levantarse en la mañana"
        path["confidence"] += 0.3

    # Halacha reference
    m_es = HALACHA_PATTERN.search(header_text)
    if m_es:
        path["halacha_ref"] = f"Halajá {m_es.group(1)}:{m_es.group(2)}"
        path["confidence"] += 0.4

    m_he = HALACHA_HE_PATTERN.search(header_text)
    if m_he:
        path["halacha_ref"] = f"הלכה {m_he.group(1)}:{m_he.group(2)}"
        path["confidence"] += 0.4

    # Printed page
    pp = extract_printed_page(header_text)
    if pp:
        path["printed_page"] = pp

    # Build node_path
    parts = [path["work_title"]]
    if path["section_title_he"] or path["section_title_es"]:
        parts.append(path["section_title_es"] or path["section_title_he"] or "")
    if path["halacha_ref"]:
        parts.append(path["halacha_ref"])
    path["node_path"] = " > ".join(p for p in parts if p)

    return path

def analyze_page_refined(doc, pg_idx: int) -> dict:
    page = doc[pg_idx]
    blocks = page.get_text('blocks', sort=True)
    text_full = page.get_text('text')

    result = {
        "pdf_index": pg_idx,
        "full_text_length": len(text_full),
        "printed_page": extract_printed_page(text_full),
        "blocks": [],
        "node_path": None,
        "sources_found": [],
        "crossrefs_found": [],
    }

    for i, b in enumerate(blocks):
        x0, y0, x1, y1, text, _, _ = b
        cls = refine_classification(x0, y0, x1, y1, text)
        lang = detect_language(text)
        sources = find_sources(text)
        crossrefs = find_crossrefs(text)

        result["sources_found"].extend(sources)
        result["crossrefs_found"].extend(crossrefs)

        blk = {
            "block_index": i,
            "bbox": [round(x0), round(y0), round(x1), round(y1)],
            "classified_type": cls,
            "language": lang,
            "text_preview": text[:120].replace("\n", " | "),
            "text_length": len(text),
            "sources_in_block": len(sources),
            "crossrefs_in_block": len(crossrefs),
        }
        result["blocks"].append(blk)

    result["node_path"] = extract_node_path(blocks)
    result["total_blocks"] = len(blocks)
    result["total_sources"] = len(result["sources_found"])
    result["total_crossrefs"] = len(result["crossrefs_found"])

    return result

def print_page_summary(r: dict):
    pp = r["printed_page"] or "?"
    np = r["node_path"]["node_path"] if r["node_path"] else "N/A"
    cls_counts = defaultdict(int)
    lang_counts = defaultdict(int)
    for b in r["blocks"]:
        cls_counts[b["classified_type"]] += 1
        lang_counts[b["language"]] += 1

    print(f"PDF {r['pdf_index']:3d} → Printed {str(pp):>4s}")
    print(f"  Blocks: {r['total_blocks']:2d} | Chars: {r['full_text_length']:5d} | Sources: {r['total_sources']:2d} | Crossrefs: {r['total_crossrefs']:2d}")
    print(f"  Types: {dict(cls_counts)}")
    print(f"  Langs: {dict(lang_counts)}")
    print(f"  NodePath: {np}")
    print()

def main():
    doc = fitz.open(PDF_PATH)

    # Load page mapping
    mapping_path = OUT_DIR / "page_mapping.json"
    if mapping_path.exists():
        with open(mapping_path) as f:
            mapping = json.load(f)
        mapping = {int(k): int(v) for k, v in mapping.items()}
        printed_to_pdf = mapping
    else:
        printed_to_pdf = {}

    # Target pages for refined analysis
    targets = [0, 1, 2, 3, 19, 21, 35, 39, 40, 41, 48, 49, 50, 53, 54, 55, 57, 62, 67, 72, 77, 82, 87, 92, 97]

    all_results = {}
    for pg_idx in targets:
        r = analyze_page_refined(doc, pg_idx)
        all_results[str(pg_idx)] = r

    # ── Print comprehensive summary ──
    print("=" * 80)
    print("REFINED LAYOUT ANALYSIS — PHASES 3-6")
    print("=" * 80)
    print()

    for pg_idx in targets:
        r = all_results[str(pg_idx)]
        print_page_summary(r)

    # ── Source findings ──
    print("=" * 80)
    print("SOURCES FOUND ACROSS SAMPLE")
    print("=" * 80)
    source_summary = defaultdict(list)
    for pg_idx in targets:
        r = all_results[str(pg_idx)]
        for s in r["sources_found"]:
            source_summary[s["source_type"]].append((pg_idx, s["matched_text"]))

    for stype, instances in sorted(source_summary.items()):
        print(f"  {stype}: {len(instances)} occurrences")
        for pg, text in instances[:5]:
            print(f"    Page {pg}: {text}")
        if len(instances) > 5:
            print(f"    ... and {len(instances)-5} more")
    print()

    # ── Crossref findings ──
    print("=" * 80)
    print("CROSS-REFERENCES FOUND")
    print("=" * 80)
    crossref_summary = defaultdict(list)
    for pg_idx in targets:
        r = all_results[str(pg_idx)]
        for c in r["crossrefs_found"]:
            crossref_summary[c["type"]].append((pg_idx, c["label"]))
    for ctype, instances in sorted(crossref_summary.items()):
        print(f"  {ctype}: {len(instances)} occurrences")
        for pg, text in instances[:5]:
            print(f"    Page {pg}: {text}")
        if len(instances) > 5:
            print(f"    ... and {len(instances)-5} more")
    print()

    # ── Save compiled results ──
    output = {
        "sources": {str(k): v for k, v in source_summary.items()},
        "crossrefs": {str(k): v for k, v in crossref_summary.items()},
        "pages": all_results,
    }
    out_path = OUT_DIR / "refined_analysis.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"  Saved {out_path}")

    doc.close()

if __name__ == "__main__":
    main()
