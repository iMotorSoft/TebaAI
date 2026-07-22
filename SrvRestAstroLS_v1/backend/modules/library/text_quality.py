"""Deterministic text quality analysis and evidence snippet sanitization.

This module is the single source for detecting corruption and producing
safe display snippets. It never rewrites canonical text in PostgreSQL,
never invents content, and never classifies valid Hebrew as mojibake.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Literal


C0_CONTROL = frozenset(chr(c) for c in range(0, 0x20) if c not in {0x09, 0x0A, 0x0D})
C1_CONTROL = frozenset(chr(c) for c in range(0x80, 0xA0))
DEL_CHAR = frozenset({chr(0x7F)})
ALL_CONTROL = C0_CONTROL | C1_CONTROL | DEL_CHAR
PDF_ARTIFACT_PATTERNS: list[re.Pattern] = [
    re.compile(r"<#>?"),
    re.compile(r"\\x[0-9a-fA-F]{2}"),
    re.compile(r"■"),
    re.compile(r"●"),
    re.compile(r"►"),
    re.compile(r"↕"),
    re.compile("\ufffd"),
]
CONTROL_CHAR_CODEPOINTS = ALL_CONTROL

HEBREW_RANGE = re.compile(r"[\u0590-\u05ff\uFB1D-\uFB4F]")
LATIN_BASIC = re.compile(r"[A-Za-z\u00C0-\u00FF\u0100-\u017F\u0300-\u036F]")

BIDI_CHARS = frozenset("\u200E\u200F\u202A\u202B\u202C\u202D\u202E\u2066\u2067\u2068\u2069")


def analyze_text_quality(text: str) -> dict:
    """Return a deterministic quality report for the given text."""
    control_chars = [c for c in text if c in CONTROL_CHAR_CODEPOINTS]
    has_mojibake = _detect_mojibake(text)
    pdf_artifacts = [pat.findall(text) for pat in PDF_ARTIFACT_PATTERNS]
    pdf_artifact_count = sum(len(matches) for matches in pdf_artifacts)
    total = len(text)
    printable = sum(1 for c in text if c.isprintable() and c not in CONTROL_CHAR_CODEPOINTS)
    printable_ratio = printable / total if total else 1.0
    has_bidi_control = any(c in BIDI_CHARS for c in text)
    # Find leading corruption span
    first_clean = _first_clean_position(text)
    return {
        "has_control_chars": bool(control_chars),
        "control_char_count": len(control_chars),
        "control_char_positions": [text.index(c) for c in control_chars[:10]] if control_chars else [],
        "has_mojibake": has_mojibake,
        "has_pdf_artifacts": pdf_artifact_count > 0,
        "pdf_artifact_count": pdf_artifact_count,
        "printable_ratio": round(printable_ratio, 4),
        "leading_corruption_span": [0, first_clean] if first_clean > 0 else None,
        "has_bidi_control_chars": has_bidi_control,
        "reason_codes": _reason_codes(has_mojibake, bool(control_chars), pdf_artifact_count > 0, first_clean, has_bidi_control),
    }


def _reason_codes(
    has_mojibake: bool,
    has_control: bool,
    has_pdf: bool,
    first_clean: int,
    has_bidi_control: bool,
) -> list[str]:
    codes: list[str] = []
    if has_mojibake:
        codes.append("suspected_mojibake")
    if has_control:
        codes.append("c0_and_c1_control_chars")
    if has_pdf:
        codes.append("pdf_marker_artifact")
    if first_clean > 0:
        codes.append("leading_corruption_trimmed")
    if has_bidi_control:
        codes.append("bidi_control_removed")
    return codes


def _detect_mojibake(text: str) -> bool:
    """Heuristic for Latin-1 misinterpretation of UTF-8 Hebrew bytes.

    Checks for Windows-1252 bytes that would represent Hebrew codepoints
    if the original encoding were UTF-8. Considers C1 range chars that
    co-occur with Spanish text, indicating a mixed encoding page.
    """
    if "\ufffd" in text or re.search(r"(?:Ã.|Â.|â€|ðŸ)", text):
        return True
    c1_count = sum(1 for c in text if c in C1_CONTROL)
    hebrew_count = len(HEBREW_RANGE.findall(text))
    if c1_count >= 3:
        # C1 chars near clean Spanish text strongly suggest mojibake
        # Only flag if there's also minimal Hebrew presence (artifact)
        if hebrew_count < c1_count * 2:
            return True
    # Check for high-byte Windows-1252 chars in positions 0x80-0x9F range
    # that appear adjacent to printable ASCII
    suspicious = sum(
        1 for c in text
        if 0x80 <= ord(c) <= 0x9F
    )
    if suspicious >= 5 and hebrew_count < 20:
        return True
    return False


def _first_clean_position(text: str) -> int:
    """Return the first position where clean printable text begins.

    Scans line by line (preserving original line boundaries), skipping
    lines that consist only of:
    - Short Hebrew fragments (page headers)
    - Single-character remnants or non-word tokens
    - Numbers without real word context
    - Lines with no real Latin word (>=4 printable Latin chars)

    Returns the byte offset of the first line that contains valid text.
    """
    lines = text.splitlines(keepends=True)
    cumulative = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            cumulative += len(line)
            continue
        if len(stripped) < 3:
            cumulative += len(line)
            continue
        # Count content categories
        hebrew_chars = HEBREW_RANGE.findall(stripped)
        latin_letters = re.findall(r"[A-Za-z\u00C0-\u00FF\u0100-\u017F]", stripped)
        digits = re.findall(r"[0-9]", stripped)
        other = len(stripped) - len(hebrew_chars) - len(latin_letters) - len(digits)

        # Extract multi-letter Latin tokens (3+ consecutive Latin letters)
        latin_tokens = re.findall(r"[A-Za-z\u00C0-\u00FF]{3,}", stripped)
        long_latin_tokens = [t for t in latin_tokens if len(t) >= 5]

        # Clean line has either:
        # A) At least one long Latin word (5+ chars)
        # B) At least 2 Latin tokens of 3+ chars AND fewer than 50% Hebrew
        # C) At least 1 Latin token AND 70%+ Latin letters AND Hebrew < 10%
        has_long_word = bool(long_latin_tokens)
        has_two_tokens = len(latin_tokens) >= 2
        latin_ratio = len(latin_letters) / len(stripped) if stripped else 0
        he_ratio = len(hebrew_chars) / len(stripped) if stripped else 0

        is_clean = (
            has_long_word
            or (has_two_tokens and he_ratio < 0.5)
            or (len(latin_tokens) >= 1 and latin_ratio >= 0.5 and he_ratio < 0.2)
        )
        if is_clean:
            return cumulative
        cumulative += len(line)
    return 0





def sanitize_evidence_snippet(
    raw_text: str,
    *,
    canonical_text: str | None = None,
    matched_phrase: str | None = None,
    max_length: int = 1200,
    context_lines: int = 2,
) -> dict:
    """Produce a display-safe snippet while preserving raw text for audit.

    Returns a dict with:
      - raw_snippet: the original text (unchanged)
      - display_snippet: sanitized, match-centered, corruption-free text
      - sanitization_applied: bool
      - sanitization_reason_codes: list[str]
      - matched_phrase_preserved: bool
      - match_offset: int | None
    """
    analysis = analyze_text_quality(raw_text)
    sanitized = _clean_text_for_display(raw_text)
    reason_codes = list(analysis.get("reason_codes", []))

    # Determine starting position: skip leading corruption
    first_clean = _first_clean_position(sanitized)
    clean_text = sanitized[first_clean:] if first_clean > 0 else sanitized

    # Build match-centered window
    match_offset = None
    if matched_phrase:
        match_lower = matched_phrase.lower()
        clean_lower = clean_text.lower()
        pos = clean_lower.find(match_lower)
        if pos == -1:
            pos = clean_lower.find(matched_phrase.lower().strip())
        if pos >= 0:
            match_offset = pos
        else:
            # Try normalized search
            norm_phrase = _normalize_for_search(matched_phrase)
            norm_text = _normalize_for_search(clean_text)
            pos = norm_text.find(norm_phrase)
            if pos >= 0:
                match_offset = _approximate_offset(norm_text, norm_phrase, clean_text)

    if match_offset is not None:
        display = _match_centered_window(clean_text, match_offset, len(matched_phrase or ""), max_length, context_lines)
    else:
        # Fall back to truncation without match centering
        display = clean_text[:max_length].rstrip()
        if len(clean_text) > max_length:
            display += "…"

    matched_preserved = matched_phrase is not None and matched_phrase.lower() in display.lower()

    if not matched_preserved and matched_phrase and clean_text:
        # Last resort: find the line containing the phrase
        for line in clean_text.splitlines():
            if matched_phrase.lower() in line.lower():
                display = line.strip()
                matched_preserved = True
                break

    if first_clean > 0 and "leading_corruption_trimmed" not in reason_codes:
        reason_codes.append("leading_corruption_trimmed")

    return {
        "raw_snippet": raw_text,
        "display_snippet": display,
        "sanitization_applied": bool(reason_codes),
        "sanitization_reason_codes": reason_codes,
        "matched_phrase_preserved": matched_preserved,
        "match_offset": match_offset,
    }


def _clean_text_for_display(text: str) -> str:
    """Remove control characters and PDF artifacts for display."""
    result = []
    for char in text:
        if char in ALL_CONTROL or char in BIDI_CHARS:
            result.append(" ")
        else:
            result.append(char)
    cleaned = "".join(result)
    for pattern in PDF_ARTIFACT_PATTERNS:
        cleaned = pattern.sub(" ", cleaned)
    cleaned = re.sub(r" {2,}", " ", cleaned)
    return cleaned.strip()


def _match_centered_window(
    text: str,
    match_start: int,
    match_length: int,
    max_length: int,
    context_lines: int = 2,
) -> str:
    """Build a window around the match position with sentence context."""
    lines = text.splitlines(keepends=True)
    # Find which line contains the match
    char_offset = 0
    match_line_idx = None
    match_line_start = 0
    for idx, line in enumerate(lines):
        line_len = len(line)
        if char_offset <= match_start < char_offset + line_len:
            match_line_idx = idx
            match_line_start = char_offset
            break
        char_offset += line_len

    if match_line_idx is None:
        if len(text) <= max_length:
            return text
        return text[:max_length].rsplit(" ", 1)[0] + "…"

    # Window around the matching line
    start_line = max(0, match_line_idx - context_lines)
    end_line = min(len(lines), match_line_idx + context_lines + 1)

    # Try to extend to sentence boundaries
    snippet = "".join(lines[start_line:end_line])
    if len(snippet) > max_length:
        # Try smaller window
        start_line = max(0, match_line_idx - 1)
        end_line = min(len(lines), match_line_idx + 2)
        snippet = "".join(lines[start_line:end_line])

    result = snippet.strip()
    if len(result) > max_length:
        local_match = max(0, match_start - match_line_start)
        start = max(0, local_match - max_length // 2)
        end = min(len(result), start + max_length)
        start = max(0, end - max_length)
        result = result[start:end].strip()
        if start > 0:
            result = "…" + result
        if end < len(snippet.strip()):
            result += "…"
    if start_line > 0:
        result = "…" + result
    if end_line < len(lines) and result.endswith("\n"):
        result = result.rstrip("\n")
    if end_line < len(lines):
        result = result + "…"

    return result


def _normalize_for_search(text: str) -> str:
    """NFKC normalize and lowercase for searching."""
    return unicodedata.normalize("NFKC", text).lower().strip()


def _approximate_offset(norm_text: str, norm_phrase: str, original_text: str) -> int:
    """Find the approximate offset of a normalized phrase in original text."""
    idx = norm_text.find(norm_phrase)
    if idx < 0:
        return 0
    # Walk through original text to find approximate position
    count = 0
    for pos, char in enumerate(original_text):
        if count >= idx:
            return pos
        unfolded = unicodedata.normalize("NFKC", char)
        count += len(unfolded)
    return 0


def singular_plural(count: int, singular: str, plural: str | None = None) -> str:
    """Return the correct form for the count."""
    if plural is None:
        plural = singular + "s"
    if count == 1:
        return f"1 {singular}"
    return f"{count} {plural}"


def build_summary(primary: int, contextual: int, additional: int) -> str:
    """Build a grammatically correct summary string."""
    parts = [
        singular_plural(primary, "evidencia principal", "evidencias principales"),
        singular_plural(contextual, "relación contextual", "relaciones contextuales"),
        singular_plural(additional, "coincidencia literal adicional", "coincidencias literales adicionales"),
    ]
    return " · ".join(parts)
