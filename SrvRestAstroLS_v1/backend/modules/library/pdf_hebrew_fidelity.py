"""Source-backed Hebrew boundary repairs for PyMuPDF4LLM Markdown.

Never infer word boundaries from Hebrew strings alone. Repairs require raw
glyph metadata and an exact (whitespace-tolerant) source match in Markdown.
"""

from __future__ import annotations

import re
import unicodedata


def _hebrew(char: str) -> bool:
    return "\u05d0" <= char <= "\u05ea" or "\ufb1d" <= char <= "\ufb4f"


def _mark(char: str) -> bool:
    return unicodedata.category(char).startswith("M")


def repair_markdown(markdown: str, raw: dict) -> tuple[str, list[dict]]:
    """Repair only boundaries demonstrated by horizontal source glyphs.

    Remove synthetic spaces after Hebrew marks when the surrounding base
    glyphs touch/overlap. Separate adjacent numeric equation cells only when
    a large physical gutter divides their Hebrew letter and next number.
    Real spaces, non-Hebrew text and unproven boundaries are preserved.
    """
    changes: list[dict] = []
    for block in raw.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            if tuple(line.get("dir", (1, 0))) != (1, 0):
                continue
            chars = [dict(char, size=span["size"]) for span in line["spans"] for char in span["chars"]]
            source = "".join(char["c"] for char in chars).strip()
            removed: set[int] = set()
            gutters: set[int] = set()
            for index, char in enumerate(chars):
                if char["c"] == " " and char.get("synthetic") and index and _mark(chars[index - 1]["c"]):
                    left = next((c for c in reversed(chars[:index]) if not _mark(c["c"])), None)
                    right = next((c for c in chars[index + 1:] if not _mark(c["c"])), None)
                    if left and right and _hebrew(left["c"]) and _hebrew(right["c"]):
                        gap = max(left["bbox"][0], right["bbox"][0]) - min(left["bbox"][2], right["bbox"][2])
                        if gap <= char["size"] * 0.03:
                            removed.add(index)
            # Require an entire line of >=2 numeric/Hebrew equation cells,
            # with a physical gutter at EVERY cell boundary, including those
            # where the PDF already supplies a real space.
            cell = r"[0-9]+\s*=\s*[\u05d0-\u05ea](?:\s*,\s*[\u05d0-\u05ea])?"
            full_source = "".join(c["c"] for c in chars)
            cells = list(re.finditer(cell, full_source))
            if len(cells) >= 2 and not re.sub(cell, "", full_source).strip():
                boundaries = [(previous.end() - 1, following.start()) for previous, following in zip(cells, cells[1:])]
                if all(chars[right]["bbox"][0] - chars[left]["bbox"][2] >= chars[right]["size"] for left, right in boundaries):
                    gutters = {right for _, right in boundaries}
            if not removed and not gutters:
                continue
            corrected = "".join((" ; " if i in gutters else "") + c["c"] for i, c in enumerate(chars) if i not in removed).strip()
            if gutters:
                # Each demonstrated cell gets an explicit delimiter, including
                # cells whose PDF already carries a space across the gutter.
                corrected = " ; ".join(re.sub(r"\s+", " ", c).strip() for c in re.findall(cell, corrected)) + "\n\n"
            # Whitespace may be folded by the Markdown converter. Permit extra
            # whitespace only at source cell gutters; retain all other chars.
            start = next(i for i, c in enumerate(chars) if not c["c"].isspace())
            end = max(i for i, c in enumerate(chars) if not c["c"].isspace()) + 1
            pattern = "".join(
                (r"\s*" if i in gutters and not chars[i - 1]["c"].isspace() else "")
                + (r"\s*" if c["c"].isspace() else re.escape(c["c"]))
                for i, c in enumerate(chars) if start <= i < end
            )
            matches = list(re.finditer(pattern, markdown))
            # Duplicate textual matches have no reliable page-local anchor.
            # Leave them unchanged rather than applying geometry to a run
            # whose provenance cannot be determined.
            if len(matches) != 1 or matches[0].group() == corrected:
                continue
            match = matches[0]
            markdown = markdown[:match.start()] + corrected + markdown[match.end():]
            changes.append({
                "source": source, "corrected": corrected,
                "synthetic_spaces_removed": len(removed),
                "cell_gutters": len(gutters), "matches": 1,
            })
    return markdown, changes


def document_header_info(document):
    """Reuse legacy header analysis only when the converter exposes and uses it."""
    import pymupdf4llm

    # Layout ignores hdr_info; scanning every page for legacy font-size
    # headers would add an unused full-document pass (and layout inference).
    if getattr(pymupdf4llm, "_use_layout", False):
        return None
    identify = getattr(pymupdf4llm, "IdentifyHeaders", None)
    return identify(document) if identify is not None else None


def page_markdown(document, page_index: int, *, hdr_info=None) -> tuple[str, list[dict]]:
    """Keep PyMuPDF4LLM as canonical extractor, then repair proven boundaries."""
    import pymupdf4llm

    options = {"hdr_info": hdr_info} if hdr_info is not None else {}
    markdown = pymupdf4llm.to_markdown(document, pages=[page_index], **options)
    raw = document[page_index].get_text("rawdict")
    return repair_markdown(markdown, raw)
