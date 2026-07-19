"""Deterministic query resolution with edit distance, transliteration and catalog lookup.

Flow:
1. Normalise query deterministically (lowercase, trim, NFC, ASCII-fold diacritics)
2. Exact match against concept catalog (all searchable forms)
3. Alias / transliteration lookup
4. Damerau–Levenshtein edit-distance search against catalog forms
5. Rank candidates by confidence
6. Return resolution with suggestion type, confidence and alternatives

The module never invents terms — every suggestion is backed by the catalog.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Literal

from modules.library.concept_catalog import (
    CATALOG,
    ConceptEntry,
    get_concept,
    lookup_by_form,
)

SuggestionType = Literal[
    "exact_match",
    "normalized_match",
    "alias_match",
    "transliteration_match",
    "hebrew_original",
    "probable_typo",
    "no_suggestion",
]

# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

_LATIN_DIACRITICS = {
    "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u",
    "à": "a", "è": "e", "ì": "i", "ò": "o", "ù": "u",
    "â": "a", "ê": "e", "î": "i", "ô": "o", "û": "u",
    "ä": "a", "ë": "e", "ï": "i", "ö": "o", "ü": "u",
    "ñ": "n", "ç": "c",
    "Á": "a", "É": "e", "Í": "i", "Ó": "o", "Ú": "u",
    "À": "a", "È": "e", "Ì": "i", "Ò": "o", "Ù": "u",
    "Â": "a", "Ê": "e", "Î": "i", "Ô": "o", "Û": "u",
    "Ä": "a", "Ë": "e", "Ï": "i", "Ö": "o", "Ü": "u",
    "Ñ": "n", "Ç": "c",
}

_APOSTROPHES = str.maketrans({"ʼ": "'", "ʻ": "'", "ʽ": "'", "`": "'", "‘": "'", "’": "'"})


def normalize_query(raw: str) -> str:
    """Deterministic normalisation for Latin-script query terms.

    Steps: trim → NFC → lowercase → remove apostrophe variants → fold diacritics.
    """
    text = raw.strip()
    text = unicodedata.normalize("NFC", text)
    text = text.lower()
    text = text.translate(_APOSTROPHES)
    text = "".join(_LATIN_DIACRITICS.get(c, c) for c in text)
    return text


def _normalize_catalog_form(form: str) -> str:
    """Normalise a catalog form the same way as a user query for comparison."""
    return normalize_query(form)


# ---------------------------------------------------------------------------
# Damerau–Levenshtein distance
# ---------------------------------------------------------------------------

def _damerau_levenshtein(a: str, b: str) -> int:
    """Damerau–Levenshtein distance between two strings."""
    n, m = len(a), len(b)
    if n > m:
        a, b = b, a
        n, m = m, n
    d = [[0] * (m + 1) for _ in range(2)]
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        d[1][0] = i
        for j in range(1, m + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            d[1][j] = min(
                d[0][j] + 1,
                d[1][j - 1] + 1,
                d[0][j - 1] + cost,
            )
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[1][j] = min(d[1][j], d[0][j - 2] + cost)
        d[0], d[1] = d[1], d[0]
    return d[0][m]


# ---------------------------------------------------------------------------
# Candidate
# ---------------------------------------------------------------------------

class SuggestionCandidate:
    """A single suggestion derived from the catalog."""

    def __init__(
        self,
        concept_id: str,
        label: str,
        suggestion_type: SuggestionType,
        confidence: float,
        edit_distance: int = -1,
    ):
        self.concept_id = concept_id
        self.label = label
        self.suggestion_type = suggestion_type
        self.confidence = confidence
        self.edit_distance = edit_distance

    def __repr__(self) -> str:
        return (
            f"SuggestionCandidate("
            f"concept_id={self.concept_id!r}, "
            f"label={self.label!r}, "
            f"type={self.suggestion_type}, "
            f"confidence={self.confidence})"
        )


# ---------------------------------------------------------------------------
# Query resolution
# ---------------------------------------------------------------------------

def _min_word_length(query: str) -> int:
    return max(len(w) for w in query.split())


def resolve_query(query: str) -> tuple[str, list[SuggestionCandidate], str | None]:
    """Resolve a raw query against the concept catalog.

    Returns (normalized_query, candidates, autoapply_concept_id).

    Candidates are sorted by confidence descending.
    autoapply_concept_id is set when a single high-confidence suggestion exists.
    """
    norm = normalize_query(query)

    # --- 1. Exact match against all catalog forms ---
    concept_id = lookup_by_form(norm)
    if concept_id:
        return norm, [
            SuggestionCandidate(
                concept_id=concept_id,
                label=_canonical_label(concept_id),
                suggestion_type="exact_match",
                confidence=1.0,
            )
        ], concept_id

    # --- 2. Alias / transliteration lookup (normalised forms) ---
    for entry in CATALOG:
        all_forms = entry.all_searchable_forms()
        all_normalized = {_normalize_catalog_form(f) for f in all_forms}
        if norm in all_normalized:
            return norm, [
                SuggestionCandidate(
                    concept_id=entry.concept_id,
                    label=entry.canonical_label,
                    suggestion_type="alias_match",
                    confidence=1.0,
                )
            ], entry.concept_id

    # --- 3. Edit-distance search ---
    max_len = max(len(norm), 4)
    # Dynamic threshold: more tolerant for longer terms
    if max_len >= 10:
        max_dist = 2
    elif max_len >= 6:
        max_dist = 1
    else:
        max_dist = 1  # Short terms: only distance 1

    scored: list[tuple[float, SuggestionCandidate]] = []

    for entry in CATALOG:
        all_forms = entry.all_searchable_forms()
        all_normalized = {_normalize_catalog_form(f) for f in all_forms}
        for catalog_norm in all_normalized:
            dist = _damerau_levenshtein(norm, catalog_norm)
            if dist > max_dist:
                continue

            # Determine the type
            if dist == 1 and len(norm) >= 6:
                stype: SuggestionType = "probable_typo"
            elif dist <= max_dist and len(norm) >= 8:
                stype = "probable_typo"
            else:
                stype = "probable_typo"

            # Confidence: higher for shorter distance, longer terms
            # 1 - (dist / max_dist) adjusted by term length
            length_factor = min(1.0, len(norm) / 10.0)
            confidence = max(0.5, 1.0 - (dist / (max_dist + 1)) * (1.0 - length_factor * 0.3))

            scored.append((
                -confidence,
                SuggestionCandidate(
                    concept_id=entry.concept_id,
                    label=entry.canonical_label,
                    suggestion_type=stype,
                    confidence=round(confidence, 4),
                    edit_distance=dist,
                ),
            ))

    # Sort by confidence descending (negated score asc)
    scored.sort(key=lambda x: x[0])
    candidates = [sc for _, sc in scored]

    if not candidates:
        return norm, [], None

    # --- Auto-apply logic ---
    best = candidates[0]
    total = len(candidates)
    autoapply_id: str | None = None

    if best.edit_distance == 1 and len(norm) >= 6:
        # Single transposition/substitution on a sufficiently long term → high confidence
        autoapply_id = best.concept_id
    elif best.confidence >= 0.85 and total <= 2 and best.edit_distance != -1:
        autoapply_id = best.concept_id
    elif best.confidence >= 0.90 and total <= 2:
        autoapply_id = best.concept_id

    return norm, candidates, autoapply_id


def _canonical_label(concept_id: str) -> str:
    entry = get_concept(concept_id)
    return entry.canonical_label if entry else concept_id


def build_suggestion_contract(
    original_query: str,
    normalized_query: str,
    candidates: list[SuggestionCandidate],
    autoapply_id: str | None,
) -> dict:
    """Build the query_resolution dict for the API response."""
    best = candidates[0] if candidates else None
    exact = bool(best and best.suggestion_type == "exact_match")
    autoapplied = bool(autoapply_id and not exact)

    result: dict = {
        "original_query": original_query,
        "normalized_query": normalized_query,
        "exact_match": exact,
        "suggestion_applied": autoapplied,
    }

    if not candidates:
        result["suggested_query"] = None
        result["suggestion_type"] = None
        result["confidence"] = None
        result["alternatives"] = []
        result["related_concepts"] = []
        return result

    if autoapplied and best is not None:
        result["suggested_query"] = best.label
        result["suggestion_type"] = best.suggestion_type
        result["confidence"] = best.confidence

    # Build alternatives list (excluding the top candidate if autoapplied)
    alt_type_map = {
        "probable_typo": "Variante ortográfica probable",
        "transliteration_match": "Variante de transliteración",
        "alias_match": "Alias",
        "hebrew_original": "Forma hebrea",
        "exact_match": "Coincidencia exacta",
        "normalized_match": "Coincidencia normalizada",
        "no_suggestion": "",
    }
    alternatives = []
    seen_ids = set()
    # Include all candidates as alternatives
    for cand in candidates:
        if cand.concept_id in seen_ids:
            continue
        seen_ids.add(cand.concept_id)
        if cand.suggestion_type == "hebrew_original" and cand.confidence >= 0.9:
            continue
        entry = get_concept(cand.concept_id)
        alt_label = entry.canonical_label if entry else cand.label
        alternatives.append({
            "label": alt_label,
            "type": alt_type_map.get(cand.suggestion_type, cand.suggestion_type),
        })

    # Add related concepts from the best candidate's entry
    related_concepts = []
    if best:
        entry = get_concept(best.concept_id)
        if entry:
            for rel in entry.related_concepts:
                related_concepts.append({
                    "label": rel.label,
                    "relation_type": rel.relation_type,
                })
            # Always add Hebrew original if it exists
            if entry.hebrew and not any(a.get("label") == entry.hebrew for a in alternatives):
                alternatives.append({
                    "label": entry.hebrew,
                    "type": "Forma hebrea",
                })

    result["alternatives"] = alternatives
    result["related_concepts"] = related_concepts
    return result


__all__ = [
    "resolve_query",
    "normalize_query",
    "build_suggestion_contract",
    "SuggestionCandidate",
    "SuggestionType",
]
