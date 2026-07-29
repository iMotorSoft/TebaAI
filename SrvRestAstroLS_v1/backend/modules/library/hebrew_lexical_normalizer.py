"""Hebrew lexical normalizer for retrieval and gate support.

This module provides safe, reversible lexical normalization for Hebrew text
used in retrieval (FTS, BM25, lexical gates). It never modifies the canonical
text stored in PostgreSQL.

NOT a morphological analyzer. NOT shoresh/lemmas. NOT stemming.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Hebrew Unicode blocks
HEBREW_BLOCK = range(0x0590, 0x05FF + 1)

# Niqqud (vowel marks) — safe to remove for lexical matching
NIQQUD = set(range(0x05B0, 0x05BD)) | {0x05C1, 0x05C2, 0x05C7}
# Exclude 0x05BD (meteg) from niqqud stripping — treated separately

# Taamim (cantillation marks) — safe to remove for lexical matching
TAAMIM = set(range(0x0591, 0x05AF + 1))

# Meteg (U+05BD) — secondary stress marker, removed for lexical matching
METEG = {0x05BD}

# Maqaf (U+05BE) — Hebrew hyphen
MAQAF = "\u05be"

# Geresh (U+05F3) and Gershayim (U+05F4)
GERESH = "\u05f3"
GERSHAYIM = "\u05f4"

# Unicode directional and invisible marks — removed for retrieval
INVISIBLE_MARKS = set(range(0x200B, 0x200F + 1)) | set(range(0x2028, 0x202F + 1)) | {0xFEFF, 0x2060, 0x2061, 0x2062, 0x2063, 0x2064}


_HEB_CHAR = re.compile(r"[\u0590-\u05ff]")
_HEBREW_LETTER = re.compile(r"[\u05d0-\u05ea]")
_HEBREW_EDGE_INSTRUCTION = re.compile(
    r"^(?:(?:איפה|היכן)(?:\s+מופיע(?:ה)?)?|מצא)\s+(?:(?:הפסוק|הביטוי|המילים)\s+)?|"
    r"\s+(?:(?:איפה|היכן)(?:\s+מופיע(?:ה)?)?|מצא)$"
)
_INSTRUCTION_LANGUAGE = (
    ("es", re.compile(r"(?i)\b(?:d[oó]nde|buscar|p[aá]gina|encuentra|aparece)\b")),
    ("en", re.compile(r"(?i)\b(?:where|find|page|appear)\b")),
)


@dataclass(frozen=True)
class HebrewLiteralQuery:
    """Lossless analysis of a Hebrew literal embedded in a user question."""

    literal_raw: str
    instruction: str
    instruction_language: str | None
    graphemes: tuple[str, ...]
    compact_letters: str
    literal_reconstructed: str
    literal_search_normalized: str
    pdf_glyph_spacing_detected: bool
    candidates: tuple[str, ...]


@dataclass(frozen=True)
class HebrewSearchNormalization:
    """Bounded search representations without mutating the source text."""

    original: str
    nfc: str
    compacted_with_marks: str
    without_cantillation: str
    without_niqqud: str
    tokens: tuple[str, ...]
    compact_letters: str
    artificial_spacing_detected: bool
    rtl_controls_removed: bool
    approximate_variants: tuple[str, ...]


def has_hebrew(text: str) -> bool:
    """Check if text contains any Hebrew character."""
    return bool(_HEB_CHAR.search(text))


def strip_niqqud(text: str) -> str:
    """Remove Hebrew niqqud (vowel marks)."""
    return "".join(c for c in text if ord(c) not in NIQQUD)


def strip_taamim(text: str) -> str:
    """Remove Hebrew taamim (cantillation marks)."""
    return "".join(c for c in text if ord(c) not in TAAMIM)


def strip_meteg(text: str) -> str:
    """Remove Hebrew meteg (secondary stress marker U+05BD)."""
    return "".join(c for c in text if ord(c) not in METEG)


def strip_hebrew_marks(text: str) -> str:
    """Remove niqqud, taamim, and meteg from Hebrew text."""
    prohibited = NIQQUD | TAAMIM | METEG
    return "".join(c for c in text if ord(c) not in prohibited)


def normalize_maqaf(text: str) -> str:
    """Normalize maqaf (Hebrew hyphen) to regular hyphen-minus."""
    return text.replace(MAQAF, "-")


def remove_invisible_marks(text: str) -> str:
    """Remove Unicode invisible/formatting characters."""
    return "".join(c for c in text if ord(c) not in INVISIBLE_MARKS)


def normalize_hebrew_lexical(
    text: str,
    *,
    do_niqqud: bool = True,
    do_taamim: bool = True,
    do_meteg: bool = True,
    do_unicode: bool = True,
    do_maqaf: bool = True,
    do_invisible: bool = True,
) -> str:
    """Normalize Hebrew text for lexical retrieval.

    Performs safe, reversible operations only. Never modifies canonical text.

    Args:
        text: Input text (may contain Hebrew, English, or mixed content).
        do_niqqud: Remove vowel marks (U+05B0-U+05BC, U+05C1-U+05C2, U+05C7).
        do_taamim: Remove cantillation marks (U+0591-U+05AF).
        do_meteg: Remove meteg (U+05BD).
        do_unicode: Apply NFC normalization.
        do_maqaf: Replace Hebrew hyphen (U+05BE) with ASCII hyphen.
        do_invisible: Remove Unicode invisible/formatting chars.

    Returns:
        Normalized string. English and non-Hebrew content is preserved.
    """
    result = text

    if do_unicode:
        # NFKC is retrieval-only and expands Hebrew presentation forms such as
        # FB31 (BET WITH DAGESH) before marks are stripped. Canonical source
        # text is never written through this function.
        result = unicodedata.normalize("NFC", unicodedata.normalize("NFKC", result))

    if do_invisible:
        result = remove_invisible_marks(result)

    if do_niqqud:
        result = strip_niqqud(result)

    if do_taamim:
        result = strip_taamim(result)

    if do_meteg:
        result = strip_meteg(result)

    if do_maqaf:
        result = normalize_maqaf(result)

    return result


def normalize_hebrew_search(text: str) -> str:
    """Return the shared Hebrew literal-search representation.

    Canonical text is never passed back through this function for storage. The
    derived form is NFC, niqqud/taamim insensitive, bidi-control free,
    punctuation tolerant, case-folded for mixed Latin text, and whitespace
    normalized. Hebrew final letters and word boundaries are preserved.
    """
    result = normalize_hebrew_lexical(text)
    result = "".join(
        " " if unicodedata.category(char)[0] in {"P", "S", "Z", "C"} else char
        for char in result
    )
    return " ".join(result.casefold().split())


def normalize_hebrew_for_search(text: str) -> HebrewSearchNormalization:
    """Build the canonical Hebrew query forms used by literal and vector search.

    The original value remains byte-for-byte available. Approximate
    segmentations are bounded and are never suitable for display as a quote.
    """
    nfc = unicodedata.normalize("NFC", unicodedata.normalize("NFKC", text))
    without_controls = remove_invisible_marks(nfc)
    analysis = extract_literal_segments(without_controls)
    literal = analysis.literal_raw if analysis else without_controls
    segmentation = next(
        (
            candidate
            for candidate in (analysis.candidates if analysis else ())
            if " " in candidate
        ),
        None,
    )
    reconstructed = (
        reconstruct_pdf_spaced_hebrew(literal, segmentation)
        if analysis and analysis.pdf_glyph_spacing_detected and segmentation
        else analysis.literal_reconstructed
        if analysis and analysis.literal_reconstructed
        else " ".join(literal.split())
    )
    without_cantillation = normalize_hebrew_lexical(
        reconstructed,
        do_niqqud=False,
        do_taamim=True,
        do_meteg=True,
    )
    without_niqqud = normalize_hebrew_search(reconstructed)
    tokens = tuple(
        token for token in without_niqqud.split() if _HEBREW_LETTER.search(token)
    )
    compact_letters = "".join(_HEBREW_LETTER.findall(without_niqqud))
    approximate = analysis.candidates if analysis else (without_niqqud,)
    return HebrewSearchNormalization(
        original=text,
        nfc=nfc,
        compacted_with_marks=reconstructed,
        without_cantillation=without_cantillation,
        without_niqqud=without_niqqud,
        tokens=tokens,
        compact_letters=compact_letters,
        artificial_spacing_detected=bool(
            analysis and analysis.pdf_glyph_spacing_detected
        ),
        rtl_controls_removed=without_controls != nfc,
        approximate_variants=tuple(dict.fromkeys(approximate))[:64],
    )


def _is_hebrew_mark(char: str) -> bool:
    return "\u0590" <= char <= "\u05cf" and unicodedata.category(char).startswith("M")


def _pointed_graphemes(value: str) -> tuple[tuple[str, ...], tuple[int, ...]]:
    """Group Hebrew letters with marks even when PDF copy inserted a space.

    The returned gaps contain the number of separator characters observed
    before each grapheme after the first. No visual-order manipulation occurs.
    """
    graphemes: list[str] = []
    gaps: list[int] = []
    pending_gap = 0
    for char in unicodedata.normalize("NFD", remove_invisible_marks(value)):
        if _HEBREW_LETTER.fullmatch(char):
            if graphemes:
                gaps.append(pending_gap)
            graphemes.append(char)
            pending_gap = 0
        elif _is_hebrew_mark(char) and graphemes:
            graphemes[-1] += char
            pending_gap = 0
        elif char.isspace() or unicodedata.category(char).startswith("Z"):
            pending_gap += 1
    return tuple(unicodedata.normalize("NFC", item) for item in graphemes), tuple(gaps)


def _segmentation_candidates(compact: str, *, limit: int = 64) -> tuple[str, ...]:
    """Return bounded, non-linguistic segmentations for corpus validation."""
    if not compact:
        return ()
    if len(compact) > 32:
        return (compact,)
    final_letters = set("ךםןףץ")
    generated: set[tuple[str, ...]] = set()

    def visit(offset: int, words: tuple[str, ...]) -> None:
        if len(generated) >= 512 or len(words) >= 7:
            return
        if offset == len(compact):
            generated.add(words)
            return
        remaining = len(compact) - offset
        for size in range(2, min(10, remaining) + 1):
            end = offset + size
            if end < len(compact) and compact[end - 1] in final_letters:
                visit(end, (*words, compact[offset:end]))
            elif end == len(compact) or compact[end - 1] not in final_letters:
                visit(end, (*words, compact[offset:end]))

    visit(0, ())

    def score(words: tuple[str, ...]) -> tuple[int, int, int, tuple[int, ...], str]:
        final_boundaries = sum(word[-1] in final_letters for word in words[:-1])
        short_penalty = sum(len(word) == 2 for word in words)
        return (-final_boundaries, abs(len(words) - 3), short_penalty, tuple(-len(word) for word in words), " ".join(words))

    values = [" ".join(words) for words in sorted(generated, key=score)]
    if compact not in values:
        values.insert(0, compact)
    return tuple(dict.fromkeys(values))[:limit]


def reconstruct_pdf_spaced_hebrew(value: str, segmentation: str | None = None) -> str:
    """Reassociate spaced marks and optionally apply corpus-verified word cuts."""
    graphemes, gaps = _pointed_graphemes(value)
    if not graphemes:
        return ""
    if segmentation:
        word_lengths = [len(_HEBREW_LETTER.findall(word)) for word in segmentation.split()]
        if sum(word_lengths) == len(graphemes):
            words: list[str] = []
            offset = 0
            for size in word_lengths:
                words.append("".join(graphemes[offset:offset + size]))
                offset += size
            return " ".join(words)
    spaced_ratio = sum(gap > 0 for gap in gaps) / max(1, len(gaps))
    if spaced_ratio >= 0.50 and len(graphemes) >= 4:
        return "".join(graphemes)
    return "".join(
        grapheme if index == 0 or not gaps[index - 1] else " " + grapheme
        for index, grapheme in enumerate(graphemes)
    )


def extract_literal_segments(question: str) -> HebrewLiteralQuery | None:
    """Separate a Hebrew literal from surrounding localization instructions.

    Hebrew extraction is script based. Small edge vocabularies only identify
    the instruction; they never define or translate the literal itself.
    """
    positions = [index for index, char in enumerate(question) if _HEB_CHAR.fullmatch(char)]
    if not positions:
        return None
    start, end = positions[0], positions[-1] + 1
    literal_raw = question[start:end].strip()
    outside = " ".join(part.strip() for part in (question[:start], question[end:]) if part.strip())
    edge_match = _HEBREW_EDGE_INSTRUCTION.search(literal_raw)
    hebrew_instruction = ""
    if edge_match:
        hebrew_instruction = edge_match.group().strip()
        literal_raw = _HEBREW_EDGE_INSTRUCTION.sub("", literal_raw, count=1).strip()
    internal_non_hebrew = " ".join(
        token for token in literal_raw.split()
        if not any(_HEB_CHAR.fullmatch(char) for char in token)
    )
    if internal_non_hebrew:
        literal_raw = " ".join(
            token for token in literal_raw.split()
            if any(_HEB_CHAR.fullmatch(char) for char in token)
        )
    instruction = " ".join(filter(None, (outside, internal_non_hebrew, hebrew_instruction))).strip()
    instruction_language = "he" if hebrew_instruction else next(
        (lang for lang, pattern in _INSTRUCTION_LANGUAGE if pattern.search(instruction)),
        "unknown" if instruction else None,
    )
    graphemes, gaps = _pointed_graphemes(literal_raw)
    compact = "".join(grapheme[0] for grapheme in graphemes)
    reconstructed = reconstruct_pdf_spaced_hebrew(literal_raw)
    normalized = normalize_hebrew_search(reconstructed)
    spaced_ratio = sum(gap > 0 for gap in gaps) / max(1, len(gaps))
    artificial_spacing = spaced_ratio >= 0.50 and len(graphemes) >= 4
    candidates = list(_segmentation_candidates(compact)) if artificial_spacing else [normalized]
    if normalized and normalized not in candidates:
        candidates.insert(0, normalized)
    return HebrewLiteralQuery(
        literal_raw=literal_raw,
        instruction=instruction,
        instruction_language=instruction_language,
        graphemes=graphemes,
        compact_letters=compact,
        literal_reconstructed=reconstructed,
        literal_search_normalized=normalized,
        pdf_glyph_spacing_detected=artificial_spacing,
        candidates=tuple(candidates[:64]),
    )
