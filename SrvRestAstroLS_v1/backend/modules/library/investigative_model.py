"""Pure contracts for canonical, evidence-first investigative retrieval."""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass

TERM_ALIASES: dict[str, tuple[str, ...]] = {
    "alegría": ("alegría", "alegria", "שמחה", "simcha", "simjá", "joy", "happiness"),
    "fe": ("fe", "אמונה", "emunah", "emuná", "faith"),
    "plegaria": ("plegaria", "oración", "תפילה", "tefilah", "tefilá", "prayer"),
    "daat": ("daat", "דעת", "conocimiento", "knowledge", "consciousness"),
    "tzadik": ("tzadik", "צדיק", "righteous one"),
    "hitbodedut": ("hitbodedut", "התבודדות", "secluded prayer"),
    "temor": ("temor", "miedo", "temor reverencial", "יראה", "פחד", "awe", "fear"),
    "brit": ("brit", "ברית", "covenant", "sexual purity", "שמירת הברית", "pureza sexual"),
}

def normalize_literal(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).split())

def stable_hash(text: str) -> str:
    return hashlib.sha256(normalize_literal(text).encode("utf-8")).hexdigest()

def detect_language(text: str) -> str:
    if re.search(r"[\u0590-\u05ff]", text):
        return "he"
    # English-only is intentionally conservative; Spanish is the product default.
    if re.search(r"\b(the|and|prayer|fear|joy|faith)\b", text, re.I):
        return "en"
    return "es"

@dataclass(frozen=True)
class QueryExpansion:
    query: str
    language: str
    variants: tuple[str, ...]

def expand_query(query: str) -> QueryExpansion:
    language = detect_language(query)
    folded = unicodedata.normalize("NFKD", query).encode("ascii", "ignore").decode().casefold()
    values = [query.strip()]
    for canonical, aliases in TERM_ALIASES.items():
        tokens = (canonical, *aliases)
        if any(token.casefold() in query.casefold() or unicodedata.normalize("NFKD", token).encode("ascii", "ignore").decode().casefold() in folded for token in tokens):
            values.extend(aliases)
    return QueryExpansion(query=query, language=language, variants=tuple(dict.fromkeys(value for value in values if value)))

def relation_strength(relation_type: str, evidence_type: str, source_role: str, target_role: str) -> str:
    if relation_type in {"parallel_translation", "same_node"} or evidence_type in {"literal_same_span", "literal_same_node"}:
        return "strong"
    if relation_type == "same_page" and source_role != target_role:
        return "weak_contextual"
    if relation_type in {"ai_inferred", "thematic_relation"} or evidence_type in {"semantic", "thematic", "inferred"}:
        return "thematic_or_inferred"
    return "supported"
