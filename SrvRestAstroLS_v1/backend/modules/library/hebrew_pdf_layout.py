"""Geometry-based reconstruction for Hebrew PDF text layers.

PDF text extraction may insert spaces between Hebrew grapheme clusters or emit
them in visual order.  This module rebuilds a logical Unicode line from glyph
coordinates.  It does not reverse strings and does not modify the source PDF.
"""
from __future__ import annotations

from functools import lru_cache
import re
import unicodedata

HEBREW_RE = re.compile(r"[\u0590-\u05ff]")
HEBREW_BASE_RE = re.compile(r"[\u05d0-\u05ea]")


def readable_line(raw_line: dict) -> str:
    """Rebuild one rawdict line in logical order using glyph coordinates."""
    clusters: list[dict[str, float | str]] = []
    raw_values: list[str] = []
    for span in raw_line.get("spans", []):
        for char in span.get("chars", []):
            value = unicodedata.normalize("NFKC", str(char.get("c", "")))
            if not value:
                continue
            raw_values.append(value)
            if value.isspace():
                continue
            bbox = char.get("bbox", (0.0, 0.0, 0.0, 0.0))
            if all(unicodedata.combining(item) for item in value) and clusters:
                if HEBREW_BASE_RE.search(str(clusters[-1]["text"])):
                    clusters[-1]["text"] = str(clusters[-1]["text"]) + value
                    clusters[-1]["x0"] = min(float(clusters[-1]["x0"]), float(bbox[0]))
                    clusters[-1]["x1"] = max(float(clusters[-1]["x1"]), float(bbox[2]))
                else:
                    clusters.append({"text": value, "x0": float(bbox[0]), "x1": float(bbox[2])})
            else:
                clusters.append({"text": value, "x0": float(bbox[0]), "x1": float(bbox[2])})
    if not clusters:
        return ""

    for orphan in [cluster for cluster in clusters if all(unicodedata.combining(char) for char in str(cluster["text"]))]:
        candidates = [
            cluster for cluster in clusters
            if cluster is not orphan and any(not unicodedata.combining(char) for char in str(cluster["text"]))
        ]
        if candidates:
            hebrew_candidates = [cluster for cluster in candidates if HEBREW_BASE_RE.search(str(cluster["text"]))]
            center = (float(orphan["x0"]) + float(orphan["x1"])) / 2
            target = min(
                hebrew_candidates or candidates,
                key=lambda cluster: abs(((float(cluster["x0"]) + float(cluster["x1"])) / 2) - center),
            )
            target["text"] = str(target["text"]) + str(orphan["text"])
            clusters.remove(orphan)

    hebrew_clusters = sum(bool(HEBREW_RE.search(str(cluster["text"]))) for cluster in clusters)
    if hebrew_clusters <= len(clusters) * 0.45:
        return unicodedata.normalize("NFC", "".join(raw_values))

    clusters.sort(key=lambda cluster: float(cluster["x0"]), reverse=True)
    result: list[str] = []
    for index, cluster in enumerate(clusters):
        if index:
            previous = clusters[index - 1]
            if float(previous["x0"]) - float(cluster["x1"]) > 2.2:
                result.append(" ")
        result.append(str(cluster["text"]))
    return unicodedata.normalize("NFC", "".join(result))


def readable_block(raw_block: dict) -> str:
    """Rebuild a PDF text block without crossing its geometric boundary."""
    grouped: list[dict] = []
    for line in raw_block.get("lines", []):
        baseline = float(line.get("bbox", (0.0, 0.0, 0.0, 0.0))[1])
        if grouped and abs(float(grouped[-1]["baseline"]) - baseline) <= 1.0:
            grouped[-1]["spans"].extend(line.get("spans", []))
        else:
            grouped.append({"baseline": baseline, "spans": list(line.get("spans", []))})
    values = [readable_line(line).strip() for line in grouped]
    return "\n".join(value for value in values if value).strip()


@lru_cache(maxsize=128)
def readable_pdf_blocks(source_path: str, pdf_page: int) -> tuple[tuple[tuple[float, float, float, float], str], ...]:
    """Return logical text blocks in physical top-to-bottom order.

    This is a presentation projection from the immutable source PDF. It does
    not replace PostgreSQL authority or write the reconstructed text back.
    """
    import fitz

    with fitz.open(source_path) as document:
        page = document[pdf_page - 1]
        blocks = []
        for raw_block in page.get_text("rawdict").get("blocks", []):
            bbox = tuple(float(item) for item in raw_block.get("bbox", (0.0, 0.0, 0.0, 0.0)))
            value = readable_block(raw_block)
            if value:
                blocks.append((bbox, value))
    return tuple(sorted(blocks, key=lambda item: (item[0][1], item[0][0])))


def readable_pdf_block(source_path: str, pdf_page: int, bbox: list[float] | tuple[float, ...] | None) -> str | None:
    """Resolve the closest immutable PDF block to a persisted block bbox."""
    blocks = readable_pdf_blocks(source_path, pdf_page)
    if not blocks:
        return None
    if not bbox or len(bbox) < 4:
        return blocks[0][1]
    target = tuple(float(item) for item in bbox[:4])
    _, value = min(
        blocks,
        key=lambda item: sum(abs(item[0][index] - target[index]) for index in range(4)),
    )
    return value


def readable_page(raw_page: dict) -> str:
    """Rebuild a rawdict page while preserving logical line order."""
    lines: list[str] = []
    for block in raw_page.get("blocks", []):
        value = readable_block(block)
        if value:
            lines.append(value)
    return "\n".join(lines).strip()
