"""Decoder for TeX Hebrew (SI-960) encoded text from Tiqwah fonts.

This module converts text extracted from PDFs using TeX Hebrew fonts
(Tiqwah family, tq*) into proper Unicode Hebrew.

The font encoding maps Hebrew characters to Latin character positions:
  - Lowercase a-z: Hebrew consonants (and some suffix letters)
  - Uppercase A-Z: Final forms and dagesh variants
  - U+2019 / U+2018: Alef and ayin (via Adobe glyph name mapping)
  - U+0022 ("): Ayin
  - Punctuation and digits: Kept as-is

For 8-bit characters (Latin-1 Supplement and Latin Extended-A),
the HE8 encoding is used where possible.
"""

SI960_TO_HEBREW: dict[str, str] = {
    "b": "\u05d1",  # bet
    "g": "\u05d2",  # gimel
    "d": "\u05d3",  # dalet
    "h": "\u05d4",  # he
    "w": "\u05d5",  # vav
    "z": "\u05d6",  # zayin
    "x": "\u05d7",  # het
    "j": "\u05d8",  # tet
    "y": "\u05d9",  # yod
    "k": "\u05db",  # kaf
    "l": "\u05dc",  # lamed
    "m": "\u05de",  # mem
    "n": "\u05e0",  # nun
    "s": "\u05e1",  # samekh
    "p": "\u05e4",  # pe
    "c": "\u05e6",  # tsadi
    "q": "\u05e7",  # qof
    "r": "\u05e8",  # resh
    "t": "\u05ea",  # tav
    "a": "\u05d0",  # alef (rare)
    "e": "\u05e2",  # ayin (variant position)
    "f": "\u05e4",  # pe (variant)
    "i": "\u05d9",  # yod (variant)
    "o": "\u05df",  # final nun
    "u": "\u05e5",  # final tsadi
    "v": "\u05e6",  # tsadi (variant)
    "#": "\u05e9",  # shin (position 35, rarely used in this font)
    "'": "\u05d0",  # alef (ASCII apostrophe, SI-960)
    '"': "\u05e2",  # ayin (ASCII double quote, SI-960)
    "C": "\u05e5",  # final tsadi
    "K": "\u05da",  # final kaf
    "M": "\u05dd",  # final mem
    "N": "\u05df",  # final nun
    "P": "\u05e3",  # final pe
    "S": "\u05e9",  # shin (primary encoding for shin)
    "T": "\u05ea\u05bc",  # tav with dagesh
    "J": "\u05d8\u05bc",  # tet with dagesh
    "B": "\u05d1\u05bc",  # bet with dagesh
    "G": "\u05d2\u05bc",  # gimel with dagesh
    "D": "\u05d3\u05bc",  # dalet with dagesh
    "H": "\u05d4\u05bc",  # he with mapiq
    "Y": "\u05d9\u05b4",  # yod with hiriq
    "Q": "\u05e7\u05bc",  # qof with dagesh
    "W": "\u05d5\u05bc",  # vav with dagesh
    "Z": "\u05e9\u05c2",  # sin (sin dot)
    "V": "\u05e9\u05c1",  # shin (shin dot)
    "I": "\u05d9\u05b7",  # yad with patah
    "O": "\u05db\u05bc",  # kaf with dagesh
    "E": "\u05d0\u05b5",  # alef with tsere
    "L": "\u05dc\u05bc",  # lamed with dagesh
    "R": "\u05e8\u05bc",  # resh with dagesh
    "U": "\u05d5\u05b9",  # vav with holam
}

# Niqqud and special marks mapped via HE8 encoding
HE8_NIQQUD: dict[str, str] = {
    "\u00c0": "\u05b0",  # À → sheva
    "\u00c1": "\u05b1",  # Á → hataf segol
    "\u00c2": "\u05b2",  # Â → hataf patah
    "\u00c3": "\u05b3",  # Ã → hataf qamats
    "\u00c4": "\u05b4",  # Ä → hiriq
    "\u00c5": "\u05b5",  # Å → tsere
    "\u00c6": "\u05b6",  # Æ → segol
    "\u00c7": "\u05b7",  # Ç → patah
    "\u00c8": "\u05b8",  # È → qamats
    "\u00c9": "\u05b9",  # É → holam
    "\u00ca": "\u05ba",  # Ê → holam haser
    "\u00cb": "\u05bb",  # Ë → qubuts
    "\u00d3": "\u05c3",  # Ó → sof pasuq
    "\u00d7": "\u05f3",  # × → geresh
    "\u00d8": "\u05f4",  # Ø → gershayim
}

# HE8 Hebrew letters at positions 224-250
HE8_LETTERS: dict[str, str] = {
    "\u00e0": "\u05d0",  # à → alef
    "\u00e1": "\u05d1",  # á → bet
    "\u00e2": "\u05e6",  # â → tsadi
    "\u00e8": "\u05d8",  # è → tet
    "\u00ea": "\u05da",  # ê → final kaf
    "\u00eb": "\u05db",  # ë → kaf
    "\u00ec": "\u05dd",  # ì → final mem
    "\u00ed": "\u05de",  # í → mem
    "\u00ee": "\u05df",  # î → final nun
    "\u00ef": "\u05e0",  # ï → nun
}

# Latin Extended-A characters — pre-composed Hebrew + diacritic
# These encode the Cantillation marks (ta'amei ha-mikra) and specific
# vowel+letter combinations from the Tiqwah font encoding.
# The mapping is best-effort based on HE8 analysis.
LATIN_EXT_A: dict[str, str] = {
    "\u0102": "\u05d0\u05b7",  # Ă → alef + patah
    "\u0103": "\u05d0\u05b6",  # ă → alef + segol
    "\u0104": "\u05d0\u05b8",  # Ą → alef + qamats
    "\u0105": "\u05d0\u05b5",  # ą → alef + tsere
    "\u0106": "\u05d1\u05b7",  # Ć → bet + patah
    "\u010c": "\u05d1\u05b8",  # Č → bet + qamats
    "\u010e": "\u05d3\u05b8",  # Ď → dalet + qamats (or patah)
    "\u0118": "\u05d4\u05b8",  # Ę → he + qamats
    "\u0119": "\u05d4\u05b6",  # ę → he + segol
    "\u011a": "\u05d4\u05b7",  # Ě → he + patah
    "\u011b": "\u05d4\u05b5",  # ě → he + tsere
    "\u011e": "\u05d2\u05b7",  # Ğ → gimel + patah
    "\u0132": "\u05d9\u05b7",  # Ĳ → yod + patah
    "\u0133": "\u05d9\u05b6",  # ĳ → yod + segol
    "\u0139": "\u05dc\u05b7",  # Ĺ → lamed + patah
    "\u013d": "\u05dc\u05b8",  # Ľ → lamed + qamats
    "\u0141": "\u05de\u05b7",  # Ł → mem + patah
    "\u0147": "\u05e0\u05b8",  # Ň → nun + qamats
    "\u0148": "\u05e0\u05b7",  # ň → nun + patah
    "\u0154": "\u05e8\u05b8",  # Ŕ → resh + qamats
    "\u0158": "\u05e8\u05b7",  # Ř → resh + patah
    "\u0159": "\u05e8\u05b6",  # ř → resh + segol
    "\u015b": "\u05e9\u05b7",  # ś → shin + patah
    "\u0163": "\u05ea\u05b7",  # ţ → tav + patah
    "\u0165": "\u05ea\u05b8",  # ť → tav + qamats
    "\u016f": "\u05d5\u05b9",  # ů → vav + holam
    "\u0171": "\u05d5\u05bc\u05b9",  # ű → vav + dagesh + holam
    "\u017e": "\u05d6\u05b8",  # ž → zayin + qamats
}


import logging
import re

logger = logging.getLogger(__name__)

# Characters that are intentionally NOT mapped by the decoder.
# These appear in the Tiqwah TeX font encoding but:
#   a) mapping is uncertain without font file inspection, or
#   b) they represent typographic ligatures from LaTeX typesetting
# They are preserved as-is rather than mapped incorrectly.
# Revisit when font metrics become available.
KNOWN_UNMAPPED: dict[str, str] = {
    "\u00bf": "¿ — possibly rafe (U+05BF), but uncertain",
    "\u00cd": "Í — unknown; context suggests vowel variant",
    "\u00a7": "§ — section sign from original typesetting",
    "\u00a3": "£ — pound sign from original typesetting",
    "\u0151": "ő — Latin extended-A; unmapped",
}
_HEB_LETTER_PATTERN = re.compile(
    r"[\u05d0-\u05ea\u05f0-\u05f4\u0590-\u05ff"
    r"\u00c0-\u00ff\u0100-\u017f"
    r"a-zA-Z'\"#]+"
)

# SI-960 uppercase marker letters — final forms and dagesh variants used
# mid-word in SI-960 Hebrew but rarely in English prose (except all-caps).
_SI960_MARKER_UPPER = frozenset("KMNPSVWZ")

# Letters that are BOTH SI-960 Hebrew and ordinary English.
# We use these only in combination with stronger signals.
_SI960_AMBIGUOUS = frozenset("abcdefghijklmnopqrstuvwxyz")


def _get_si960_word_signals(text: str) -> tuple[int, int, int, int]:
    """Analyze text for SI-960 signals per word.

    Returns (mid_word_upper, mid_word_quotes, marker_total, signal_word_count).
    """
    mid_word_upper = 0
    mid_word_quotes = 0
    marker_total = 0
    signal_words = 0

    words = text.split()
    for w in words:
        if not w:
            continue

        has_consecutive_upper = any(
            w[i].isupper() and i > 0 and w[i + 1].isupper()
            for i in range(len(w) - 1)
        )
        word_signals = 0

        # Mid-word uppercase letters.
        # In SI-960, isolated uppercase mid-word indicates dagesh/final-form.
        # CamelCase (``pdfLATEX``) excluded by skipping words with consecutive
        # uppercase. Punctuation-preceded uppercase (``(Textus``) excluded by
        # checking prev char is a letter.
        if not has_consecutive_upper:
            for i, c in enumerate(w):
                if not c.isupper() or i == 0:
                    continue
                if not w[i - 1].isalpha():
                    continue
                mid_word_upper += 1
                word_signals += 1
        # Marker letters (final-form indicators in SI-960).
        # Only count if NOT at word start (common English proper nouns start with
        # letters like M, N, P, S, T, etc.).
        for i, c in enumerate(w):
            if c in _SI960_MARKER_UPPER and i > 0:
                if w[i - 1].isalpha():
                    marker_total += 1
                    word_signals += 1
        # Mid-word quotes (Alef/Ayin inside a word).
        for i, c in enumerate(w):
            if c in "'\"" and i > 0 and i < len(w) - 1:
                if w[i - 1].isalpha() and w[i + 1].isalpha():
                    mid_word_quotes += 1
                    word_signals += 2
        if word_signals > 0:
            signal_words += 1

    return mid_word_upper, mid_word_quotes, marker_total, signal_words


def is_likely_si960_encoded(text: str, min_chars: int = 10) -> bool:
    """Detect if *text* is SI-960 TeX Hebrew rather than ordinary English.

    Uses per-word signal analysis:
    1. Already has Hebrew Unicode → NOT SI-960 (already decoded).
    2. Combined score from mid-word uppercase, quote-markers, and marker letters.
    3. Requires signal to be distributed across multiple words (not a single
       CamelCase technical term like ``pdfLATEX``).
    """
    if not text or not text.strip():
        return False

    # If Hebrew Unicode already present, it's already decoded.
    if any("\u0590" <= c <= "\u05ff" for c in text):
        return False

    stripped = text.strip()
    if len(stripped) < min_chars:
        return False

    mid_word_upper, mid_word_quotes, marker_total, signal_words = _get_si960_word_signals(stripped)

    score = mid_word_upper * 2 + mid_word_quotes * 3 + marker_total
    # Primary path: distributed evidence across 2+ signal words
    if score >= 4 and (signal_words >= 2 or mid_word_quotes >= 1):
        return True
    # Fallback: if score is low but there is a mid-word quote (strong Alef/Ayin
    # signal), try decoding a sample and check for Hebrew Unicode output.
    if mid_word_quotes >= 1 and len(stripped) >= 10:
        try:
            decoded = decode_hebrew_text(stripped[:500])
            he_count = sum(1 for c in decoded if "\u0590" <= c <= "\u05ff")
            if he_count >= 5:
                return True
        except Exception:
            pass
    return False


def decode_hebrew_text_selective(
    text: str,
    fallback_keep_original: bool = True,
) -> str:
    """Decode SI-960 encoded text, but only if it looks like SI-960 encoding.

    If the text doesn't meet the SI-960 likelihood threshold, returns the original
    text unchanged (or with *fallback_keep_original*=True).
    """
    if is_likely_si960_encoded(text):
        return decode_hebrew_text(text)
    if fallback_keep_original:
        return text
    return text


def decode_hebrew_text(text: str) -> str:
    """Decode TeX Hebrew encoded text to Unicode Hebrew.

    Preserves digits, whitespace, and basic Latin punctuation.
    For 8-bit HE8 characters and Latin Extended-A, applies best-effort mapping.

    Also reverses character order within each Hebrew word for correct RTL
    rendering, since TeX stores Hebrew in visual (left-to-right) order.
    """
    decoded = []
    for ch in text:
        decoded.append(_decode_char(ch))
    decoded_str = "".join(decoded)
    # Reverse character order within each Hebrew word for RTL
    result = _HEB_LETTER_PATTERN.sub(_reverse_word, decoded_str)
    return result


def _reverse_word(match: re.Match) -> str:
    word = match.group(0)
    if len(word) <= 1:
        return word
    he_chars = sum(1 for c in word if "\u0590" <= c <= "\u05ff")
    if he_chars > 0 and he_chars >= len(word) * 0.3:
        return word[::-1]
    return word


def _decode_char(ch: str) -> str:
    cp = ord(ch)
    # Whitespace, control chars, ASCII digits: keep
    if cp <= 32 or (48 <= cp <= 57):
        return ch
    # SI-960 mapped characters
    if ch in SI960_TO_HEBREW:
        return SI960_TO_HEBREW[ch]
    # HE8 niqqud
    if ch in HE8_NIQQUD:
        return HE8_NIQQUD[ch]
    # HE8 letters
    if ch in HE8_LETTERS:
        return HE8_LETTERS[ch]
    # Latin Extended-A pre-composed
    if ch in LATIN_EXT_A:
        return LATIN_EXT_A[ch]
    # Common ASCII punctuation to preserve
    if cp in (0x2E, 0x2C, 0x3B, 0x3A, 0x28, 0x29, 0x5B, 0x5D, 0x2D, 0x21, 0x3F):
        return ch
    # Right single quote → alef
    if ch == "\u2019":
        return "\u05d0"
    # Left single quote → ayin
    if ch == "\u2018":
        return "\u05e2"
    # Curly quotes and dashes
    if ch in ("\u201c", "\u201d", "\u201e"):
        return '"'
    if ch in ("\u2013", "\u2014"):
        return "-"
    # Sof pasuq (end of verse) — colon in the text
    if ch == ":":
        return "\u05c3"
    # Equals sign → maqaf
    if ch == "=":
        return "\u05be"
    # Paseq
    if ch == "\u00b0":
        return "\u05c0"
    # Meteg (U+00A1 → Unicode U+05BD)
    # In the Tiqwah TeX font, position 0xA1 encodes meteg, a vertical bar
    # used as secondary stress marker in Masoretic cantillation.
    if ch == "\u00a1":
        return "\u05bd"
    # Ì (U+00CC) — context suggests qamats qatan (U+05C7) based on HE8 analysis
    if ch == "\u00cc":
        return "\u05c7"
    # Í (U+00CD) — unmapped; unknown with current evidence
    # ¿ (U+00BF) — unmapped; multiple TeX font families assign different glyphs
    # Both preserved as-is pending font file analysis.
    # Fallback: keep original character
    return ch


def scan_unknown_characters(text: str) -> dict[str, int]:
    """Scan decoded text for characters that are not Hebrew, ASCII, or whitespace.

    Returns {char: count} for all unexpected characters.
    Useful for decoder quality audits.
    """
    from collections import Counter
    result: Counter[str] = Counter()
    for c in text:
        cp = ord(c)
        if 0x0590 <= cp <= 0x05FF:  # Hebrew
            continue
        if cp <= 0x20 or (0x21 <= cp <= 0x7E):  # ASCII controls + printable
            continue
        if c in "\n\r\t":
            continue
        if 0x05BD <= cp <= 0x05C7:  # Hebrew marks (meteg, rafe, qamats qatan, etc.)
            continue
        result[c] += 1
    return dict(result)
