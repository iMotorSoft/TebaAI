"""Deterministic editorial provenance for investigative evidence.

The classifier is deliberately conservative: layout and literal reference
markers may confirm a layer, while ambiguous material remains ``unknown``.
It never rewrites canonical text and never asks a model to assign authority.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

from modules.library.hebrew_lexical_normalizer import normalize_hebrew_search

SourceLayer = Literal[
    "rebbe_lesson_text",
    "biblical_quote_in_lesson",
    "rabbinic_quote_in_lesson",
    "editorial_translation",
    "editorial_commentary",
    "editorial_note",
    "footnote",
    "source_reference",
    "section_heading",
    "page_heading",
    "introduction",
    "unknown",
]
SourceLayerConfidence = Literal["high", "medium", "low"]

SOURCE_LAYERS: frozenset[str] = frozenset(SourceLayer.__args__)
SOURCE_LAYER_PRIORITY: dict[str, int] = {
    "rebbe_lesson_text": 0,
    "biblical_quote_in_lesson": 1,
    "rabbinic_quote_in_lesson": 2,
    "editorial_translation": 3,
    "editorial_commentary": 4,
    "editorial_note": 5,
    "footnote": 6,
    "source_reference": 7,
    "section_heading": 8,
    "page_heading": 9,
    "introduction": 10,
    "unknown": 11,
}

_HEBREW = re.compile(r"[\u0590-\u05ff]")
_HEBREW_TOKEN = re.compile(r"[\u0590-\u05ff\ufb1d-\ufb4f]+")
_BIBLICAL_HEBREW = re.compile(
    r"(?:בראשית|שמות|ויקרא|במדבר|דברים|יהושע|שופטים|שמואל|מלכים|ישעיה|ירמיה|"
    r"יחזקאל|הושע|יואל|עמוס|עובדיה|יונה|מיכה|נחום|חבקוק|צפניה|חגי|זכריה|מלאכי|"
    r"תהלים|משלי|איוב|שיר\s+השירים|רות|איכה|קהלת|אסתר|דניאל|עזרא|נחמיה|דברי\s+הימים)"
)
_RABBINIC_HEBREW = re.compile(
    r"(?:זוהר|תיקוני?\s+זוהר|תיקון|ברכות|שבת|פסחים|עירובין|סוכה|סוטה|סנהדרין|"
    r"מדרש|תלמוד|גמרא|משנה)"
)
_NUMBERED_NOTE = re.compile(r"^\s*\d{1,3}[.)]\s+")
_PAGE_HEADING = re.compile(r"(?im)^\s*\d{1,4}\s*$.*^\s*LIKUTEY\s+MOHAR", re.S)
_SECTION_HEADING = re.compile(r"(?i)(?:LIKUTEY\s+MOHAR|LECCI[ÓO]N|TOR[ÁA])[^\n]{0,80}#?\d")


@dataclass(frozen=True)
class LayerDecision:
    source_layer: SourceLayer
    confidence: SourceLayerConfidence
    rationale: str


@dataclass(frozen=True)
class LiteralContext:
    match_text: str
    sentence_text: str
    paragraph_text: str
    context_before: str
    context_after: str
    match_kind: Literal["exact_phrase", "normalized", "no_niqqud"]


def _compatibility_nfc(value: str) -> str:
    return unicodedata.normalize("NFC", unicodedata.normalize("NFKC", value))


def _tokens(value: str) -> list[tuple[str, str]]:
    return [
        (match.group(), normalize_hebrew_search(_compatibility_nfc(match.group())))
        for match in _HEBREW_TOKEN.finditer(value)
        if normalize_hebrew_search(_compatibility_nfc(match.group()))
    ]


def _bounded_distance(left: str, right: str, maximum: int = 1) -> int:
    if abs(len(left) - len(right)) > maximum:
        return maximum + 1
    previous = list(range(len(right) + 1))
    for row, lchar in enumerate(left, 1):
        current = [row]
        row_minimum = row
        for column, rchar in enumerate(right, 1):
            value = min(
                previous[column] + 1,
                current[column - 1] + 1,
                previous[column - 1] + (lchar != rchar),
            )
            current.append(value)
            row_minimum = min(row_minimum, value)
        if row_minimum > maximum:
            return maximum + 1
        previous = current
    return previous[-1]


def match_hebrew_literal(text: str, query: str) -> tuple[str, Literal["exact_phrase", "normalized", "no_niqqud"]] | None:
    """Find a literal phrase, allowing one guarded glyph/word-form mismatch."""
    text_tokens = _tokens(text)
    query_tokens = [item[1] for item in _tokens(query)]
    if not text_tokens or not query_tokens:
        return None
    width = len(query_tokens)
    for offset in range(0, len(text_tokens) - width + 1):
        window = text_tokens[offset:offset + width]
        normalized = [item[1] for item in window]
        if normalized == query_tokens:
            raw = " ".join(item[0] for item in window)
            exact = _compatibility_nfc(query) in _compatibility_nfc(text)
            pointed = any(unicodedata.combining(char) for char in unicodedata.normalize("NFD", query))
            return raw, "exact_phrase" if exact else ("normalized" if pointed else "no_niqqud")
    if width >= 4 and sum(len(item) for item in query_tokens) >= 8:
        for offset in range(0, len(text_tokens) - width + 1):
            window = text_tokens[offset:offset + width]
            distance = sum(
                _bounded_distance(left, right)
                for left, right in zip(query_tokens, (item[1] for item in window))
            )
            if distance <= 1:
                return " ".join(item[0] for item in window), "normalized"
    return None


def literal_context(text: str, query: str) -> LiteralContext | None:
    """Return sentence, paragraph and adjacent context without crossing blocks."""
    lines = [line.strip() for line in _compatibility_nfc(text).splitlines() if line.strip()]
    for index, line in enumerate(lines):
        matched = match_hebrew_literal(line, query)
        if not matched:
            continue
        match_text, match_kind = matched
        end = index
        while end + 1 < len(lines):
            end += 1
            if lines[end].rstrip().endswith((".", "׃")):
                break
        return LiteralContext(
            match_text=match_text,
            sentence_text=line,
            paragraph_text="\n".join(lines[index:end + 1]),
            context_before="\n".join(lines[max(0, index - 2):index]),
            context_after="\n".join(lines[end + 1:end + 3]),
            match_kind=match_kind,
        )
    return None


def classify_source_layer(
    text: str,
    *,
    zone_type: str | None,
    zone_role: str | None = None,
    document_part: str | None = None,
    matched_text: str | None = None,
) -> LayerDecision:
    """Classify a persisted zone from explicit script/layout markers."""
    value = _compatibility_nfc(text).strip()
    if zone_type in {"header", "page_number"} or _PAGE_HEADING.search(value):
        return LayerDecision("page_heading", "high", "validated_page_header_zone")
    if zone_type == "section_heading" or (_SECTION_HEADING.search(value) and len(value) < 140):
        return LayerDecision("section_heading", "high", "literal_section_heading")
    if document_part == "front_matter":
        return LayerDecision("introduction", "medium", "front_matter_layout")
    if _HEBREW.search(value) and zone_type == "main_text_hebrew":
        match_line = next(
            (line for line in value.splitlines() if matched_text and match_hebrew_literal(line, matched_text)),
            value,
        )
        if _BIBLICAL_HEBREW.search(match_line):
            return LayerDecision("biblical_quote_in_lesson", "high", "biblical_reference_and_quoted_hebrew_in_lesson")
        if _RABBINIC_HEBREW.search(match_line):
            return LayerDecision("rabbinic_quote_in_lesson", "high", "rabbinic_reference_and_quoted_hebrew_in_lesson")
        return LayerDecision("rebbe_lesson_text", "high", "validated_primary_hebrew_zone")
    if _NUMBERED_NOTE.search(value):
        return LayerDecision("footnote", "high", "numbered_editorial_note_marker")
    if zone_type == "note_or_source_candidate":
        return LayerDecision("editorial_note", "medium", "validated_satellite_note_zone")
    if zone_type == "main_text_spanish" and zone_role == "primary":
        return LayerDecision("editorial_translation", "medium", "primary_spanish_parallel_edition_zone")
    if len(value) < 180 and re.fullmatch(r"[\s\S]*\([^)]*(?:\d|[א-ת])[^)]*\)[\s\W]*", value):
        return LayerDecision("source_reference", "medium", "standalone_parenthetical_reference")
    if zone_role == "satellite" and not _HEBREW.search(value):
        return LayerDecision("editorial_commentary", "medium", "secondary_explanatory_zone")
    return LayerDecision("unknown", "low", "insufficient_structural_evidence")


def source_layer_priority(layer: str) -> int:
    return SOURCE_LAYER_PRIORITY.get(layer, SOURCE_LAYER_PRIORITY["unknown"])
