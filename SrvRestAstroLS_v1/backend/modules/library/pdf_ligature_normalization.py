"""Deterministic, reusable literal normalization for PDF-extracted text.

Two representations are kept distinct on purpose:

- ``text_original``: the exact extracted/persisted surface.  It is used for
  citations, visible evidence, original offsets, audits and editorial
  reproduction.  It is never rewritten here.
- ``search_text_normalized``: a search-only form.  It may apply Unicode
  compatibility normalization (NFKC), controlled whitespace collapse and,
  when explicitly requested, controlled PDF split-word variants.

PDF extractors commonly emit typographic ligatures (``ﬁ`` U+FB01,
``ﬂ`` U+FB02, ``ﬀ`` U+FB00, ``ﬃ`` U+FB03, ``ﬄ`` U+FB04, ``ﬅ`` U+FB05,
``ﬆ`` U+FB06) and occasionally insert an internal space around them
(``reﬁ namiento`` for ``refinamiento``).  This module normalizes those
ligatures for search matching without touching the original citation text.

Safety invariants
-----------------

- Normalization never corrects orthography (``aﬀecto`` -> ``affecto``, not
  ``afecto``).
- Variants only ever *insert* a space after a compatibility-ligature digraph
  inside an alphabetic run, mirroring the extraction defect.  Spaces already
  present are never removed, so real word boundaries are never joined
  (``la flor`` never becomes ``laflor``; ``por fin`` never becomes
  ``porfin``; ``fi nal`` is never collapsed to ``final``).
- Latin ligature normalization is independent from Hebrew normalization.
- The function is deterministic and idempotent:
  ``normalize_pdf_search_text(normalize_pdf_search_text(x)) == normalize_pdf_search_text(x)``.
"""

from __future__ import annotations

import re
import unicodedata

# Explicit compatibility-ligature expansion table.  NFKC already resolves
# every entry below; the explicit map is kept so the behavior is documented,
# deterministic and independent from the Python Unicode database version.
PDF_LIGATURE_EXPANSIONS: dict[str, str] = {
    "\ufb00": "ff",  # LATIN SMALL LIGATURE FF
    "\ufb01": "fi",  # LATIN SMALL LIGATURE FI
    "\ufb02": "fl",  # LATIN SMALL LIGATURE FL
    "\ufb03": "ffi",  # LATIN SMALL LIGATURE FFI
    "\ufb04": "ffl",  # LATIN SMALL LIGATURE FFL
    "\ufb05": "st",  # LATIN SMALL LIGATURE LONG S T
    "\ufb06": "st",  # LATIN SMALL LIGATURE ST
}

# Digraphs produced by expanding the ligatures above, in priority order
# (longest first so ``ffi``/``ffl`` are handled before ``ff``/``fi``/``fl``).
PDF_FRAGMENT_DIGRAPHS: tuple[str, ...] = ("ffi", "ffl", "ff", "fi", "fl", "st")

# Category classes that represent presentation whitespace in a search form.
_WHITESPACE_CATEGORIES = frozenset({"Cf", "Cc", "Zl", "Zp", "Zs"})

_ALPHABETIC_RUN = re.compile(r"[\w\u00c0-\u024f\u0370-\u03ff]+", re.UNICODE)

# A parenthetical gloss is an inline editorial explanation inserted right
# after a word (``Birur (pl. birurim; lit. “tamizar”) hace …``).  For literal
# matching only, such glosses are elided when the opening parenthesis is
# immediately preceded by an alphabetic character (``birur (gloss) hace`` ->
# ``birur hace``).  References printed at line/block starts (``(Salmos 16:1)``)
# are never touched because the preceding character is not a letter.
GLOSS_ELISION_PATTERN = r"(?<=[a-z]) *\([^()\n]{2,120}\)"
_GLOSS_ELISION_RE = re.compile(GLOSS_ELISION_PATTERN, re.IGNORECASE)


def elide_parenthetical_glosses(text: str) -> str:
    """Remove inline parenthetical glosses for search matching only.

    Only a parenthesis preceded by an alphabetic character is removed, so
    standalone references such as ``(Salmos 16:1)`` are preserved.  The
    function never alters the original citation text; it is a matching
    surface used alongside the original.
    """
    if not text:
        return text
    return _GLOSS_ELISION_RE.sub("", text)


def expand_pdf_compatibility_characters(text: str) -> str:
    """Expand typographic ligatures to their multi-character equivalents.

    ``reﬁnamiento`` -> ``refinamiento``; ``aﬀecto`` -> ``affecto``.
    Orthography is not corrected: the output is purely mechanical.
    """
    if not text:
        return text
    expanded = unicodedata.normalize("NFKC", text)
    for ligature, replacement in PDF_LIGATURE_EXPANSIONS.items():
        if ligature in expanded:
            expanded = expanded.replace(ligature, replacement)
    return expanded


def _collapse_whitespace(text: str) -> str:
    """Replace every run of presentation whitespace with a single space.

    This never removes spaces; it only normalizes their width/kind.
    """
    return " ".join(text.split())


def normalize_pdf_search_text(text: str) -> str:
    """Canonical search form for PDF-extracted text.

    Applies NFKC (which expands compatibility ligatures), collapses
    presentation whitespace and trims.  Original text is never modified.

    Example::

        "reﬁ namiento" -> "refi namiento"

    Note the internal space is *preserved* here: collapsing it would join
    real words.  Split-word reconstruction is offered separately through
    :func:`build_pdf_literal_match_variants`.
    """
    if not text:
        return ""
    expanded = expand_pdf_compatibility_characters(text)
    return _collapse_whitespace(expanded)


def _digraph_positions(word: str) -> list[tuple[int, str]]:
    """Return (position, digraph) pairs inside an alphabetic run.

    A digraph qualifies only when it is fully embedded between alphabetic
    characters, i.e. it is neither at the start nor at the end of the run
    and has letters on both sides.  This models a word that a PDF extractor
    split right after the ligature (``reﬁ| namiento``).
    """
    lowered = word.casefold()
    found: list[tuple[int, str]] = []
    for digraph in PDF_FRAGMENT_DIGRAPHS:
        start = 0
        while True:
            position = lowered.find(digraph, start)
            if position == -1:
                break
            end = position + len(digraph)
            before_ok = position > 0 and word[position - 1].isalpha()
            after_ok = end < len(word) and word[end].isalpha()
            if before_ok and after_ok:
                found.append((position, digraph))
            start = position + 1
    # Stable order: longest digraph first, then by position.
    found.sort(key=lambda item: (-len(item[1]), item[0]))
    return found


def _fragmentation_variants(text: str, *, limit: int = 4) -> list[str]:
    """Generate controlled split-word variants of *text*.

    Each variant inserts exactly one space right after an embedded ligature
    digraph inside an alphabetic run, mirroring PDF split-word extraction.
    Because only spaces are inserted, real word boundaries are never joined.
    """
    if not text or limit <= 0:
        return []
    variants: list[str] = []
    seen: set[str] = set()
    for match in _ALPHABETIC_RUN.finditer(text):
        word = match.group()
        # A very short run is far more likely to be a real standalone word.
        if len(word) < 4:
            continue
        for position, digraph in _digraph_positions(word):
            insert_at = position + len(digraph)
            split_word = f"{word[:insert_at]} {word[insert_at:]}"
            variant = f"{text[:match.start()]}{split_word}{text[match.end():]}"
            if variant not in seen:
                seen.add(variant)
                variants.append(variant)
                if len(variants) >= limit:
                    return variants
    return variants


def build_pdf_literal_match_variants(text: str) -> list[str]:
    """Return ``[canonical, *fragmentation variants]`` for literal matching.

    The canonical form is first and matches text whose ligatures were
    expanded but whose internal extraction space remains
    (``reﬁ namiento`` -> ``refi namiento``).  Fragmentation variants add the
    extraction space to the query side (``refinamiento`` -> ``refi namiento``)
    so both surfaces can be located literally.  Variants are matching-only;
    they never replace the original citation text.
    """
    canonical = normalize_pdf_search_text(text)
    if not canonical:
        return []
    return list(dict.fromkeys([canonical, *_fragmentation_variants(canonical)]))


def has_pdf_fragmentation_signal(text: str) -> bool:
    """True when the search form contains an embedded ligature digraph.

    Used by audit tooling to decide whether a query is eligible for
    fragmentation variants without ever applying them blindly.
    """
    canonical = normalize_pdf_search_text(text)
    return any(
        word
        for match in _ALPHABETIC_RUN.finditer(canonical)
        if len((word := match.group())) >= 4 and _digraph_positions(word)
    )
