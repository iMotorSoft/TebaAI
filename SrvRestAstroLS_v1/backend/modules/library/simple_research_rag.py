"""Simple, failure-tolerant, PostgreSQL-grounded RAG for research."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

import httpx

from globalVar import (
    BRESLOV_PRODUCTIVE_COLLECTION,
    EMBEDDINGS_DIMENSION,
    EMBEDDINGS_MODEL_ALIAS,
    LITELLM_API_KEY,
    LITELLM_BASE_URL,
    LITELLM_TIMEOUT_SECONDS,
    RESEARCH_CONVERSATION_MODEL,
    RESEARCH_INCLUDE_TEST_CANDIDATES_READONLY,
)
from infrastructure.milvus.client import (
    create_connection,
    ensure_collection,
    search_vectors,
)
from modules.embeddings.client import embed_text
from modules.library.hybrid_search import resolve_milvus_collection_code_for_scope
from modules.library.investigative_model import detect_language
from modules.library.hebrew_lexical_normalizer import (
    HebrewSearchNormalization,
    has_hebrew,
    normalize_hebrew_for_search,
)
from modules.library.simple_research_repository import (
    fetch_canonical_chunks,
    resolve_ready_documents,
    search_literal_candidates,
)

logger = logging.getLogger(__name__)

DEFAULT_SCOPE = "breslov_primary"
DEFAULT_WORKS = {"kitzur", "lmi", "lmii", "lh", "lm_xv", "potencia_plegaria"}
SEMANTIC_TOP_K = 30
LITERAL_TOP_K = 30
CONTEXT_MIN = 8
CONTEXT_MAX = 12

_HEBREW_LETTER = re.compile(r"[\u05d0-\u05ea]")
_HEBREW_PREFIXES = frozenset("ובכלמש")
_LATIN_NAME_TOKEN = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]+(?:['’][A-Za-zÀ-ÖØ-öø-ÿ]+)?")
_PAGE_MARKER = re.compile(r"(?m)^## Page\s+(\d+)\s*$")
_NAME_CONNECTORS = frozenset({"of", "de", "del", "ben", "bar", "von", "van"})
_NAME_HONORIFICS = frozenset({
    "baal", "maggid", "moharnat", "rabbi", "rabi", "rabí", "rav", "reb",
    "rebbe",
})
_QUESTION_WORDS = frozenset({
    "what", "where", "when", "why", "how", "who", "which", "does", "is",
    "are", "can", "could", "would", "should",
})


@dataclass(frozen=True)
class EnglishNameQuery:
    normalized: str
    tokens: tuple[str, ...]
    nominal_tokens: tuple[str, ...]


def normalize_english_for_search(value: str) -> str:
    """Normalize Latin search text without dropping nominal connectors such as 'of'."""
    normalized = unicodedata.normalize("NFKC", value)
    normalized = "".join(
        " "
        if unicodedata.category(char) in {"Cf", "Cc", "Zl", "Zp"}
        else char
        for char in normalized
    )
    normalized = (
        normalized.replace("’", "'")
        .replace("‘", "'")
        .replace("–", "-")
        .replace("—", "-")
    )
    tokens = _LATIN_NAME_TOKEN.findall(normalized)
    return " ".join(token.casefold() for token in tokens)


def detect_short_english_name_query(value: str) -> EnglishNameQuery | None:
    """Recognize bounded nominal lookups without requiring an intent classifier."""
    if has_hebrew(value):
        return None
    raw_tokens = _LATIN_NAME_TOKEN.findall(unicodedata.normalize("NFKC", value))
    if not 1 <= len(raw_tokens) <= 5:
        return None
    tokens = tuple(token.casefold().replace("’", "'") for token in raw_tokens)
    if tokens[0] in _QUESTION_WORDS:
        return None
    non_connector_tokens = [
        (raw_token, token)
        for raw_token, token in zip(raw_tokens, tokens, strict=True)
        if token not in _NAME_CONNECTORS
    ]
    has_nominal_shape = (
        any(token in _NAME_CONNECTORS or token in _NAME_HONORIFICS for token in tokens)
        or all(raw_token[:1].isupper() for raw_token, _ in non_connector_tokens)
    )
    if not has_nominal_shape:
        return None
    nominal_tokens = tuple(
        token for token in tokens if token not in _NAME_CONNECTORS
    )
    if not nominal_tokens:
        return None
    return EnglishNameQuery(
        normalized=" ".join(tokens),
        tokens=tokens,
        nominal_tokens=nominal_tokens,
    )


def detect_research_query_language(
    value: str,
    english_name_query: EnglishNameQuery | None = None,
) -> str:
    """Resolve ASCII proper-name lookups as English instead of the Spanish default."""
    english_name_query = english_name_query or detect_short_english_name_query(value)
    if english_name_query is not None and all(ord(char) < 128 for char in value):
        return "en"
    return detect_language(value)


def _english_name_orthographic_variants(query: EnglishNameQuery) -> list[str]:
    """Generate a small, auditable vowel-variation set for transliterated names."""
    variants: list[str] = []
    token_index = len(query.tokens) - 1
    token = query.tokens[token_index]
    if token in _NAME_CONNECTORS or len(token) < 5:
        return variants
    for char_index, char in enumerate(token):
        if char not in {"e", "i"}:
            continue
        replacement = "i" if char == "e" else "e"
        changed = token[:char_index] + replacement + token[char_index + 1:]
        changed_tokens = list(query.tokens)
        changed_tokens[token_index] = changed
        variants.append(" ".join(changed_tokens))
        if len(variants) >= 4:
            break
    return variants


def _hebrew_catalog_cross_language_variants(original_query: str) -> list[str]:
    """Look up Hebrew tokens in the concept catalog and return ES/EN aliases.

    For each significant Hebrew token found in the query, strip common prefixes
    (ה, ו, ב, כ, ל, מ, ש) and look up the form in the concept catalog.
    If matched, add all non-Hebrew aliases and translations from the entry.
    """
    if not has_hebrew(original_query):
        return []
    from modules.library.concept_catalog import CATALOG

    # Build reverse index: Hebrew form → concept_id
    hebrew_to_concept: dict[str, str] = {}
    for entry in CATALOG:
        if entry.hebrew:
            hebrew_to_concept[entry.hebrew] = entry.concept_id
        for alias in entry.aliases:
            if bool(_HEBREW_LETTER.search(alias)):
                hebrew_to_concept[alias] = entry.concept_id

    tokens = set(re.findall(r"[\u0590-\u05ff]{2,}", original_query))
    seen: set[str] = set()
    variants: list[str] = []

    for token in tokens:
        if len(token) < 2:
            continue
        # Direct form
        concept_id = hebrew_to_concept.get(token)
        # Strip a single prefix/waw/conjunctive letter (ובכלמש)
        if not concept_id and len(token) >= 3 and token[0] in _HEBREW_PREFIXES:
            concept_id = hebrew_to_concept.get(token[1:])
        # Strip definite article ה
        if not concept_id and len(token) >= 3 and token[0] == 'ה':
            concept_id = hebrew_to_concept.get(token[1:])
        # Strip double prefix (e.g. "והעקרב" → "עקרב")
        if not concept_id and len(token) >= 4 and token[0] in _HEBREW_PREFIXES and token[1] in _HEBREW_PREFIXES:
            concept_id = hebrew_to_concept.get(token[2:])
        if not concept_id and len(token) >= 4 and token[0] in _HEBREW_PREFIXES and token[1] == 'ה':
            concept_id = hebrew_to_concept.get(token[2:])

        if concept_id and concept_id not in seen:
            seen.add(concept_id)
            entry = next((e for e in CATALOG if e.concept_id == concept_id), None)
            if entry:
                for alias in entry.aliases:
                    if not _HEBREW_LETTER.search(alias):
                        variants.append(alias)
                for trans in entry.translations:
                    if not _HEBREW_LETTER.search(trans):
                        variants.append(trans)
    return list(dict.fromkeys(variants))


_LATIN_LETTERS = re.compile(r"[a-zA-Z]")


def _latin_catalog_cross_language_variants(original_query: str) -> list[str]:
    """Look up significant Latin-script tokens in the concept catalog.

    For each alphabet token found in the query, check the catalog's form index.
    If matched, add Hebrew and non-English/non-Spanish aliases from the entry.
    This covers English queries like "speech" → "habla" + "דיבור".
    """
    if not _LATIN_LETTERS.search(original_query):
        return []
    from modules.library.concept_catalog import CATALOG, lookup_by_form

    tokens = re.findall(r"[a-zA-Z\u00e0-\u00fc]{3,}", original_query.casefold())
    seen: set[str] = set()
    variants: list[str] = []

    for token in tokens:
        concept_id = lookup_by_form(token)
        if concept_id and concept_id not in seen:
            seen.add(concept_id)
            entry = next((e for e in CATALOG if e.concept_id == concept_id), None)
            if entry:
                # Add Hebrew form if available
                if entry.hebrew and entry.hebrew not in variants:
                    variants.append(entry.hebrew)
                # Add Hebrew aliases
                for alias in entry.aliases:
                    if _HEBREW_LETTER.search(alias) and alias not in variants:
                        variants.append(alias)
    return list(dict.fromkeys(variants))


CONTROLLED_EXPANSIONS: dict[str, tuple[str, ...]] = {
    "azamra": ("Azamra", "Azamrá", "אזמרה", "אֲזַמְּרָה", "I will sing", "cantaré"),
    "escorpion": ("escorpión", "escorpion", "escorpiones", "scorpion", "scorpions", "עקרב", "עקרבים"),
    "scorpion": ("scorpion", "scorpions", "escorpión", "escorpion", "escorpiones", "עקרב", "עקרבים"),
    "habla": ("habla", "palabra", "decir", "voz", "speech", "speaking", "דיבור"),
    "sangre": ("sangre", "blood", "דם"),
    "alegria": ("alegría", "alegria", "simjá", "simcha", "joy", "שמחה"),
    "emuna": ("emuná", "emuna", "emunah", "fe", "faith", "אמונה"),
    "miedo": ("miedo", "temor", "fear", "awe", "פחד", "יראה"),
    "tristeza": ("tristeza", "melancolía", "sadness", "atzvut", "עצבות"),
    "hitbodedut": ("hitbodedut", "התבודדות", "plegaria personal", "secluded prayer"),
    "salmo 19": ("Salmo 19", "Salmos 19", "Psalm 19", "Psalms 19", "תהלים יט"),
}


def _fold(value: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", value).casefold()
        if not unicodedata.combining(char)
    )


def build_query_variants(original_query: str) -> list[str]:
    """Keep the complete query first and add only bounded, controlled aliases."""
    folded = _fold(original_query)
    variants = [original_query]
    english_name_query = detect_short_english_name_query(original_query)
    if english_name_query:
        variants.append(english_name_query.normalized)
        variants.extend(_english_name_orthographic_variants(english_name_query))
    if has_hebrew(original_query):
        try:
            normalized = normalize_hebrew_for_search(original_query)
            variants.extend((
                normalized.compacted_with_marks,
                normalized.without_cantillation,
                normalized.without_niqqud,
            ))
        except Exception:
            logger.warning("Hebrew query variant normalization failed", exc_info=True)
    for key, aliases in CONTROLLED_EXPANSIONS.items():
        if key in folded:
            variants.extend(aliases)
    if "sangre" in folded and "habla" in folded:
        variants.extend((
            "impurezas en la sangre",
            "elevar la voz",
            "recitación del Shemá",
            "recitar esos dos versículos",
            "Reinado del Cielo",
        ))
    # Hebrew cross-language expansion via concept catalog
    hebrew_cross = _hebrew_catalog_cross_language_variants(original_query)
    variants.extend(hebrew_cross)
    # Latin cross-language expansion via concept catalog (English→Hebrew, etc.)
    latin_cross = _latin_catalog_cross_language_variants(original_query)
    variants.extend(latin_cross)
    return list(dict.fromkeys(item.strip() for item in variants if item.strip()))[:36]


def build_explicit_filters(data: Any) -> dict[str, Any]:
    works = list(data.works)
    explicit_works = works if set(works) != DEFAULT_WORKS else []
    query_language = detect_language(data.question)
    languages = list(dict.fromkeys([query_language, *data.languages]))
    return {
        "scope": DEFAULT_SCOPE,
        "works": explicit_works,
        "languages": languages,
        "include_parallels": bool(data.include_thematic),
        "result_limit": min(max(int(data.max_hits_per_work), 1), 20),
        "include_test_candidates": RESEARCH_INCLUDE_TEST_CANDIDATES_READONLY,
    }


def _milvus_expression(
    *,
    scope_code: str,
    languages: list[str],
    document_ids: list[str],
) -> str:
    clauses = [
        f'collection_code == "{resolve_milvus_collection_code_for_scope(scope_code)}"'
    ]
    if languages:
        quoted = ", ".join(json.dumps(item) for item in languages)
        clauses.append(f"language in [{quoted}]")
    if document_ids:
        quoted = ", ".join(json.dumps(item) for item in document_ids)
        clauses.append(f"document_id in [{quoted}]")
    return " and ".join(clauses)


def _semantic_search(
    original_query: str,
    *,
    scope_code: str,
    languages: list[str],
    document_ids: list[str],
    simulate_failure: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    started = time.perf_counter()
    if simulate_failure:
        raise RuntimeError("simulated_milvus_failure")
    vector = embed_text(original_query)
    if len(vector) != EMBEDDINGS_DIMENSION:
        raise ValueError("embedding_dimension_mismatch")
    create_connection()
    ensure_collection(BRESLOV_PRODUCTIVE_COLLECTION, dimension=len(vector))
    hits = search_vectors(
        collection_name=BRESLOV_PRODUCTIVE_COLLECTION,
        query_embedding=vector,
        top_k=SEMANTIC_TOP_K,
        expr=_milvus_expression(
            scope_code=scope_code,
            languages=languages,
            document_ids=document_ids,
        ),
        output_fields=["chunk_id", "document_id", "language"],
    )
    return (
        [
            {
                "chunk_id": str(hit.get("chunk_id") or ""),
                "semantic_score": float(hit.get("distance") or 0.0),
                "semantic_rank": index + 1,
            }
            for index, hit in enumerate(hits)
            if hit.get("chunk_id")
        ],
        {
            "model": EMBEDDINGS_MODEL_ALIAS,
            "dimension": len(vector),
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        },
    )


def _semantic_search_variants(
    original_query: str,
    *,
    normalized_query: str | None,
    scope_code: str,
    languages: list[str],
    document_ids: list[str],
    simulate_failure: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Search the original query and one bounded Hebrew-normalized variant."""
    queries = list(dict.fromkeys(
        query for query in (original_query, normalized_query) if query
    ))
    by_id: dict[str, dict[str, Any]] = {}
    metadata: dict[str, Any] = {}
    total_latency = 0.0
    for query_index, query in enumerate(queries):
        hits, current = _semantic_search(
            query,
            scope_code=scope_code,
            languages=languages,
            document_ids=document_ids,
            simulate_failure=simulate_failure,
        )
        metadata = current
        total_latency += float(current.get("latency_ms") or 0.0)
        for hit in hits:
            chunk_id = hit["chunk_id"]
            existing = by_id.get(chunk_id)
            if existing is None or hit["semantic_score"] > existing["semantic_score"]:
                by_id[chunk_id] = {
                    **hit,
                    "semantic_query_variant": (
                        "original" if query_index == 0 else "hebrew_without_niqqud"
                    ),
                }
    ordered = sorted(
        by_id.values(),
        key=lambda item: item["semantic_score"],
        reverse=True,
    )[:SEMANTIC_TOP_K]
    for rank, item in enumerate(ordered, 1):
        item["semantic_rank"] = rank
    metadata["latency_ms"] = round(total_latency, 2)
    metadata["query_variants_used"] = len(queries)
    return ordered, metadata


def merge_results(
    semantic: list[dict[str, Any]],
    literal: list[dict[str, Any]],
    *,
    query_language: str,
    english_name_query: EnglishNameQuery | None = None,
) -> list[dict[str, Any]]:
    """Fuse ranks without allowing either retrieval branch to erase the other."""
    merged: dict[str, dict[str, Any]] = {}
    for item in semantic:
        merged[item["chunk_id"]] = {
            **item,
            "literal_score": 0.0,
            "literal_rank": None,
            "exact_match": False,
            "retrieval_sources": ["milvus"],
        }
    for rank, item in enumerate(literal, 1):
        chunk_id = str(item["chunk_id"])
        target = merged.setdefault(chunk_id, {
            "chunk_id": chunk_id,
            "semantic_score": 0.0,
            "semantic_rank": None,
            "retrieval_sources": [],
        })
        target.update({
            "literal_score": float(item.get("literal_score") or 0.0),
            "literal_rank": rank,
            "exact_match": bool(item.get("exact_match")),
            "exact_variant_count": int(item.get("exact_variant_count") or 0),
            "literal_match_type": str(
                item.get("literal_match_type")
                or ("exact_phrase" if item.get("exact_match") else "literal")
            ),
            "search_record_type": str(item.get("search_record_type") or "chunk"),
            "matched_variant": item.get("matched_variant"),
            "matched_variant_ordinal": item.get("matched_variant_ordinal"),
        })
        if english_name_query:
            matched_variant = normalize_english_for_search(
                str(item.get("matched_variant") or "")
            )
            if item.get("exact_match") and matched_variant == english_name_query.normalized:
                target["literal_match_type"] = "english_name_exact"
            elif item.get("exact_match") and matched_variant:
                target["literal_match_type"] = "english_name_variant"
            else:
                target["literal_match_type"] = "english_name_partial"
        target["retrieval_sources"].append("literal")
    for item in merged.values():
        semantic_rrf = 1 / (50 + item["semantic_rank"]) if item.get("semantic_rank") else 0.0
        literal_rrf = 1 / (50 + item["literal_rank"]) if item.get("literal_rank") else 0.0
        overlap_bonus = 0.008 if len(item["retrieval_sources"]) == 2 else 0.0
        exact_bonus = 0.006 if item.get("exact_match") else 0.0
        controlled_coverage_bonus = min(
            int(item.get("exact_variant_count") or 0),
            8,
        ) * 0.002
        hebrew_literal_priority = {
            "hebrew_exact_diacritized": 12.0,
            "hebrew_exact_normalized": 11.0,
            "hebrew_all_tokens_ordered": 9.0,
            "hebrew_all_tokens_proximity": 8.0,
            "hebrew_bigram": 6.0,
            "hebrew_partial_tokens": 4.0,
        }.get(str(item.get("literal_match_type")), 0.0)
        english_name_priority = {
            "english_name_exact": 12.0,
            "english_name_normalized": 11.0,
            "english_name_all_tokens_ordered": 9.0,
            "english_name_all_tokens_proximity": 8.0,
            "english_name_variant": 7.0,
            "english_name_partial": 4.0,
        }.get(str(item.get("literal_match_type")), 0.0)
        semantic_only_penalty = (
            -0.02
            if (
                (query_language == "he" or english_name_query is not None)
                and not item.get("literal_rank")
            )
            else 0.0
        )
        item["combined_score"] = (
            hebrew_literal_priority
            + english_name_priority
            + semantic_rrf
            + literal_rrf
            + overlap_bonus
            + exact_bonus
            + controlled_coverage_bonus
            + semantic_only_penalty
        )
        item["query_language"] = query_language
    return sorted(
        merged.values(),
        key=lambda item: (item["combined_score"], item["semantic_score"]),
        reverse=True,
    )


def _source_layer(chunk: dict[str, Any]) -> str:
    role = str(chunk.get("evidence_role") or "")
    block = str(chunk.get("block_type") or "")
    if chunk.get("authority_level") == "primary_original":
        return "rebbe_lesson_text"
    if block == "footnote":
        return "footnote"
    if "source" in role:
        return "rebbe_lesson_text"
    if "comment" in role:
        return "editorial_commentary"
    return "editorial_translation" if chunk.get("language") == "es" else "unknown"


def _work_code(chunk: dict[str, Any]) -> str:
    title = _fold(str(chunk.get("work") or ""))
    if "kitzur" in title:
        return "kitzur"
    if "potencia de la plegaria" in title:
        return "potencia_plegaria"
    if "likutey halajot" in title:
        return "lh"
    if "likutey moharan ii" in title:
        return "lmii"
    if "likutey moharan" in title:
        return "lmi"
    return str(chunk.get("document_code") or "breslov")


def select_context(
    ranked: list[dict[str, Any]],
    canonical_by_id: dict[str, dict[str, Any]],
    *,
    explicit_work_filter: bool,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    per_work: defaultdict[str, int] = defaultdict(int)
    seen_content: set[str] = set()
    max_per_work = CONTEXT_MAX if explicit_work_filter else 4
    for item in ranked:
        chunk = canonical_by_id.get(item["chunk_id"])
        if not chunk:
            continue
        content_key = str(chunk.get("content_sha256") or "")
        if not content_key:
            content_key = hashlib.sha256(str(chunk.get("markdown") or "").encode()).hexdigest()
        if content_key in seen_content:
            continue
        work = str(chunk.get("work") or "")
        if per_work[work] >= max_per_work:
            continue
        selected.append({**chunk, **item})
        seen_content.add(content_key)
        per_work[work] += 1
        if len(selected) >= CONTEXT_MAX:
            break
    return selected


def _evidence_id(chunk_id: str) -> str:
    return f"ev-{hashlib.sha256(chunk_id.encode()).hexdigest()[:16]}"


HEBREW_PRIMARY_MATCH_TYPES = {
    "hebrew_exact_diacritized",
    "hebrew_exact_normalized",
    "hebrew_all_tokens_ordered",
}
ENGLISH_NAME_PRIMARY_MATCH_TYPES = {
    "english_name_exact",
    "english_name_normalized",
    "english_name_all_tokens_ordered",
    "english_name_all_tokens_proximity",
    "english_name_variant",
}


def _is_primary_eligible(
    chunk: dict[str, Any],
    *,
    query_language: str,
    english_name_query: EnglishNameQuery | None = None,
) -> bool:
    match_type = str(chunk.get("literal_match_type"))
    if query_language == "he":
        return match_type in HEBREW_PRIMARY_MATCH_TYPES
    if english_name_query is not None:
        return match_type in ENGLISH_NAME_PRIMARY_MATCH_TYPES
    return True


def _match_local_pdf_page(chunk: dict[str, Any]) -> int | None:
    """Resolve the page marker nearest a literal match inside a spanning chunk."""
    markdown = str(chunk.get("markdown") or "")
    matched_variant = str(chunk.get("matched_variant") or "").strip()
    if not markdown or not matched_variant:
        return chunk.get("pdf_page")
    match_position = markdown.casefold().find(matched_variant.casefold())
    if match_position < 0:
        return chunk.get("pdf_page")
    markers = [
        (match.start(), int(match.group(1)))
        for match in _PAGE_MARKER.finditer(markdown)
        if match.start() <= match_position
    ]
    if not markers:
        return chunk.get("pdf_page")
    marker_page = markers[-1][1]
    page_start = chunk.get("pdf_page")
    page_end = chunk.get("pdf_page_end")
    if (
        page_start is not None
        and page_end is not None
        and not int(page_start) <= marker_page <= int(page_end)
    ):
        return chunk.get("pdf_page")
    return marker_page


def _context_pack(
    original_query: str,
    filters: dict[str, Any],
    chunks: list[dict[str, Any]],
    normalization: HebrewSearchNormalization | None = None,
) -> str:
    lines = [
        "PREGUNTA ORIGINAL",
        original_query,
        "",
        "FILTROS EXPLÍCITOS",
        json.dumps(filters, ensure_ascii=False),
        "",
        "INSTRUCCIONES DE RESPUESTA",
        "Usá exclusivamente las fuentes siguientes. Citá evidence_ids.",
    ]
    if normalization:
        lines.extend([
            "",
            "NORMALIZACIÓN HEBREA DE BÚSQUEDA (no es una cita)",
            f"Forma sin niqqud: {normalization.without_niqqud}",
            f"Tokens principales: {', '.join(normalization.tokens)}",
        ])
    for index, chunk in enumerate(chunks, 1):
        lines.extend([
            "",
            f"FUENTE {index}",
            f"Evidence ID: {chunk['evidence_id']}",
            f"Obra: {chunk['work']}",
            f"Página PDF: {chunk.get('pdf_page')}",
            f"Página impresa: {chunk.get('printed_page')}",
            f"Idioma: {chunk.get('language')}",
            f"Tipo de coincidencia: {chunk.get('literal_match_type', 'semantic_only')}",
            f"Variante coincidente: {chunk.get('matched_variant') or 'ninguna'}",
            "Markdown:",
            str(chunk.get("markdown") or ""),
        ])
    return "\n".join(lines)


def validate_grounded_answer(
    value: dict[str, Any],
    chunks: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    allowed = {chunk["evidence_id"]: chunk for chunk in chunks}
    markdown = str(value.get("answer_markdown") or "").strip()
    claims = value.get("claims")
    if not markdown or not isinstance(claims, list) or not claims:
        raise ValueError("missing_grounded_answer")
    cited_in_markdown = set(re.findall(r"\bev-[0-9a-f]{16}\b", markdown))
    if not cited_in_markdown.issubset(allowed):
        raise ValueError("invented_markdown_evidence_id")
    normalized_claims = []
    for index, claim in enumerate(claims, 1):
        ids = list(dict.fromkeys(
            str(item).strip().strip("[]`")
            for item in claim.get("evidence_ids", [])
        ))
        if not ids or not set(ids).issubset(allowed):
            raise ValueError(f"invalid_evidence_id:{ids}")
        relation_type = str(claim.get("relation_type") or "thematic")
        if relation_type not in {"direct", "mediated", "thematic", "none"}:
            raise ValueError("invalid_relation_type")
        confidence = str(claim.get("confidence") or "low")
        if confidence not in {"high", "medium", "low"}:
            raise ValueError("invalid_confidence")
        normalized_claims.append({
            "claim_id": str(claim.get("claim_id") or f"claim_{index}"),
            "text": str(claim.get("text") or "").strip(),
            "strength": {"high": "strong", "medium": "medium", "low": "weak"}[confidence],
            "confidence": confidence,
            "relation_type": relation_type,
            "evidence_ids": ids,
            "primary_evidence_id": ids[0],
        })
        if not normalized_claims[-1]["text"]:
            raise ValueError("empty_claim")
    allowed_pages = {
        str(chunk["pdf_page"])
        for chunk in chunks
        if chunk.get("pdf_page") is not None
    }
    mentioned_pages = re.findall(r"(?i)(?:página|pdf p\.)\s*(\d+)", markdown)
    if any(page not in allowed_pages for page in mentioned_pages):
        raise ValueError("invented_page")
    if not any(evidence_id in markdown for evidence_id in allowed):
        raise ValueError("missing_markdown_evidence_id")
    return markdown, normalized_claims


async def render_grounded_answer(
    original_query: str,
    filters: dict[str, Any],
    chunks: list[dict[str, Any]],
    *,
    simulate_failure: bool,
    normalization: HebrewSearchNormalization | None = None,
) -> tuple[str, list[dict[str, Any]], bool]:
    if simulate_failure:
        raise RuntimeError("simulated_ai_render_failure")
    if not LITELLM_API_KEY:
        raise RuntimeError("litellm_key_missing")
    prompt = (
        "Respondé únicamente usando las fuentes proporcionadas. Conservá la pregunta "
        "original. Si la relación es directa, decilo; si es mediada, explicá la cadena; "
        "si es temática, marcala como temática. No inventes citas, páginas, obras ni "
        "referencias. Cada afirmación importante debe incluir evidence_ids. Diferenciá "
        "cita literal de interpretación. No copies citas textuales en la respuesta: "
        "parafraseá y remití al evidence_id para que el backend muestre el Markdown "
        "canónico. Si las fuentes no alcanzan, decilo claramente. Respondé en el idioma "
        "del usuario. No uses conocimiento externo. Devolvé JSON con answer_markdown y "
        "claims. Cada claim: claim_id, text, "
        "evidence_ids, relation_type (direct|mediated|thematic|none), confidence "
        "(high|medium|low). Escribí como máximo 350 palabras y 3 claims. Todos los "
        "claims deben tener al menos un evidence_id exacto del paquete."
        " Respondé en el idioma indicado por filtros.query_language."
        " answer_markdown debe incluir al menos un evidence_id exacto entre "
        "corchetes para que la cita sea visible."
        " Si filtros.query_shape es short_proper_name, explicá únicamente el "
        "contexto de la mención nominal mejor rankeada, priorizá "
        "english_name_exact/normalized sobre fuentes semánticas, e indicá obra, "
        "página y evidence_id. No conviertas el nombre en una pregunta relacional "
        "ni agregues biografía externa."
        " Para hebreo, no afirmes que una frase no existe en el corpus: solo que "
        "no aparece en las fuentes recuperadas. No uses semantic_only como prueba "
        "literal. Si aparece exacta o normalizada, indicá obra, sección y página."
    )
    context_pack = _context_pack(original_query, filters, chunks, normalization)
    allowed_ids = [chunk["evidence_id"] for chunk in chunks]
    last_error: Exception | None = None
    async with httpx.AsyncClient(timeout=LITELLM_TIMEOUT_SECONDS) as client:
        for attempt in range(2):
            repair = (
                ""
                if attempt == 0
                else (
                    "\nREINTENTO DE VALIDACIÓN: la salida anterior fue rechazada. "
                    "Usá solamente estos IDs exactos, no dejes evidence_ids vacío "
                    "e incluí al menos uno literalmente en answer_markdown: "
                    + ", ".join(allowed_ids)
                )
            )
            try:
                response = await client.post(
                    f"{LITELLM_BASE_URL}/v1/chat/completions",
                    headers={"Authorization": f"Bearer {LITELLM_API_KEY}"},
                    json={
                        "model": RESEARCH_CONVERSATION_MODEL,
                        "messages": [
                            {"role": "system", "content": prompt + repair},
                            {"role": "user", "content": context_pack},
                        ],
                        "temperature": 0,
                        "max_tokens": 1200,
                        "response_format": {"type": "json_object"},
                    },
                )
                response.raise_for_status()
                value = json.loads(
                    response.json()["choices"][0]["message"]["content"]
                )
                markdown, claims = validate_grounded_answer(value, chunks)
                return markdown, claims, True
            except Exception as exc:
                last_error = exc
    assert last_error is not None
    raise last_error


def _fallback_answer(chunks: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    lines = [
        "## Fuentes recuperadas",
        "",
        "La redacción automática no estuvo disponible. Se muestran las fuentes recuperadas.",
    ]
    for chunk in chunks[:5]:
        location = f"PDF p. {chunk['pdf_page']}" if chunk.get("pdf_page") is not None else "página no disponible"
        excerpt = " ".join(str(chunk.get("markdown") or "").split())[:500]
        lines.extend([
            "",
            f"### {chunk['work']} — {location}",
            f"> {excerpt}",
            f"Evidence ID: `{chunk['evidence_id']}`",
        ])
    ids = [chunk["evidence_id"] for chunk in chunks[:3]]
    claims = [{
        "claim_id": "sources_recovered",
        "text": "Se recuperaron fuentes canónicas relevantes; no se generó una interpretación automática.",
        "strength": "weak",
        "confidence": "low",
        "relation_type": "none",
        "evidence_ids": ids,
        "primary_evidence_id": ids[0],
    }] if ids else []
    return "\n".join(lines), claims


def _frontend_hit(chunk: dict[str, Any], primary_ids: set[str]) -> dict[str, Any]:
    evidence_id = chunk["evidence_id"]
    markdown = str(chunk.get("markdown") or "")
    language = chunk.get("language") if chunk.get("language") in {"es", "en", "he"} else "es"
    match_type = str(chunk.get("literal_match_type") or "semantic_only")
    literal = match_type != "semantic_only" and float(chunk.get("literal_score") or 0.0) > 0
    return {
        "hit_id": evidence_id,
        "evidence_id": evidence_id,
        "chunk_id": str(chunk["chunk_id"]),
        "content_node_id": (
            str(chunk["content_node_id"])
            if chunk.get("content_node_id")
            else None
        ),
        "page_anchor_id": (
            str(chunk["page_anchor_id"])
            if chunk.get("page_anchor_id")
            else None
        ),
        "document_id": str(chunk["document_id"]),
        "work_code": _work_code(chunk),
        "work_title": str(chunk.get("work") or ""),
        "pdf_page": chunk.get("pdf_page"),
        "physical_pdf_page": chunk.get("pdf_page"),
        "printed_page": (
            int(chunk["printed_page"])
            if str(chunk.get("printed_page") or "").isdigit()
            else None
        ),
        "section": chunk.get("section"),
        "quote": markdown,
        "snippet": " ".join(markdown.split())[:900],
        "display_snippet": " ".join(markdown.split())[:900],
        "match_text": "",
        "sentence_text": "",
        "paragraph_text": markdown,
        "context_before": "",
        "context_after": "",
        "language": language,
        "direction": "rtl" if language == "he" else "ltr",
        "evidence_type": "canonical_markdown",
        "literal_strength": "strong" if literal else "weak",
        "evidence_strength": "strong" if evidence_id in primary_ids else "medium",
        "relation_relevance": "direct_relation" if literal else "thematic_parallel",
        "relation_type": "direct_literal" if literal else "thematic_parallel",
        "relation_strength": "high" if literal else "medium",
        "literal_relation": literal,
        "inference_required": not literal,
        "matched_terms": list(chunk.get("matched_terms") or []),
        "matched_concepts": [],
        "is_primary": evidence_id in primary_ids,
        "source_layer": _source_layer(chunk),
        "source_layer_confidence": "medium",
        "source_layer_rationale": "canonical_chunk_metadata",
        "is_original_language": True,
        "is_primary_language_match": language == chunk.get("query_language"),
        "is_translation": False,
        "is_editorial_commentary": _source_layer(chunk) == "editorial_commentary",
        "parallel_texts": [],
        "language_match": "exact" if language == chunk.get("query_language") else "secondary",
        "literal_match_kind": (
            "normalized"
            if match_type in {"hebrew_exact_normalized", "english_name_variant"}
            else "exact_phrase" if chunk.get("exact_match") else "semantic"
        ),
        "match_kind": match_type,
        "retrieval_tier": 0 if literal else 1,
        "retrieval_sources": chunk.get("retrieval_sources", []),
        "semantic_score": chunk.get("semantic_score"),
        "literal_score": chunk.get("literal_score"),
        "combined_score": chunk.get("combined_score"),
        "warnings": (
            ["test_candidate_read_only: no constituye promoción productiva"]
            if chunk.get("document_status") == "test_candidate"
            else []
        ),
        "physical_file_name": chunk.get("physical_file_name"),
        "source_sha256": chunk.get("source_sha256"),
        "author_quote_status": "not_confirmed",
        "attribution_label": "Markdown canónico recuperado desde PostgreSQL",
        "raw_snippet": markdown,
        "snippet_sanitized": False,
        "sanitization_reason_codes": [],
    }


async def run_simple_rag(
    conn: Any,
    data: Any,
    *,
    simulations: dict[str, bool] | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    simulations = simulations or {}
    original_query = data.question
    filters = build_explicit_filters(data)
    english_name_query = detect_short_english_name_query(original_query)
    query_language = detect_research_query_language(
        original_query,
        english_name_query,
    )
    if query_language == "en" and english_name_query is not None:
        filters["languages"] = list(dict.fromkeys([
            "en",
            *filters["languages"],
        ]))
    filters["query_language"] = query_language
    warnings: list[str] = []
    normalization_status = "not_needed"
    try:
        normalization = (
            normalize_hebrew_for_search(original_query)
            if query_language == "he" and has_hebrew(original_query)
            else None
        )
        if normalization:
            normalization_status = "ok"
    except Exception:
        normalization = None
        normalization_status = "failed"
        warnings.append(
            "La normalización hebrea no estuvo disponible; se conservaron la "
            "consulta original y las búsquedas de respaldo."
        )
    variants = build_query_variants(original_query)
    if english_name_query:
        filters["query_shape"] = "short_proper_name"
    latency: dict[str, float] = {}

    documents = await resolve_ready_documents(
        conn,
        knowledge_scope_code=filters["scope"],
        work_codes=filters["works"] or None,
        include_test_candidates=filters["include_test_candidates"],
    )
    document_ids = [str(item["document_id"]) for item in documents]
    semantic_task = asyncio.create_task(asyncio.to_thread(
        _semantic_search_variants,
        original_query,
        normalized_query=(
            normalization.without_niqqud
            if normalization and normalization.without_niqqud != original_query
            else None
        ),
        scope_code=filters["scope"],
        languages=filters["languages"],
        document_ids=document_ids if filters["works"] else [],
        simulate_failure=bool(simulations.get("milvus")),
    ))

    literal_started = time.perf_counter()
    literal_status = "ok"
    try:
        if simulations.get("literal"):
            raise RuntimeError("simulated_literal_failure")
        literal_variants = (
            variants[:2] if english_name_query is not None else variants
        )
        literal = await search_literal_candidates(
            conn,
            knowledge_scope_code=filters["scope"],
            variants=literal_variants,
            languages=filters["languages"],
            document_ids=document_ids if filters["works"] else None,
            top_k=LITERAL_TOP_K,
            hebrew_compact=normalization.compact_letters if normalization else "",
            hebrew_fallback_compacts=(
                [
                    "".join(normalization.tokens[index:index + 2])
                    for index in range(len(normalization.tokens) - 1)
                ]
                if normalization
                else []
            ),
            include_test_candidates=filters["include_test_candidates"],
        )
        if (
            english_name_query is not None
            and len(variants) > len(literal_variants)
            and not any(item.get("exact_match") for item in literal)
        ):
            literal = await search_literal_candidates(
                conn,
                knowledge_scope_code=filters["scope"],
                variants=variants,
                languages=filters["languages"],
                document_ids=document_ids if filters["works"] else None,
                top_k=LITERAL_TOP_K,
                include_test_candidates=filters["include_test_candidates"],
            )
    except Exception:
        literal = []
        literal_status = "failed"
        warnings.append("La búsqueda literal no estuvo disponible; se utilizó recuperación semántica.")
    latency["literal_ms"] = round((time.perf_counter() - literal_started) * 1000, 2)

    semantic_status = "ok"
    embedding_metadata: dict[str, Any] = {}
    try:
        semantic, embedding_metadata = await semantic_task
    except Exception:
        semantic = []
        semantic_status = "failed"
        warnings.append("La búsqueda semántica no estuvo disponible; se utilizó búsqueda literal.")
    latency["embedding_and_milvus_ms"] = float(embedding_metadata.get("latency_ms") or 0.0)

    ranked = merge_results(
        semantic,
        literal,
        query_language=query_language,
        english_name_query=english_name_query,
    )
    fetch_started = time.perf_counter()
    canonical = await fetch_canonical_chunks(
        conn,
        knowledge_scope_code=filters["scope"],
        chunk_ids=[item["chunk_id"] for item in ranked],
        include_test_candidates=filters["include_test_candidates"],
    )
    latency["fetch_chunks_ms"] = round((time.perf_counter() - fetch_started) * 1000, 2)
    canonical_by_id = {str(item["chunk_id"]): item for item in canonical}
    selected = select_context(
        ranked,
        canonical_by_id,
        explicit_work_filter=bool(filters["works"]),
    )
    if english_name_query is not None:
        exact_name_chunks = [
            chunk
            for chunk in selected
            if chunk.get("literal_match_type") == "english_name_exact"
        ]
        if exact_name_chunks:
            selected = exact_name_chunks[:4]
    for chunk in selected:
        chunk["evidence_id"] = _evidence_id(str(chunk["chunk_id"]))
        chunk["canonical_pdf_page_start"] = chunk.get("pdf_page")
        chunk["pdf_page"] = _match_local_pdf_page(chunk)
        if normalization:
            chunk["matched_terms"] = list(normalization.tokens)
            chunk.setdefault("literal_match_type", "semantic_only")
        elif english_name_query:
            chunk["matched_terms"] = list(english_name_query.nominal_tokens)
            chunk.setdefault("literal_match_type", "semantic_only")
    if any(chunk.get("document_status") == "test_candidate" for chunk in selected):
        warnings.append(
            "test_candidate_read_only: fuente DEV; no constituye promoción productiva"
        )

    retrieval_failed = semantic_status == "failed" and literal_status == "failed"
    canonical_missing = bool(ranked) and not canonical
    if not selected:
        if retrieval_failed or canonical_missing:
            research_status = "degraded"
            answer = (
                "No fue posible completar correctamente la búsqueda por un "
                "problema técnico. "
                "No se concluye que el corpus carezca de evidencia."
            )
            if canonical_missing:
                warnings.append(
                    "Se recuperaron IDs, pero PostgreSQL no entregó el contenido "
                    "canónico correspondiente."
                )
        else:
            research_status = "no_evidence"
            answer = "No se encontró evidencia suficiente en el corpus consultado."
        claims: list[dict[str, Any]] = []
        ai_status = "not_run"
        ai_used = False
    else:
        ai_started = time.perf_counter()
        try:
            render_options: dict[str, Any] = {
                "simulate_failure": bool(simulations.get("ai_render")),
            }
            if normalization:
                render_options["normalization"] = normalization
            answer, claims, ai_used = await render_grounded_answer(
                original_query,
                filters,
                selected,
                **render_options,
            )
            ai_status = "ok"
        except Exception as exc:
            logger.warning(
                "simple_rag grounded render rejected: %s",
                type(exc).__name__,
                exc_info=True,
            )
            answer, claims = _fallback_answer(selected)
            ai_status = "failed"
            ai_used = False
            warnings.append(
                "La redacción automática no estuvo disponible. Se muestran las fuentes recuperadas."
            )
            warnings.append(f"ai_render_failed:{type(exc).__name__}")
        latency["ai_ms"] = round((time.perf_counter() - ai_started) * 1000, 2)
        research_status = (
            "complete"
            if (
                semantic_status == literal_status == ai_status == "ok"
                and normalization_status != "failed"
            )
            else "degraded"
        )
        exact_literal_answer = bool(selected) and (
            (
                english_name_query is not None
                and selected[0].get("literal_match_type") == "english_name_exact"
            )
            or selected[0].get("literal_match_type") == "hebrew_exact_normalized"
        )
        if (
            research_status == "complete"
            and len(selected) < CONTEXT_MIN
            and not exact_literal_answer
        ):
            research_status = "partial"

    primary_eligible_ids = {
        chunk["evidence_id"]
        for chunk in selected
        if _is_primary_eligible(
            chunk,
            query_language=query_language,
            english_name_query=english_name_query,
        )
    }
    if query_language == "he" or english_name_query is not None:
        best_primary_id = next((
            chunk["evidence_id"]
            for chunk in selected
            if chunk["evidence_id"] in primary_eligible_ids
        ), None)
        grounded_claims = []
        for claim in claims:
            eligible = [
                evidence_id
                for evidence_id in claim.get("evidence_ids", [])
                if evidence_id in primary_eligible_ids
            ]
            if not eligible:
                continue
            if best_primary_id:
                claim["evidence_ids"] = list(dict.fromkeys([
                    best_primary_id,
                    *claim.get("evidence_ids", []),
                ]))
                claim["primary_evidence_id"] = best_primary_id
            else:
                claim["primary_evidence_id"] = eligible[0]
            grounded_claims.append(claim)
        claims = grounded_claims
    primary_ids = list(dict.fromkeys(
        claim["primary_evidence_id"]
        for claim in claims
        if claim.get("primary_evidence_id") in primary_eligible_ids
    ))
    if (query_language == "he" or english_name_query is not None) and primary_ids:
        primary_ids = [
            chunk["evidence_id"]
            for chunk in selected
            if chunk["evidence_id"] in primary_eligible_ids
        ][:1]
    if not primary_ids and selected:
        primary_ids = [
            chunk["evidence_id"]
            for chunk in selected
            if chunk["evidence_id"] in primary_eligible_ids
        ][:1]
    if (
        (query_language == "he" or english_name_query is not None)
        and selected
        and not primary_ids
        and research_status == "complete"
    ):
        research_status = "partial"
    primary_match_type = next((
        chunk.get("literal_match_type")
        for chunk in selected
        if chunk["evidence_id"] in primary_ids
    ), None)
    if (
        primary_match_type == "english_name_variant"
        and research_status == "complete"
    ):
        research_status = "partial"
        warnings.append(
            "Se recuperó una variante ortográfica aproximada del nombre; "
            "la equivalencia editorial no se afirma como exacta."
        )
    hits = [_frontend_hit(chunk, set(primary_ids)) for chunk in selected]
    evidence = [{
        "evidence_id": chunk["evidence_id"],
        "chunk_id": str(chunk["chunk_id"]),
        "document_id": str(chunk["document_id"]),
        "work": chunk["work"],
        "title": chunk["work"],
        "pdf_page": chunk.get("pdf_page"),
        "printed_page": chunk.get("printed_page"),
        "section": chunk.get("section"),
        "language": chunk.get("language"),
        "markdown": chunk.get("markdown"),
        "source_layer": _source_layer(chunk),
        "attribution_status": "not_confirmed",
        "semantic_score": chunk.get("semantic_score"),
        "literal_score": chunk.get("literal_score"),
        "combined_score": chunk.get("combined_score"),
        "retrieval_sources": chunk.get("retrieval_sources"),
        "literal_match_type": chunk.get("literal_match_type", "semantic_only"),
        "content_node_id": (
            str(chunk["content_node_id"])
            if chunk.get("content_node_id")
            else None
        ),
    } for chunk in selected]
    compatibility_status = {
        "complete": "ok",
        "partial": "partial",
        "degraded": "partial",
        "no_evidence": "no_evidence",
    }[research_status]
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    latency["total_ms"] = duration_ms
    request_id = hashlib.sha256(f"{time.time_ns()}:{original_query}".encode()).hexdigest()[:16]
    logger.info(
        "simple_rag request_id=%s original_query_hash=%s query_language=%s "
        "normalization_applied=%s artificial_spacing_detected=%s "
        "query_shape=%s filters=%s milvus_status=%s literal_status=%s "
        "milvus_hits=%s literal_hits=%s selected_chunks=%s "
        "primary_match_type=%s matched_tokens=%s selected_primary=%s "
        "ai_status=%s fallback=%s latency_ms=%s",
        request_id,
        hashlib.sha256(original_query.encode()).hexdigest(),
        query_language,
        normalization is not None,
        bool(normalization and normalization.artificial_spacing_detected),
        "short_proper_name" if english_name_query else "general",
        filters,
        semantic_status,
        literal_status,
        len(semantic),
        len(literal),
        len(selected),
        primary_match_type,
        list(english_name_query.nominal_tokens) if english_name_query else [],
        bool(primary_ids),
        ai_status,
        research_status == "degraded",
        latency,
    )
    matrix = [
        {
            "work_code": work,
            "hits": sum(hit["work_code"] == work for hit in hits),
            "primary_hits": sum(
                hit["work_code"] == work and hit["is_primary"] for hit in hits
            ),
            "contextual_hits": sum(
                hit["work_code"] == work and not hit["is_primary"] for hit in hits
            ),
            "additional_literal_hits": 0,
        }
        for work in dict.fromkeys(hit["work_code"] for hit in hits)
    ]
    return {
        "pipeline": "simple_rag",
        "status": compatibility_status,
        "research_status": research_status,
        "original_query": original_query,
        "question": original_query,
        "answer_text": answer,
        "answer_markdown": answer,
        "summary": (
            f"{len(primary_ids)} fuentes principales y {max(0, len(hits) - len(primary_ids))} contextuales."
            if hits else ""
        ),
        "claims": claims,
        "evidence": evidence,
        "hits": hits,
        "primary_evidence_ids": primary_ids,
        "evidence_counts": {
            "primary": len(primary_ids),
            "contextual": max(0, len(hits) - len(primary_ids)),
            "additional_literal": 0,
        },
        "retrieval": {
            "semantic_used": bool(semantic),
            "literal_used": bool(literal),
            "semantic_status": semantic_status,
            "literal_status": literal_status,
            "semantic_hits": len(semantic),
            "literal_hits": len(literal),
            "selected_chunks": len(selected),
            "query_language": query_language,
            "query_shape": (
                "short_proper_name" if english_name_query else "general"
            ),
            "query_variants": variants,
            "normalization": ({
                "without_niqqud": normalization.without_niqqud,
                "tokens": list(normalization.tokens),
                "artificial_spacing_detected": normalization.artificial_spacing_detected,
                "rtl_controls_removed": normalization.rtl_controls_removed,
            } if normalization else None),
            "primary_match_type": primary_match_type,
            "matched_tokens": (
                list(english_name_query.nominal_tokens)
                if english_name_query
                else []
            ),
        },
        "processing": {
            "ai_interpretation_used": False,
            "ai_render_used": ai_used,
            "fallback_used": research_status == "degraded",
            "normalization_applied": normalization is not None,
            "normalization_status": normalization_status,
        },
        "execution": {
            "pipeline_version": "simple_grounded_rag_v1",
            "model": RESEARCH_CONVERSATION_MODEL,
            "embedding_model": EMBEDDINGS_MODEL_ALIAS,
            "embedding_dimension": embedding_metadata.get("dimension"),
            "used_ai_interpretation": False,
            "used_ai_rendering": ai_used,
            "used_deterministic_fallback": not ai_used and bool(selected),
            "used_vector": bool(semantic),
            "retrieval_modes": ["milvus", "literal", "fts", "trigram"],
            "duration_ms": duration_ms,
            "latency_ms": latency,
            "request_id": request_id,
        },
        "conversation": {
            "conversation_id": data.conversation.get("conversation_id"),
            "turn_id": data.conversation.get("turn_id"),
            "resolved_context": [],
        },
        "works_consulted": list(dict.fromkeys(hit["work_code"] for hit in hits)),
        "evidence_matrix": matrix,
        "cross_corpus_matrix": [],
        "relations": [],
        "not_found": [] if selected else [original_query],
        "warnings": list(dict.fromkeys(warnings)),
        "query_understanding": {
            "original_query": original_query,
            "intent": "unknown",
            "operation": "simple_grounded_retrieval",
            "subject_type": "query",
            "subject_raw": original_query,
            "subject_canonical": original_query,
            "ai_used": False,
            "ai_accepted": False,
            "fallback_used": False,
            "requires_clarification": False,
        },
    }
