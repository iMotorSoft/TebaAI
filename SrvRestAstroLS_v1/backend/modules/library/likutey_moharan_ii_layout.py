"""Deterministic layout profile for the Spanish BRI LM II edition."""
from __future__ import annotations

import re
from dataclasses import dataclass

HEBREW_RE = re.compile(r"[\u0590-\u05ff]")
LESSON_RE = re.compile(r"(?:MOHAR[ÁA]N\s*#|סימן\s*)(\d+)(?::(\d+))?", re.I)

PROFILE_NAME = "likutey_moharan_ii_spanish_bri_layout_v1"
FOOTNOTE_Y = 470.0
HEADER_Y = 205.0

@dataclass(frozen=True)
class LayoutPiece:
    kind: str
    text: str
    confidence: float

def hebrew_chars(text: str) -> int:
    return len(HEBREW_RE.findall(text))

def classify_page(blocks: list[tuple[float, float, float, float, str]], pdf_page: int) -> list[LayoutPiece]:
    """Classify only geometry+script evidence; ambiguous body remains unknown."""
    pieces: list[LayoutPiece] = []
    body: list[str] = []
    notes: list[str] = []
    headers: list[str] = []
    for _x0, y0, _x1, _y1, text in blocks:
        text = text.strip()
        if not text:
            continue
        if y0 < HEADER_Y and ("LIKUTEY MOHAR" in text.upper() or "סימן" in text or re.fullmatch(r"\d+", text)):
            headers.append(text)
        elif y0 >= FOOTNOTE_Y:
            notes.append(text)
        else:
            body.append(text)
    if headers:
        pieces.append(LayoutPiece("page_header", "\n".join(headers), 0.99))
    body_text = "\n".join(body)
    if body_text:
        hebrew = hebrew_chars(body_text)
        if hebrew >= 100:
            pieces.append(LayoutPiece("hebrew_main_text", body_text, 0.98))
        elif hebrew < 100 and pdf_page >= 13:
            pieces.append(LayoutPiece("spanish_translation", body_text, 0.95))
        else:
            pieces.append(LayoutPiece("unknown", body_text, 0.30))
    if notes:
        note_text = "\n".join(notes)
        # Numbered notes have a deterministic starting marker; do not promote otherwise.
        kind = "numbered_footnote" if re.match(r"\d+\.\s", note_text) else "unknown"
        pieces.append(LayoutPiece(kind, note_text, 0.97 if kind != "unknown" else 0.25))
    return pieces

def lesson_ref(text: str) -> tuple[int, int] | None:
    match = LESSON_RE.search(text)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2) or 1)
