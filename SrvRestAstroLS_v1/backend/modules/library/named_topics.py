"""Controlled multilingual named-topic resolution.

The model may identify a span, but only this versioned glossary can assign a
canonical topic ID or expand retrieval aliases.
"""
from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NamedTopicAlias(StrictModel):
    value: str = Field(min_length=1, max_length=200)
    language: str = Field(min_length=2, max_length=32)
    script: Literal["Latin", "Hebrew"]
    search: bool = True


class NamedTopicEntry(StrictModel):
    canonical_id: str = Field(pattern=r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")
    canonical_label: dict[Literal["es", "en", "he"], str]
    topic_type: Literal[
        "jewish_calendar_observance", "fast_day", "festival", "person",
        "work_title", "place", "institution", "conceptual_term",
        "custom_or_practice", "unknown_named_topic",
    ]
    aliases: list[NamedTopicAlias] = Field(min_length=1, max_length=80)


class NamedTopicResolution(StrictModel):
    matched: bool = True
    canonical_id: str
    canonical_label: str
    canonical_labels: dict[str, str]
    subject_raw: str
    subject_normalized: str
    subject_type: Literal["named_topic"] = "named_topic"
    topic_type: str
    matched_alias: str
    matched_alias_catalog_value: str
    match_kind: Literal[
        "exact_alias", "normalized_alias", "transliteration_variant",
        "translation_variant", "hebrew_equivalent", "minor_typo",
    ]
    confidence: float = Field(ge=0, le=1)
    language: str
    script: Literal["Latin", "Hebrew"]
    span_start: int = Field(ge=0)
    span_end: int = Field(ge=0)
    requires_clarification: bool = False
    variants_searched: list[str] = Field(default_factory=list)


_DATA_PATH = Path(__file__).with_name("data") / "named_topics.json"
_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "`": "'", "´": "'", "ʼ": "'", "׳": "'"})
_HYPHENS = re.compile(r"[\u2010-\u2015\u2212\u00ad-]")
_HEBREW = re.compile(r"[\u0590-\u05ff]")
_QUERY_WRAPPERS = {
    "que", "es", "donde", "aparece", "esta", "se", "encuentra", "menciona", "buscar", "busca",
    "what", "is", "where", "does", "appear", "mentioned", "find", "the", "topic", "concept",
    "מה", "זה", "איפה", "היכן", "מופיע", "נמצא", "מוזכר", "מושג", "המושג",
}


def normalize_named_topic_candidate(text: str) -> str:
    """Create a lookup key while leaving the caller's original text untouched."""
    value = unicodedata.normalize("NFC", text).translate(_APOSTROPHES)
    value = _HYPHENS.sub(" ", value)
    value = " ".join(value.strip().split()).casefold()
    decomposed = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in decomposed if not unicodedata.combining(char))
    value = re.sub(r"['\".,:;!?¿¡()\[\]{}]+", " ", value)
    return " ".join(value.split())


@lru_cache(maxsize=1)
def load_named_topic_glossary() -> tuple[NamedTopicEntry, ...]:
    payload = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    if payload.get("version") != 1 or not isinstance(payload.get("topics"), list):
        raise ValueError("unsupported_named_topic_glossary")
    entries = tuple(NamedTopicEntry.model_validate(item) for item in payload["topics"])
    ids = [entry.canonical_id for entry in entries]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate_named_topic_canonical_id")
    return entries


def _edit_distance_at_most_one(left: str, right: str) -> bool:
    if abs(len(left) - len(right)) > 1:
        return False
    if left == right:
        return True
    if len(left) > len(right):
        left, right = right, left
    i = j = differences = 0
    while i < len(left) and j < len(right):
        if left[i] == right[j]:
            i += 1
            j += 1
            continue
        differences += 1
        if differences > 1:
            return False
        if len(left) == len(right):
            i += 1
        j += 1
    return differences + (j < len(right)) <= 1


def _kind(alias: NamedTopicAlias, exact: bool, normalized: bool) -> str:
    if alias.script == "Hebrew":
        return "hebrew_equivalent"
    if alias.language == "transliteration":
        return "transliteration_variant"
    if alias.language in {"es", "en"} and not exact and not normalized:
        return "translation_variant"
    return "exact_alias" if exact else "normalized_alias"


def _resolution(
    entry: NamedTopicEntry,
    alias: NamedTopicAlias,
    raw: str,
    start: int,
    end: int,
    *,
    exact: bool,
    typo: bool = False,
) -> NamedTopicResolution:
    normalized = normalize_named_topic_candidate(raw)
    variants = [item.value for item in entry.aliases]
    return NamedTopicResolution(
        canonical_id=entry.canonical_id,
        canonical_label=entry.canonical_label["es"],
        canonical_labels=entry.canonical_label,
        subject_raw=raw,
        subject_normalized=normalized,
        topic_type=entry.topic_type,
        matched_alias=raw,
        matched_alias_catalog_value=alias.value,
        match_kind="minor_typo" if typo else _kind(alias, exact, normalized == normalize_named_topic_candidate(alias.value)),
        confidence=0.92 if typo else 1.0,
        language=alias.language,
        script=alias.script,
        span_start=start,
        span_end=end,
        variants_searched=variants,
    )


def resolve_named_topic(text: str) -> NamedTopicResolution | None:
    """Resolve the longest controlled alias before general token extraction."""
    original = unicodedata.normalize("NFC", text)
    normalized_query = normalize_named_topic_candidate(original)
    query_tokens = [
        (match.start(), match.end(), normalize_named_topic_candidate(match.group()))
        for match in re.finditer(r"[\w\u0590-\u05ff]+", original, re.UNICODE)
        if normalize_named_topic_candidate(match.group())
    ]
    candidates: list[tuple[int, int, NamedTopicEntry, NamedTopicAlias, str]] = []
    for entry in load_named_topic_glossary():
        for alias in entry.aliases:
            alias_key = normalize_named_topic_candidate(alias.value)
            if normalized_query == alias_key:
                candidate = (0, len(original), entry, alias, original)
                if original == alias.value or original.casefold() == alias.value.casefold():
                    candidates.insert(0, candidate)
                else:
                    candidates.append(candidate)
                continue
            alias_tokens = alias_key.split()
            for index in range(len(query_tokens) - len(alias_tokens) + 1):
                window = query_tokens[index:index + len(alias_tokens)]
                if [item[2] for item in window] == alias_tokens:
                    start, end = window[0][0], window[-1][1]
                    candidates.append((start, end, entry, alias, original[start:end]))
                    break
    if candidates:
        for start, end, entry, alias, raw in sorted(candidates, key=lambda item: (item[1] - item[0], -item[0]), reverse=True):
            residual = normalize_named_topic_candidate(original[:start] + " " + original[end:])
            residual_tokens = residual.split()
            relational = bool(re.search(r"(?i)(relaci[oó]n|relation|הקשר|compar)", original))
            if residual_tokens and not relational and any(token not in _QUERY_WRAPPERS for token in residual_tokens):
                continue
            exact = raw == alias.value
            return _resolution(entry, alias, raw, start, end, exact=exact)

    # Conservative typo recovery: whole-query only, one unique alias, no short input.
    if len(normalized_query) >= 8 and not _HEBREW.search(original):
        matches: list[tuple[NamedTopicEntry, NamedTopicAlias]] = []
        for entry in load_named_topic_glossary():
            for alias in entry.aliases:
                alias_key = normalize_named_topic_candidate(alias.value)
                if alias.script == "Latin" and len(alias_key) >= 8 and _edit_distance_at_most_one(normalized_query, alias_key):
                    matches.append((entry, alias))
        canonical_ids = {entry.canonical_id for entry, _alias in matches}
        if len(canonical_ids) == 1:
            entry, alias = min(matches, key=lambda item: len(item[1].value))
            return _resolution(entry, alias, original, 0, len(original), exact=False, typo=True)
    return None


def named_topic_retrieval_plan(resolution: NamedTopicResolution) -> dict:
    entry = next(item for item in load_named_topic_glossary() if item.canonical_id == resolution.canonical_id)
    def unique_values(values: list[str], limit: int) -> list[str]:
        selected: list[str] = []
        seen: set[str] = set()
        for value in values:
            key = value.casefold()
            if key in seen:
                continue
            selected.append(value)
            seen.add(key)
            if len(selected) >= limit:
                break
        return selected

    searchable = [alias for alias in entry.aliases if alias.search]
    transliterations = [alias.value for alias in searchable if alias.language == "transliteration"]
    primary = unique_values([
        resolution.matched_alias_catalog_value,
        entry.canonical_label["es"],
        *transliterations,
        entry.canonical_label["en"],
    ], 8)
    translations = [
        alias.value for alias in searchable
        if alias.language in {"es", "en"} and alias.value not in primary
    ]
    secondary = unique_values(translations, 4)
    hebrew = unique_values([alias.value for alias in searchable if alias.script == "Hebrew"], 2)
    ordered = list(dict.fromkeys([*primary, *secondary, *hebrew]))
    return {
        "strategy": "named_topic_multilingual",
        "canonical_id": entry.canonical_id,
        "primary_variants": primary,
        "secondary_variants": secondary,
        "hebrew_variants": hebrew,
        "variants_searched": ordered,
    }
