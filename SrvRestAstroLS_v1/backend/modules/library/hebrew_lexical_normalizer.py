"""Hebrew lexical normalizer for retrieval and gate support.

This module provides safe, reversible lexical normalization for Hebrew text
used in retrieval (FTS, BM25, lexical gates). It never modifies the canonical
text stored in PostgreSQL.

NOT a morphological analyzer. NOT shoresh/lemmas. NOT stemming.
"""

from __future__ import annotations

import re
import unicodedata

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
        result = unicodedata.normalize("NFC", result)

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
