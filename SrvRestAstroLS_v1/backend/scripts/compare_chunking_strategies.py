#! /usr/bin/env python3
"""
CLI: Compare generic vs section-aware (sijot-aware) chunking strategies.

Dry-run / read-only only. Does not write chunks to PostgreSQL or Milvus.

Usage:
    uv run python -m scripts.compare_chunking_strategies \\
        --collection breslov_test \\
        --document-title "El Alma del Rebe Najmán" \\
        --strategies generic,sijot-aware \\
        --output-json /tmp/tebaai_el_alma_chunking_compare.json \\
        --output-md /tmp/tebaai_el_alma_chunking_compare.md \\
        --sample-size 20 \\
        --max-samples 10
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import re
import statistics
import sys
from dataclasses import dataclass, field, asdict
from typing import Any
from uuid import UUID, uuid4


# ── Constants ───────────────────────────────────────────────────────────

SIJOT_EXPECTED_COUNT = 52
DEFAULT_CHUNK_SIZE = 1800
DEFAULT_CHUNK_OVERLAP = 250
DEFAULT_MIN_CHUNK = 200
LARGE_CHUNK_THRESHOLD = 2200
TINY_CHUNK_THRESHOLD = 150


# ── Data structures ─────────────────────────────────────────────────────


@dataclass
class TemporaryChunk:
    content: str
    char_start: int
    char_end: int
    content_length: int = 0
    has_heading: bool = False
    starts_with_heading: bool = False
    section_type: str | None = None
    section_number: int | None = None
    section_title: str | None = None
    section_label: str | None = None
    source_strategy: str = "generic"
    chunk_index: int = 0


@dataclass
class StrategyMetrics:
    chunks: int = 0
    avg_chars: float = 0.0
    median_chars: float = 0.0
    min_chars: int = 0
    max_chars: int = 0
    empty_chunks: int = 0
    duplicate_chunks: int = 0
    chunks_with_headings: int = 0
    chunks_starting_with_heading: int = 0
    overlap_count: int = 0
    total_chars: int = 0

    sections_detected: int = 0
    sijot_detected: int = 0
    missing_sijot: list[int] = field(default_factory=list)
    duplicate_sijot: list[int] = field(default_factory=list)
    chunks_crossing_sections: int = 0
    chunks_with_section_metadata: int = 0
    large_chunks: int = 0
    tiny_chunks: int = 0


@dataclass
class SimulatedSearchResult:
    query: str
    generic_results: list[dict] = field(default_factory=list)
    sijot_aware_results: list[dict] = field(default_factory=list)


# ── Generic strategy ────────────────────────────────────────────────────


def _paragraph_chunks(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
    min_chunk: int = DEFAULT_MIN_CHUNK,
) -> list[dict]:
    """Split text into chunks by paragraphs (in-memory)."""
    if not text.strip():
        return []

    paragraphs = text.split("\n\n")
    chunks: list[dict] = []
    current = ""
    current_start = 0
    end = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if current and len(current) + len(para) + 2 > chunk_size:
            if len(current) >= min_chunk:
                end = current_start + len(current)
                chunks.append({
                    "content": current.strip(),
                    "char_start": current_start,
                    "char_end": end,
                })
            overlap_text = current[-(overlap):] if overlap > 0 and len(current) > overlap else ""
            current = overlap_text
            current_start = max(0, end - overlap) if overlap > 0 else end

        if current:
            current += "\n\n" + para
        else:
            current = para

    if current.strip() and len(current.strip()) >= min_chunk:
        end = current_start + len(current)
        chunks.append({
            "content": current.strip(),
            "char_start": current_start,
            "char_end": end,
        })

    return chunks


def _compute_generic_chunks(text: str) -> list[TemporaryChunk]:
    """Run generic chunking and return TemporaryChunk list."""
    raw = _paragraph_chunks(text)
    result: list[TemporaryChunk] = []
    for idx, r in enumerate(raw):
        content = r["content"]
        has_heading = bool(re.search(r"^#{1,6}\s+", content, re.MULTILINE))
        starts_with_heading = bool(re.match(r"^#{1,6}\s+", content.strip()))
        tc = TemporaryChunk(
            content=content,
            char_start=r["char_start"],
            char_end=r["char_end"],
            content_length=len(content),
            has_heading=has_heading,
            starts_with_heading=starts_with_heading,
            source_strategy="generic",
            chunk_index=idx,
        )
        result.append(tc)
    return result


def _compute_generic_metrics(chunks: list[TemporaryChunk]) -> StrategyMetrics:
    m = StrategyMetrics()
    if not chunks:
        return m

    lengths = [c.content_length for c in chunks]
    m.chunks = len(chunks)
    m.avg_chars = round(statistics.mean(lengths), 1)
    m.median_chars = round(statistics.median(lengths), 1)
    m.min_chars = min(lengths)
    m.max_chars = max(lengths)
    m.empty_chunks = sum(1 for c in lengths if c == 0)
    m.total_chars = sum(lengths)

    seen: set[str] = set()
    for c in chunks:
        h = hashlib.sha256(c.content.encode()).hexdigest()
        if h in seen:
            m.duplicate_chunks += 1
        seen.add(h)

    m.chunks_with_headings = sum(1 for c in chunks if c.has_heading)
    m.chunks_starting_with_heading = sum(1 for c in chunks if c.starts_with_heading)

    for i in range(1, len(chunks)):
        if chunks[i].char_start < chunks[i - 1].char_end:
            m.overlap_count += 1

    return m


# ── Sijot-aware strategy ────────────────────────────────────────────────

SIJA_PATTERNS = [
    re.compile(r"(?:^|\n)#{1,3}\s*Sij[áa]\s*(?:N[º°]\s*)?(\d+)", re.IGNORECASE),
    re.compile(r"(?:^|\n)#{1,3}\s*Sij[aá]?\s*(?:N[º°]\s*)?(\d+)", re.IGNORECASE),
    re.compile(r"(?:^|\n)Sij[áa]\s+(?:N[º°]\s*)?(\d+)", re.IGNORECASE),
    re.compile(r"(?:^|\n)SIJA\s+(?:N[º°]\s*)?(\d+)"),
]

SECTION_TYPES = {
    "portada": re.compile(r"(?i)^\s*#{1,3}\s*(portada|cover|tapa)\b"),
    "creditos": re.compile(r"(?i)^\s*#{1,3}\s*(cr[eé]ditos|copyright|rights)\b"),
    "indice": re.compile(r"(?i)^\s*#{1,3}\s*([íi]ndice|table of contents|contenido)\b"),
    "prefacio": re.compile(r"(?i)^\s*#{1,3}\s*(prefacio|pr[oó]logo|foreword|introducci[oó]n del editor|nota del)\b"),
    "introduccion": re.compile(r"(?i)^\s*#{1,3}\s*(introducci[oó]n|introduction)\b"),
    "glosario": re.compile(r"(?i)^\s*#{1,3}\s*(glosario|glossary|ap[eé]ndice)\b"),
}


def _detect_section_type(line: str) -> str | None:
    stripped = line.strip()
    for stype, pattern in SECTION_TYPES.items():
        if pattern.search(stripped):
            return stype
    return None


def _find_sija_headers(text: str) -> list[dict]:
    """Find all Sija headers. Returns sorted list of dicts with position/number/label."""
    headers = []
    for pattern in SIJA_PATTERNS:
        for match in pattern.finditer(text):
            num = int(match.group(1))
            pos = match.start()
            label = match.group(0).strip()
            headers.append({
                "position": pos,
                "number": num,
                "label": label,
                "line": label,
            })
    seen_pos: set[int] = set()
    unique: list[dict] = []
    for h in sorted(headers, key=lambda x: x["position"]):
        if h["position"] not in seen_pos:
            seen_pos.add(h["position"])
            unique.append(h)
    return unique


def _find_section_boundaries(text: str) -> list[dict]:
    """Find all section boundaries (Sijot + other sections)."""
    boundaries = []

    sija_headers = _find_sija_headers(text)
    for h in sija_headers:
        boundaries.append({
            "position": h["position"],
            "type": "sija",
            "number": h["number"],
            "label": h["label"],
        })

    for match in re.finditer(r"^#{1,3}\s+(.+)$", text, re.MULTILINE):
        line = match.group(0)
        stype = _detect_section_type(line)
        if stype:
            boundaries.append({
                "position": match.start(),
                "type": stype,
                "number": None,
                "label": line.strip(),
            })

    boundaries.sort(key=lambda x: x["position"])
    return boundaries


def _compute_sijot_aware_chunks(text: str) -> list[TemporaryChunk]:
    """Run sijot-aware chunking returning TemporaryChunk list."""
    chunk_size = DEFAULT_CHUNK_SIZE
    min_chunk = DEFAULT_MIN_CHUNK

    boundaries = _find_section_boundaries(text)
    if not boundaries:
        fallback = _compute_generic_chunks(text)
        for c in fallback:
            c.source_strategy = "sijot-aware"
        return fallback

    sections: list[dict[str, Any]] = []
    for i, b in enumerate(boundaries):
        start = b["position"]
        end = boundaries[i + 1]["position"] if i + 1 < len(boundaries) else len(text)
        content = text[start:end].strip()
        sections.append({
            "position": start,
            "type": b["type"],
            "number": b["number"],
            "label": b["label"],
            "content": content,
            "end": end,
        })

    if boundaries and boundaries[0]["position"] > 0:
        pre_content = text[:boundaries[0]["position"]].strip()
        if pre_content:
            sections.insert(0, {
                "position": 0,
                "type": "preamble",
                "number": None,
                "label": None,
                "content": pre_content,
                "end": boundaries[0]["position"],
            })

    result: list[TemporaryChunk] = []
    global_idx = 0

    for sec in sections:
        sec_content = sec["content"]
        sec_type = sec["type"]
        sec_num = sec["number"]
        sec_label = sec["label"]

        if not sec_content:
            continue

        title_match = re.search(r"^#{1,3}\s+(.+)$", sec_content, re.MULTILINE)
        sec_title = title_match.group(1).strip() if title_match else (sec_label or "")

        section_label = ""
        if sec_type == "sija" and sec_label:
            section_label = sec_label
        elif sec_type == "sija":
            section_label = f"Sija {sec_num}" if sec_num else "Sija"
        else:
            section_label = sec_type.capitalize() if sec_type else ""

        lines = sec_content.split("\n")
        heading_line = ""
        remaining_lines = lines
        if lines and (lines[0].startswith("#") or re.match(r"^Sij[áa]\s+", lines[0], re.IGNORECASE)):
            heading_line = lines[0].strip()
            remaining_lines = lines[1:] if len(lines) > 1 else []
        remaining_text = "\n".join(remaining_lines).strip()

        total_section_len = len(sec_content)
        if total_section_len <= chunk_size * 1.2:
            tc = TemporaryChunk(
                content=sec_content,
                char_start=sec["position"],
                char_end=sec["end"],
                content_length=len(sec_content),
                has_heading=bool(heading_line),
                starts_with_heading=bool(heading_line),
                section_type=sec_type,
                section_number=sec_num,
                section_title=sec_title,
                section_label=section_label,
                source_strategy="sijot-aware",
                chunk_index=global_idx,
            )
            result.append(tc)
            global_idx += 1
        else:
            if heading_line:
                first_chunk_content = heading_line
            else:
                first_chunk_content = ""

            paras = remaining_text.split("\n\n")
            para_idx = 0
            current_content = first_chunk_content
            start_pos = sec["position"]

            while para_idx < len(paras):
                para = paras[para_idx].strip()
                if not para:
                    para_idx += 1
                    continue

                if current_content and len(current_content) + len(para) + 2 > chunk_size:
                    if len(current_content) >= min_chunk or (not result and heading_line):
                        tc = TemporaryChunk(
                            content=current_content.strip(),
                            char_start=start_pos,
                            char_end=start_pos + len(current_content),
                            content_length=len(current_content),
                            has_heading=bool(heading_line) and heading_line in current_content,
                            starts_with_heading=bool(heading_line) and current_content.startswith(heading_line),
                            section_type=sec_type,
                            section_number=sec_num,
                            section_title=sec_title,
                            section_label=section_label,
                            source_strategy="sijot-aware",
                            chunk_index=global_idx,
                        )
                        result.append(tc)
                        global_idx += 1

                    overlap_size = min(150, len(current_content))
                    overlap_text = current_content[-overlap_size:] if overlap_size > 0 else ""
                    current_content = overlap_text
                    start_pos = sec["position"] + sec_content.find(overlap_text) if overlap_text else sec["position"]

                if current_content:
                    current_content += "\n\n" + para
                else:
                    current_content = para
                    start_pos = sec["position"] + sec_content.find(para)

                para_idx += 1

            if current_content.strip() and len(current_content.strip()) >= min_chunk:
                tc = TemporaryChunk(
                    content=current_content.strip(),
                    char_start=start_pos,
                    char_end=sec["end"],
                    content_length=len(current_content),
                    has_heading=bool(heading_line) and heading_line in current_content,
                    starts_with_heading=bool(heading_line) and current_content.startswith(heading_line),
                    section_type=sec_type,
                    section_number=sec_num,
                    section_title=sec_title,
                    section_label=section_label,
                    source_strategy="sijot-aware",
                    chunk_index=global_idx,
                )
                result.append(tc)
                global_idx += 1

    return result


def _compute_sijot_metrics(chunks: list[TemporaryChunk]) -> StrategyMetrics:
    m = StrategyMetrics()
    if not chunks:
        return m

    lengths = [c.content_length for c in chunks]
    m.chunks = len(chunks)
    m.avg_chars = round(statistics.mean(lengths), 1) if lengths else 0.0
    m.median_chars = round(statistics.median(lengths), 1) if lengths else 0.0
    m.min_chars = min(lengths)
    m.max_chars = max(lengths)
    m.empty_chunks = sum(1 for c in lengths if c == 0)
    m.total_chars = sum(lengths)

    seen: set[str] = set()
    for c in chunks:
        h = hashlib.sha256(c.content.encode()).hexdigest()
        if h in seen:
            m.duplicate_chunks += 1
        seen.add(h)

    m.chunks_with_headings = sum(1 for c in chunks if c.has_heading)
    m.chunks_starting_with_heading = sum(1 for c in chunks if c.starts_with_heading)

    detected_sijot: set[int] = set()
    seen_sijot_positions: dict[int, int] = {}

    for c in chunks:
        if c.section_type == "sija" and c.section_number is not None:
            detected_sijot.add(c.section_number)
            seen_sijot_positions[c.section_number] = seen_sijot_positions.get(c.section_number, 0) + 1
            m.chunks_with_section_metadata += 1

    m.sections_detected = len(detected_sijot)
    m.sijot_detected = len(detected_sijot)

    for i in range(len(chunks) - 1):
        if (chunks[i].section_type == "sija" and chunks[i + 1].section_type == "sija"
                and chunks[i].section_number != chunks[i + 1].section_number
                and chunks[i].char_end > chunks[i + 1].char_start // 2):
            m.chunks_crossing_sections += 1

    all_expected = set(range(1, SIJOT_EXPECTED_COUNT + 1))
    m.missing_sijot = sorted(all_expected - detected_sijot)
    m.duplicate_sijot = sorted([num for num, count in seen_sijot_positions.items() if count > 1])
    m.large_chunks = sum(1 for c in chunks if c.content_length > LARGE_CHUNK_THRESHOLD)
    m.tiny_chunks = sum(1 for c in chunks if c.content_length < TINY_CHUNK_THRESHOLD)

    return m


# ── Simulated search ───────────────────────────────────────────────────


def _normalize_text(text: str) -> str:
    text = text.lower()
    replacements = {'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'ü': 'u', 'ñ': 'n'}
    for acc, plain in replacements.items():
        text = text.replace(acc, plain)
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _simulated_search(query: str, chunks: list[TemporaryChunk], top_k: int = 5) -> list[dict]:
    norm_query = _normalize_text(query)
    scored = []
    for c in chunks:
        norm_content = _normalize_text(c.content)
        if norm_query in norm_content:
            pos = norm_content.index(norm_query)
            score = 1.0 / (1.0 + pos / max(1, len(norm_content)))
            scored.append({
                "chunk_index": c.chunk_index,
                "section_type": c.section_type,
                "section_number": c.section_number,
                "section_label": c.section_label,
                "heading": c.section_title or "",
                "content_preview": c.content[:150].strip(),
                "char_start": c.char_start,
                "char_end": c.char_end,
                "score": round(score, 4),
                "content_length": c.content_length,
            })
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


# ── Page mapping simulation ────────────────────────────────────────────


def _simulate_page_mapping(chunks: list[TemporaryChunk], text: str, total_pdf_pages: int = 200) -> dict:
    total_chars = len(text)
    if total_chars == 0:
        return {}

    mapping_results = {}
    for c in chunks:
        page_est = max(1, round(c.char_start / total_chars * total_pdf_pages) + 1)
        page_est_end = max(page_est, min(total_pdf_pages, round(c.char_end / total_chars * total_pdf_pages) + 1))
        if c.section_type == "sija" and c.section_number is not None:
            confidence = "high"
        elif c.section_type == "sija":
            confidence = "medium"
        elif c.section_type:
            confidence = "medium"
        else:
            confidence = "low"

        mapping_results[c.chunk_index] = {
            "page_candidate": page_est,
            "page_end_candidate": page_est_end,
            "confidence": confidence,
            "section_type": c.section_type,
            "section_number": c.section_number,
        }
    return mapping_results


def _compute_page_mapping_summary(mapping: dict) -> dict:
    if not mapping:
        return {"high": 0, "medium": 0, "low": 0, "none": 0, "ambiguous": 0}
    counts = {"high": 0, "medium": 0, "low": 0, "none": 0, "ambiguous": 0}
    for v in mapping.values():
        conf = v.get("confidence", "none")
        if conf in counts:
            counts[conf] += 1
        else:
            counts["none"] += 1
    return counts


# ── PostgreSQL fetch ───────────────────────────────────────────────────


async def _fetch_document_text(collection: str, document_title: str) -> tuple[str | None, dict[str, Any] | None]:
    try:
        from core.config import get_settings
        from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool

        settings = get_settings()
        if not settings.postgres_enabled:
            print("WARNING: PostgreSQL not enabled. Cannot read document from DB.", file=sys.stderr)
            return None, None

        pool = create_pool_from_settings()
        await open_pool(pool)

        try:
            async with pool.connection() as conn:
                from psycopg.rows import dict_row
                conn.row_factory = dict_row
                cur = conn.cursor()
                await cur.execute("""
                    SELECT t.content, d.bibliographic_metadata, d.id, d.title
                    FROM library_documents d
                    JOIN library_collections c ON c.id = d.collection_id
                    JOIN library_document_texts t ON t.document_id = d.id
                    WHERE c.code = %(code)s
                      AND d.title = %(title)s
                    LIMIT 1
                """, {"code": collection, "title": document_title})
                row = await cur.fetchone()
                if row:
                    meta = row.get("bibliographic_metadata")
                    if isinstance(meta, str):
                        try:
                            meta = json.loads(meta)
                        except (json.JSONDecodeError, TypeError):
                            meta = {}
                    return row["content"], meta
                print(f"Document '{document_title}' not found in collection '{collection}'", file=sys.stderr)
                return None, None
        finally:
            await close_pool(pool)
    except Exception as e:
        print(f"WARNING: Could not fetch document from PostgreSQL: {e}", file=sys.stderr)
        return None, None


# ── Report builders ────────────────────────────────────────────────────


def _build_json_report(
    document_title: str,
    collection: str,
    text: str,
    generic_metrics: StrategyMetrics,
    sijot_metrics: StrategyMetrics,
    page_mapping_generic: dict,
    page_mapping_sijot: dict,
    simulated_searches: list[SimulatedSearchResult],
    recommendation: dict,
) -> dict:
    def _ps(mapping):
        return _compute_page_mapping_summary(mapping)

    return {
        "collection": collection,
        "document_title": document_title,
        "total_chars": len(text),
        "status": "test_candidate",
        "strategies": {
            "generic": asdict(generic_metrics),
            "sijot_aware": asdict(sijot_metrics),
        },
        "page_mapping": {
            "generic": _ps(page_mapping_generic),
            "sijot_aware": _ps(page_mapping_sijot),
        },
        "simulated_searches": [
            {
                "query": s.query,
                "generic_hits": len(s.generic_results),
                "sijot_aware_hits": len(s.sijot_aware_results),
                "generic_top": s.generic_results[0] if s.generic_results else None,
                "sijot_aware_top": s.sijot_aware_results[0] if s.sijot_aware_results else None,
            }
            for s in simulated_searches
        ],
        "comparison": recommendation,
    }


def _build_md_report(
    document_title: str,
    collection: str,
    text: str,
    generic_metrics: StrategyMetrics,
    sijot_metrics: StrategyMetrics,
    boundaries: list[dict],
    page_mapping_generic: dict,
    page_mapping_sijot: dict,
    simulated_searches: list[SimulatedSearchResult],
    recommendation: dict,
) -> str:
    lines = [
        f"# {document_title} — Generic vs Sijot-aware chunking dry-run",
        "",
        f"**Collection**: {collection}",
        f"**Total text chars**: {len(text):,}",
        f"**Status**: test_candidate",
        "",
        "## Summary",
        "",
        f"This dry-run compares the current generic paragraph-based chunker with a section-aware (Sijot-aware) strategy.",
        "No chunks were persisted. No Milvus or LiteLLM calls were made.",
        "",
        "## Generic strategy",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Chunks | {generic_metrics.chunks} |",
        f"| Avg chars | {generic_metrics.avg_chars} |",
        f"| Median chars | {generic_metrics.median_chars} |",
        f"| Min chars | {generic_metrics.min_chars} |",
        f"| Max chars | {generic_metrics.max_chars} |",
        f"| Empty chunks | {generic_metrics.empty_chunks} |",
        f"| Duplicate chunks | {generic_metrics.duplicate_chunks} |",
        f"| Chunks with headings | {generic_metrics.chunks_with_headings} |",
        f"| Chunks starting with heading | {generic_metrics.chunks_starting_with_heading} |",
        "",
        "## Sijot-aware strategy",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Chunks | {sijot_metrics.chunks} |",
        f"| Avg chars | {sijot_metrics.avg_chars} |",
        f"| Median chars | {sijot_metrics.median_chars} |",
        f"| Min chars | {sijot_metrics.min_chars} |",
        f"| Max chars | {sijot_metrics.max_chars} |",
        f"| Empty chunks | {sijot_metrics.empty_chunks} |",
        f"| Duplicate chunks | {sijot_metrics.duplicate_chunks} |",
        f"| Chunks with headings | {sijot_metrics.chunks_with_headings} |",
        f"| Chunks starting with heading | {sijot_metrics.chunks_starting_with_heading} |",
        f"| Large chunks (>{LARGE_CHUNK_THRESHOLD}) | {sijot_metrics.large_chunks} |",
        f"| Tiny chunks (<{TINY_CHUNK_THRESHOLD}) | {sijot_metrics.tiny_chunks} |",
        "",
        "## Section detection",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Sections detected | {sijot_metrics.sections_detected} |",
        f"| Sijot detected (unique) | {sijot_metrics.sijot_detected} |",
        f"| Expected Sijot (1–52) | {SIJOT_EXPECTED_COUNT} |",
        f"| Missing Sijot | {sijot_metrics.missing_sijot} |",
        f"| Duplicate Sijot | {sijot_metrics.duplicate_sijot} |",
        f"| Chunks crossing sections | {sijot_metrics.chunks_crossing_sections} |",
        f"| Chunks with section metadata | {sijot_metrics.chunks_with_section_metadata} |",
        "",
    ]

    if boundaries:
        lines += ["### Boundary types detected", "", "| Type | Count |", "|------|-------|"]
        type_counts: dict[str, int] = {}
        for b in boundaries:
            bt = b["type"]
            type_counts[bt] = type_counts.get(bt, 0) + 1
        for bt, count in sorted(type_counts.items()):
            lines.append(f"| {bt} | {count} |")
        lines.append("")

    pg = _compute_page_mapping_summary(page_mapping_generic)
    ps = _compute_page_mapping_summary(page_mapping_sijot)
    lines += [
        "## Page mapping dry-run",
        "",
        "| Strategy | High | Medium | Low | None | Ambiguous |",
        "|----------|-----:|-------:|----:|-----:|---------:|",
        f"| Generic | {pg['high']} | {pg['medium']} | {pg['low']} | {pg['none']} | {pg['ambiguous']} |",
        f"| Sijot-aware | {ps['high']} | {ps['medium']} | {ps['low']} | {ps['none']} | {ps['ambiguous']} |",
        "",
        "*Note: Page mapping is character-position estimation, not PDF re-extraction.*",
        "",
        "## Simulated searches",
        "",
        "| Query | Generic hits | Sijot-aware hits | Best section (Sijot-aware) |",
        "|-------|-------------:|-----------------:|---------------------------|",
    ]
    for s in simulated_searches:
        sija_best = ""
        if s.sijot_aware_results:
            r = s.sijot_aware_results[0]
            sija_best = f"{r.get('section_label', '')} (#{r.get('section_number', '')})"
        lines.append(f"| {s.query} | {len(s.generic_results)} | {len(s.sijot_aware_results)} | {sija_best} |")
    lines.append("")

    lines += [
        "## Risks",
        "",
        "- Dry-run only: no chunks persisted, no Milvus, no LiteLLM.",
        "- Section detection is heuristic based on heading patterns.",
        "- Sija numbering depends on consistent header formatting in PDF extraction.",
        "- Page mapping uses character-position estimation.",
        "",
        "## Recommendation",
        "",
        f"| Option | Decision | Motivo |",
        f"|--------|----------|--------|",
        f"| **{recommendation.get('recommended_option', 'D')}** | {recommendation.get('reason', '')} | See JSON for details |",
        "",
    ]

    return "\n".join(lines)


# ── CLI ─────────────────────────────────────────────────────────────────


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare generic vs section-aware chunking strategies (dry-run only).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--collection", default="breslov_test", help="Collection code")
    parser.add_argument("--document-title", default="El Alma del Rebe Najmán", help="Document title")
    parser.add_argument(
        "--strategies", default="generic,sijot-aware",
        help="Comma-separated strategy names (default: generic,sijot-aware)",
    )
    parser.add_argument("--output-json", default="/tmp/tebaai_el_alma_chunking_compare.json", help="Output JSON path")
    parser.add_argument("--output-md", default="/tmp/tebaai_el_alma_chunking_compare.md", help="Output Markdown path")
    parser.add_argument("--sample-size", type=int, default=0, help="Sample text size for quick testing")
    parser.add_argument("--max-samples", type=int, default=0, help="Max result entries in searches")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    return parser.parse_args(argv)


def _analyze(
    text: str,
    strategies: list[str],
    collection: str,
    document_title: str,
    sample_size: int = 0,
    max_samples: int = 0,
    verbose: bool = False,
) -> tuple[dict, str, list[TemporaryChunk], list[TemporaryChunk]]:
    """Run the analysis. Returns (json_report, md_report, generic_chunks, sijot_chunks)."""

    # Apply sample if requested
    if sample_size > 0 and sample_size < len(text):
        if verbose:
            print(f"  Using sample of {sample_size} chars from {len(text)} total", file=sys.stderr)
        text = text[:sample_size]

    generic_chunks: list[TemporaryChunk] = []
    sijot_chunks: list[TemporaryChunk] = []
    generic_metrics = StrategyMetrics()
    sijot_metrics = StrategyMetrics()
    boundaries: list[dict] = []

    if "generic" in strategies:
        if verbose:
            print("  Computing generic chunks...", file=sys.stderr)
        generic_chunks = _compute_generic_chunks(text)
        generic_metrics = _compute_generic_metrics(generic_chunks)
        if verbose:
            print(f"  Generic: {generic_metrics.chunks} chunks", file=sys.stderr)

    if "sijot-aware" in strategies:
        if verbose:
            print("  Computing sijot-aware chunks...", file=sys.stderr)
        sijot_chunks = _compute_sijot_aware_chunks(text)
        sijot_metrics = _compute_sijot_metrics(sijot_chunks)
        boundaries = _find_section_boundaries(text)
        if verbose:
            print(f"  Sijot-aware: {sijot_metrics.chunks} chunks, {sijot_metrics.sijot_detected} Sijot detected", file=sys.stderr)

    # Page mapping
    page_mapping_generic = _simulate_page_mapping(generic_chunks, text) if generic_chunks else {}
    page_mapping_sijot = _simulate_page_mapping(sijot_chunks, text) if sijot_chunks else {}

    # Simulated searches
    search_queries = [
        "La maravilla del cerebro",
        "servir a HaShem",
        "Rabí Zvi Aryeh Rosenfeld",
        "Sija 25",
        "emuná",
    ]
    simulated_searches = []
    for q in search_queries:
        top_k = max_samples if max_samples > 0 else 5
        g_results = _simulated_search(q, generic_chunks, top_k) if generic_chunks else []
        s_results = _simulated_search(q, sijot_chunks, top_k) if sijot_chunks else []
        simulated_searches.append(SimulatedSearchResult(query=q, generic_results=g_results, sijot_aware_results=s_results))

    # Recommendation logic
    rec = _compute_recommendation(generic_metrics, sijot_metrics, boundaries, verbose)

    # Build reports
    json_report = _build_json_report(
        document_title, collection, text,
        generic_metrics, sijot_metrics,
        page_mapping_generic, page_mapping_sijot,
        simulated_searches, rec,
    )
    md_report = _build_md_report(
        document_title, collection, text,
        generic_metrics, sijot_metrics,
        boundaries,
        page_mapping_generic, page_mapping_sijot,
        simulated_searches, rec,
    )

    return json_report, md_report, generic_chunks, sijot_chunks


def _compute_recommendation(
    generic_metrics: StrategyMetrics,
    sijot_metrics: StrategyMetrics,
    boundaries: list[dict],
    verbose: bool = False,
) -> dict:
    """Compute the recommendation based on dry-run metrics.

    Returns dict with recommended_option (A/B/C/D) and reason.
    """

    # Count how many of 52 Sijot were detected
    sijot_detected = sijot_metrics.sijot_detected
    missing = sijot_metrics.missing_sijot

    # If no sections found at all, generic is the only option
    if sijot_detected == 0:
        if verbose:
            print("  Recommendation: A (no sections detected, generic is baseline)", file=sys.stderr)
        return {
            "recommended_option": "A",
            "reason": "No sections detected in document text. The generic strategy is the only viable option.",
        }

    # If most Sijot are missing, need improvement before applying
    if len(missing) > 30:
        if verbose:
            print(f"  Recommendation: C (only {sijot_detected}/52 Sijot detected, need improvement)", file=sys.stderr)
        return {
            "recommended_option": "C",
            "reason": f"Only {sijot_detected}/52 Sijot detected ({len(missing)} missing). The section detector needs improvement before it can be applied.",
            "sijot_detected": sijot_detected,
            "missing_sijot_count": len(missing),
            "missing_sijot": missing,
        }

    # If significant coverage but with gaps
    if len(missing) > 10:
        if verbose:
            print(f"  Recommendation: C (partial detection: {sijot_detected}/52, {len(missing)} missing)", file=sys.stderr)
        return {
            "recommended_option": "C",
            "reason": f"Partial Sijot detection: {sijot_detected}/52 found, {len(missing)} missing. Improve detector before applying.",
            "sijot_detected": sijot_detected,
            "missing_sijot_count": len(missing),
            "missing_sijot": missing,
        }

    # Good coverage: check crossing sections and chunk quality
    if sijot_metrics.chunks_crossing_sections > 0:
        if verbose:
            print(f"  Recommendation: C ({sijot_metrics.chunks_crossing_sections} chunks cross sections)", file=sys.stderr)
        return {
            "recommended_option": "C",
            "reason": f"{sijot_metrics.chunks_crossing_sections} chunks cross section boundaries. Fix section boundary detection before applying.",
            "crossing_sections": sijot_metrics.chunks_crossing_sections,
        }

    # Full or near-full detection with no crossing issues
    if sijot_detected >= 50:
        if verbose:
            print(f"  Recommendation: B ({sijot_detected}/52 Sijot detected cleanly)", file=sys.stderr)
        return {
            "recommended_option": "B",
            "reason": f"Strong section detection: {sijot_detected}/52 Sijot found with no crossing issues. Ready for application.",
            "sijot_detected": sijot_detected,
        }

    # Good but not perfect detection
    return {
        "recommended_option": "B",
        "reason": f"Good section detection: {sijot_detected}/52 Sijot found. Suitable for application.",
        "sijot_detected": sijot_detected,
    }


async def _run(args: argparse.Namespace) -> int:
    """Main async entry point. Fetches text from PostgreSQL then runs analysis."""
    print(f"── Compare chunking strategies (dry-run) ──", file=sys.stderr)
    print(f"  Collection:  {args.collection}", file=sys.stderr)
    print(f"  Document:    {args.document_title}", file=sys.stderr)
    print(f"  Strategies:  {args.strategies}", file=sys.stderr)
    print(f"  Sample size: {args.sample_size or 'full'}", file=sys.stderr)
    print(f"  Output JSON: {args.output_json}", file=sys.stderr)
    print(f"  Output MD:   {args.output_md}", file=sys.stderr)
    print(file=sys.stderr)

    strategies = [s.strip() for s in args.strategies.split(",")]

    # Fetch text from PostgreSQL
    text, metadata = await _fetch_document_text(args.collection, args.document_title)
    if text is None:
        print("\nERROR: Could not read document from PostgreSQL.", file=sys.stderr)
        print("To use this script, set TEBAAI_POSTGRES_ENABLED=true and provide", file=sys.stderr)
        print("PostgreSQL connection environment variables.", file=sys.stderr)
        return 1

    text_len = len(text)
    print(f"  Text chars:  {text_len:,}", file=sys.stderr)
    print(file=sys.stderr)

    # Run analysis
    json_report, md_report, generic_chunks, sijot_chunks = _analyze(
        text, strategies, args.collection, args.document_title,
        sample_size=args.sample_size,
        max_samples=args.max_samples,
        verbose=args.verbose,
    )

    # Write JSON output
    with open(args.output_json, "w", encoding="utf-8") as f:
        json.dump(json_report, f, indent=2, ensure_ascii=False)
    print(f"JSON report written: {args.output_json}", file=sys.stderr)

    # Write Markdown output
    with open(args.output_md, "w", encoding="utf-8") as f:
        f.write(md_report)
    print(f"Markdown report written: {args.output_md}", file=sys.stderr)

    # Summary
    if args.verbose:
        g = json_report["strategies"]["generic"]
        s = json_report["strategies"]["sijot_aware"]
        print(file=sys.stderr)
        print(f"  Generic:      {g['chunks']} chunks, avg {g['avg_chars']} chars", file=sys.stderr)
        print(f"  Sijot-aware:  {s['chunks']} chunks, avg {s['avg_chars']} chars", file=sys.stderr)
        print(f"  Sections:     {s['sijot_detected']}/{SIJOT_EXPECTED_COUNT} Sijot detected", file=sys.stderr)
        print(f"  Missing:      {s['missing_sijot']}", file=sys.stderr)
        print(f"  Recommend:    {json_report['comparison']['recommended_option']}", file=sys.stderr)
        print(file=sys.stderr)

    print("── Dry-run complete. No chunks were written. ──", file=sys.stderr)
    return 0


def main() -> int:
    args = _parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())