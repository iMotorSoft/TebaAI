"""Grounded conversational investigative QA; corpus evidence is authoritative."""
from __future__ import annotations

import json
import re
import time
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

import httpx
from pydantic import BaseModel, Field

from globalVar import (
    LITELLM_API_KEY,
    LITELLM_BASE_URL,
    LITELLM_TIMEOUT_SECONDS,
    RESEARCH_CONVERSATION_MODEL,
)
from modules.library.concept_catalog import get_concept
from modules.library.investigative_model import stable_hash
from modules.library.hebrew_lexical_normalizer import (
    HebrewLiteralQuery,
    extract_literal_segments,
    normalize_hebrew_search,
    reconstruct_pdf_spaced_hebrew,
)
from modules.library.editorial_source_layer import (
    SOURCE_LAYERS,
    SourceLayer,
    classify_source_layer,
    literal_context,
    source_layer_priority,
)
from modules.library.hebrew_pdf_layout import readable_pdf_block
from modules.library.text_quality import (
    sanitize_evidence_snippet,
    build_summary,
    singular_plural,
)
from modules.library.multilingual_query import (
    QueryInterpretation,
    deterministic_interpret,
    interpret_query,
    preprocess_query,
)
from modules.library.named_topics import (
    NamedTopicResolution,
    load_named_topic_glossary,
    named_topic_retrieval_plan,
    normalize_named_topic_candidate,
    resolve_named_topic,
)
from modules.library.query_resolution import (
    build_suggestion_contract,
    resolve_query,
)

WORKS = {"kitzur", "lmi", "lmii", "lh", "lm_xv", "potencia_plegaria"}
WORK_TITLES = {
    "kitzur": "Kitzur",
    "lmi": "Likutey Moharán I — edición española BRI",
    "lmii": "Likutey Moharán II",
    "lh": "Likutey Halajot",
    "lm_xv": "Likutey Moharán XV KDP",
    "potencia_plegaria": "La Potencia de la Plegaria",
}
RELATION_RELEVANCE = {
    "direct_relation",
    "same_fragment_both_terms",
    "same_page_both_terms",
    "same_section_relation",
    "single_term_literal",
    "thematic_parallel",
    "inferred_relation",
    "unrelated_literal_noise",
}
RELATION_PRIORITY = {
    "direct_relation": 0,
    "same_fragment_both_terms": 1,
    "same_section_relation": 2,
    "same_page_both_terms": 3,
    "thematic_parallel": 4,
    "inferred_relation": 5,
    "single_term_literal": 6,
    "unrelated_literal_noise": 7,
}
LANGUAGE_TIER = {"he": 0, "es": 1, "en": 2}
STOP_WORDS = {
    "cual", "cuál", "como", "cómo", "donde", "dónde", "aparece", "aparecen",
    "relacion", "relación", "entre", "sobre", "dice", "dicen", "algo", "alguna",
    "what", "where", "between", "relation", "relationship", "about", "the", "una",
    "uno", "el", "la", "es", "is", "para", "por", "con", "del", "las", "los", "que", "hay", "tambien",
    "termino", "término", "term",
    "does", "can", "could", "would", "should", "will", "shall", "may", "might",
    "this", "that", "these", "those", "its", "has", "have", "had", "been",
    "was", "were", "are", "being", "very", "much", "many", "some", "any",
    "each", "every", "own", "same", "both", "all", "most", "few", "more",
}
HEBREW_STOP_WORDS = {
    "את", "וה", "ו", "ה", "ש", "של", "כי", "יש", "לא", "אם",
    "זה", "זו", "אלה", "הוא", "היא", "הם", "הן", "אנחנו",
    "אני", "אתה", "אתן", "אתם", "על", "אל", "מן", "עם",
    "לו", "לה", "להם", "להן", "לי", "לך", "לנו", "לכם",
    "בן", "בין", "כמו", "כן", "אז", "עוד", "רק", "אך",
}
HEBREW_LETTER_RE = re.compile(r"[\u0590-\u05ff]")
HEBREW_WORD_RE = re.compile(r"[\u0590-\u05ff]{2,}")
LATIN_LETTER_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]")
PHRASE_DELIM_RE = re.compile(r"[\u0590-\u05ff]{4,}(?:\s+[\u0590-\u05ff]{2,})+")
ALIASES: dict[str, tuple[str, ...]] = {
    "plegaria": ("plegaria", "oración", "rezar", "rezo", "tefilá", "tefila"),
    "hitbodedut": ("hitbodedut", "aislamiento", "plegaria personal"),
    "miedo": ("miedo", "temor", "temor reverencial"),
    "temor": ("temor", "miedo", "temor reverencial"),
    "fear": ("fear", "awe", "miedo", "temor", "temor reverencial", "יראה", "פחד"),
    "fe": ("fe", "emuná", "emuna"),
    "tristeza": ("tristeza", "melancolía", "melancolia"),
    "alegría": ("alegría", "alegria", "simjá", "simja"),
    "habla": ("habla", "hablar", "palabra", "palabras", "lenguaje", "voz"),
    "alma": ("alma", "neshamá", "neshama"),
    "sangre": ("sangre", "sanguínea", "sanguinea"),
    "deseo": ("deseo", "anhelo", "lujuria", "lujurioso"),
    "pureza": ("pureza", "purificación", "purificacion"),
    "rabí natán": ("rabí natán", "rabi natan", "reb noson", "rabí noson"),
    "rebe najmán": ("rebe najmán", "rebe najman", "rabí najmán", "rabi najman"),
    "zohar": ("zohar", "zóhar"),
    "torá": ("torá", "tora", "torah"),
    "notas": ("nota", "notas", "fuente"),
    "lágrimas": ("lágrimas", "lagrimas", "llorar", "llanto"),
    "escorpión": ("escorpión", "escorpion", "escorpiones", "עקרב", "עקרבים", "עַקְרַב"),
}


AuthorQuoteStatus = Literal[
    "confirmed_author_text",
    "confirmed_translated_author_text",
    "editorial_paraphrase",
    "editorial_commentary",
    "translator_note",
    "footnote_reference",
    "not_confirmed",
    "not_applicable",
]

ATTRIBUTION_LABELS: dict[str, str] = {
    "confirmed_author_text": "Cita textual del autor confirmada",
    "confirmed_translated_author_text": "Traducción del texto original del autor",
    "editorial_paraphrase": "Paráfrasis editorial",
    "editorial_commentary": "Comentario editorial",
    "translator_note": "Nota del traductor",
    "footnote_reference": "Referencia en nota al pie",
    "not_confirmed": "No confirmada como formulación textual del autor original",
    "not_applicable": "No corresponde atribución al autor",
}

AUTHOR_QUOTE_MAP: dict[str, AuthorQuoteStatus] = {
    "rebbe_lesson_text": "confirmed_author_text",
    "biblical_quote_in_lesson": "confirmed_author_text",
    "rabbinic_quote_in_lesson": "confirmed_author_text",
    "editorial_translation": "confirmed_translated_author_text",
    "editorial_commentary": "editorial_commentary",
    "editorial_note": "editorial_commentary",
    "footnote": "footnote_reference",
    "source_reference": "not_applicable",
    "section_heading": "not_applicable",
    "page_heading": "not_applicable",
    "introduction": "editorial_commentary",
    "unknown": "not_confirmed",
}


class QaAi(BaseModel):
    enabled: bool = True
    model: str = "gpt-5.4-nano"


class QaRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    phase: Literal["legacy", "interpret", "analyze"] = "legacy"
    interpretation_id: str | None = Field(default=None, max_length=100)
    supersedes_interpretation_id: str | None = Field(default=None, max_length=100)
    idempotency_key: str | None = Field(default=None, max_length=100)
    works: list[str] = Field(default_factory=lambda: sorted(WORKS))
    languages: list[Literal["es", "en", "he"]] = Field(default_factory=lambda: ["es", "he", "en"])
    include_thematic: bool = True
    include_audit: bool = False
    min_evidence: Literal["literal", "strong", "medium", "weak"] = "literal"
    max_hits_per_work: int = Field(default=10, ge=1, le=20)
    return_markdown: bool = True
    return_json: bool = True
    ai: QaAi = Field(default_factory=QaAi)
    conversation: dict = Field(default_factory=dict)


class ParallelText(BaseModel):
    language: Literal["es", "en", "he"]
    source_layer: SourceLayer
    text: str
    linked_to_evidence_id: str
    link_type: Literal["parallel_translation"]
    physical_pdf_page: int | None = None
    printed_page: int | None = None


class Hit(BaseModel):
    hit_id: str
    work_code: str
    work_title: str
    pdf_page: int | None = None
    printed_page: int | None = None
    quote: str
    snippet: str = ""
    display_quote: str | None = None
    display_snippet: str | None = None
    display_normalization: str | None = None
    source_view: str
    search_record_type: str
    source_layer: SourceLayer
    source_layer_confidence: Literal["high", "medium", "low"] = "low"
    source_layer_rationale: str = "insufficient_structural_evidence"
    zone_type: str | None = None
    note_number: str | None = None
    surface_form: str | None = None
    normalized_reference_name: str | None = None
    matched_terms: list[str]
    matched_concepts: list[str] = Field(default_factory=list)
    evidence_type: str
    literal_strength: Literal["strong", "medium", "weak"] = "strong"
    evidence_strength: Literal["strong", "medium", "weak", "insufficient"]
    relation_relevance: Literal[
        "direct_relation", "same_fragment_both_terms", "same_page_both_terms",
        "same_section_relation", "single_term_literal", "thematic_parallel",
        "inferred_relation", "unrelated_literal_noise",
    ] = "single_term_literal"
    relation_level: Literal["literal", "contextual", "thematic"] = "literal"
    is_primary: bool = False
    language_match: Literal["exact", "primary", "secondary", "fallback"] = "fallback"
    literal_match_kind: Literal[
        "none", "exact_phrase", "normalized", "no_niqqud", "single_term", "semantic",
        "named_topic_exact", "named_topic_normalized", "named_topic_alias",
        "named_topic_translation", "named_topic_hebrew_equivalent", "named_topic_partial",
    ] = "none"
    match_kind: str = "none"
    direct_support: bool = False
    match_strength: Literal["strong", "medium", "weak", "insufficient"] = "insufficient"
    single_term: bool = True
    canonical_topic_id: str | None = None
    matched_variant: str | None = None
    match_language: str | None = None
    match_script: Literal["Latin", "Hebrew"] | None = None
    retrieval_tier: int = 99
    warnings: list[str] = Field(default_factory=list)
    document_id: str | None = None
    physical_file_name: str | None = None
    source_sha256: str | None = None
    page_anchor_id: str | None = None
    section: str | None = None
    retrieval_position: int | None = None
    physical_pdf_page: int | None = None
    match_text: str = ""
    sentence_text: str = ""
    paragraph_text: str = ""
    context_before: str = ""
    context_after: str = ""
    language: Literal["es", "en", "he"] = "es"
    direction: Literal["ltr", "rtl"] = "ltr"
    source_original_language: Literal["es", "en", "he", "unknown"] = "unknown"
    is_original_language: bool = False
    is_primary_language_match: bool = False
    is_translation: bool = False
    is_editorial_commentary: bool = False
    parent_zone_id: str | None = None
    content_node_id: str | None = None
    evidence_id: str | None = None
    page_anchor_kind: str | None = None
    ingestion_run_id: str | None = None
    parallel_texts: list[ParallelText] = Field(default_factory=list)
    author_quote_status: AuthorQuoteStatus = "not_confirmed"
    attribution_label: str = "Coincidencia literal en la edición"
    raw_snippet: str = ""
    snippet_sanitized: bool = False
    sanitization_reason_codes: list[str] = Field(default_factory=list)


def language(question: str) -> str:
    if re.search(r"[\u0590-\u05ff]", question):
        return "he"
    return "en" if re.search(r"\b(where|what|prayer|fear|joy|faith)\b", question, re.I) else "es"


def _fold(value: str) -> str:
    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().casefold()


def _clean_concept(value: str) -> str:
    words = re.findall(r"[\wáéíóúñÁÉÍÓÚÑ\u0590-\u05ff]+", value.casefold())
    return " ".join(word for word in words if word not in STOP_WORDS).strip()


def _extract_literal_phrases(question: str) -> list[dict]:
    """Detect Hebrew literal phrases within a mixed-language query."""
    analysis = extract_literal_segments(question)
    if analysis is None:
        return []
    search_text = analysis.literal_reconstructed
    phrases = []
    for match in re.finditer(r"[\u0590-\u05ff]{3,}(?:\s+[\u0590-\u05ff]{2,})+", search_text):
        phrase = match.group()
        words = [w for w in phrase.split() if len(w) >= 2 and w not in HEBREW_STOP_WORDS]
        if words:
            phrases.append({
                "text": phrase,
                "language": "he",
                "script": "Hebrew",
                "word_count": len(phrase.split()),
                "content_words": words,
            })
    if not phrases:
        hebrew_words = sorted(set(
            w for w in re.findall(r"[\u0590-\u05ff]+", search_text)
            if len(w) >= 3 and w not in HEBREW_STOP_WORDS
        ))
        if len(hebrew_words) >= 2:
            phrases.append({
                "text": " ".join(hebrew_words),
                "language": "he",
                "script": "Hebrew",
                "word_count": len(hebrew_words),
                "content_words": hebrew_words,
                "reconstructed": True,
            })
        elif hebrew_words:
            phrases.append({
                "text": hebrew_words[0],
                "language": "he",
                "script": "Hebrew",
                "word_count": 1,
                "content_words": hebrew_words,
                "single_word": True,
            })
    return phrases


def _normalized_token_segmentations(text: str, compact: str) -> list[str]:
    """Find exact token windows whose Hebrew letters equal a compact query."""
    words = [word for word in text.split() if re.search(r"[\u05d0-\u05ea]", word)]
    results: list[str] = []
    for start in range(len(words)):
        joined = ""
        selected: list[str] = []
        for word in words[start:start + 8]:
            letters = "".join(re.findall(r"[\u05d0-\u05ea]", word))
            if not letters:
                continue
            joined += letters
            selected.append(letters)
            if joined == compact:
                results.append(" ".join(selected))
                break
            if len(joined) >= len(compact):
                break
    return list(dict.fromkeys(results))


def _detect_interface_language(question: str) -> str:
    """Detect the user's primary language, ignoring Hebrew literal quotations."""
    non_hebrew = HEBREW_LETTER_RE.sub("", question).strip()
    return language(non_hebrew) if non_hebrew else "he"


def _analyze_query_language(question: str) -> dict:
    interface_lang = _detect_interface_language(question)
    literal_phrases = _extract_literal_phrases(question)
    has_hebrew = bool(literal_phrases) or bool(HEBREW_LETTER_RE.search(question))
    query_language = "he" if has_hebrew else interface_lang
    primary_retrieval_language = "he" if has_hebrew else interface_lang
    secondary_languages = ["es", "en", "he"]
    if primary_retrieval_language == "he":
        secondary_languages = ["es", "en"]
    elif primary_retrieval_language == "es":
        secondary_languages = ["he", "en"]
    else:
        secondary_languages = ["he", "es"]
    return {
        "interface_language": interface_lang,
        "query_language": query_language,
        "primary_retrieval_language": primary_retrieval_language,
        "literal_phrases": literal_phrases,
        "secondary_languages": [lang for lang in secondary_languages if lang != primary_retrieval_language],
    }


def classify_intent(question: str) -> Literal[
    "literal_lookup", "concept_lookup", "concept_cooccurrence", "relation_query",
    "translation_or_explanation", "reference_lookup", "follow_up", "book_scope_query",
    "source_request", "comparison_query", "unknown",
]:
    """Classify retrieval intent deterministically before optional AI wording."""
    return deterministic_interpret(preprocess_query(question), []).intent


def _hebrew_content_words(text: str) -> list[str]:
    words = re.findall(r"[\u0590-\u05ff]+", text)
    return [w for w in words if len(w) >= 2 and w not in HEBREW_STOP_WORDS]


def relation_concepts(question: str) -> list[dict[str, object]]:
    """Extract user-stated concepts; model expansions never become retrieval authority."""
    literal_phrases = _extract_literal_phrases(question)
    if literal_phrases:
        phrase = literal_phrases[0]
        words = phrase.get("content_words", [])
        if words:
            result = []
            if phrase.get("reconstructed") or phrase.get("single_word"):
                for word in words[:3]:
                    result.append({"label": word, "terms": [word]})
            else:
                result.append({"label": phrase["text"], "terms": [phrase["text"]]})
                for word in words[:3]:
                    if word not in [t for r in result for t in r["terms"]]:
                        result.append({"label": word, "terms": [word]})
            return result[:2]
    cleaned = question.strip(" ¿?")
    cleaned = re.sub(r"(?i)^.*?\b(?:relaci[oó]n|v[ií]nculo|comparaci[oó]n)\s+(?:entre|de)\s+", "", cleaned)
    parts = re.split(r"\s+(?:y|e|and|con)\s+", cleaned, maxsplit=1, flags=re.I)
    labels = [_clean_concept(part) for part in parts]
    labels = [label for label in labels if label]
    if len(labels) < 2:
        folded_cleaned = _fold(cleaned)
        multiword_alias = next(
            (alias for alias in ALIASES if " " in alias and _fold(alias) in folded_cleaned),
            None,
        )
        if multiword_alias:
            labels = [multiword_alias]
        else:
            tokens = [_clean_concept(token) for token in re.findall(r"[\wáéíóúñÁÉÍÓÚÑ\u0590-\u05ff]+", cleaned)]
            labels = [token for token in tokens if token][:2] or [_clean_concept(question)]
    result = []
    for label in labels[:2]:
        alias_key = next((key for key in ALIASES if _fold(key) == _fold(label)), label)
        variants = ALIASES.get(alias_key, (label,))
        result.append({"label": label, "terms": list(dict.fromkeys(variants))})
    return result


def _prior_relational_question(history: list[dict]) -> str | None:
    for item in reversed(history[-15:]):
        question = str(item.get("question", "")) if isinstance(item, dict) else ""
        if re.search(r"(?i)\b(relaci[oó]n|v[ií]nculo|compar| y | e | and )", question):
            return question
    return None


def _is_contextual_followup(question: str) -> bool:
    return bool(re.search(r"(?i)\b(mostr|fuente|principal|qu[eé] parte|eso|tambi[eé]n|literal|interpretaci[oó]n|impureza)\b", question))


def _mentioned_works(question: str) -> list[str]:
    folded = _fold(question)
    aliases = {
        "kitzur": ("kitzur",),
        "lmi": ("likutey moharan i", "likutey moharan 1"),
        "lmii": ("likutey moharan ii", "likutey moharan 2"),
        "lh": ("likutey halajot", "likutey halakhot"),
        "lm_xv": ("likutey moharan xv", "likutey moharan 15"),
        "potencia_plegaria": ("potencia de la plegaria",),
    }
    return [work for work, names in aliases.items() if any(name in folded for name in names)]


def terms(question: str) -> list[str]:
    return [term for concept in relation_concepts(question) for term in concept["terms"]][:20]


async def _ai_interpret(question: str, history: list[dict] | None = None) -> tuple[dict, list[str]]:
    concepts = relation_concepts(question)
    fallback = {
        "detected_language": language(question),
        "normalized_question": question,
        "concepts": [item["label"] for item in concepts],
        "requires_cross_corpus": True,
    }
    if not LITELLM_API_KEY:
        return fallback, ["ai_interpretation_fallback:litellm_key_missing"]
    try:
        async with httpx.AsyncClient(timeout=LITELLM_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{LITELLM_BASE_URL}/v1/chat/completions",
                headers={"Authorization": f"Bearer {LITELLM_API_KEY}"},
                json={
                    "model": RESEARCH_CONVERSATION_MODEL,
                    "messages": [
                        {"role": "system", "content": "Return JSON only: detected_language(es|en|he), normalized_question, requires_cross_corpus(boolean). Resolve follow-up references from the supplied question history, but do not add unrelated concepts and never provide citations."},
                        {"role": "user", "content": json.dumps({"question": question, "history": (history or [])[-15:]}, ensure_ascii=False)},
                    ],
                    "temperature": 0,
                    "max_tokens": 180,
                    "response_format": {"type": "json_object"},
                },
            )
        value = json.loads(response.json()["choices"][0]["message"]["content"])
        return {
            **fallback,
            "detected_language": value.get("detected_language", fallback["detected_language"]),
            "normalized_question": value.get("normalized_question", question),
            "requires_cross_corpus": bool(value.get("requires_cross_corpus", True)),
        }, []
    except Exception as exc:
        return fallback, [f"ai_interpretation_fallback:{type(exc).__name__}"]


def _lm_xv_location(header: str | None) -> tuple[int | None, str | None]:
    value = str(header or "")
    printed = re.search(r"(?m)^\s*(\d{1,4})\s*$", value)
    section = re.search(r"(?im)^\s*(LIKUTEY\s+MOHAR[ÁA]N\s+II\s+#\d+(?::\d+)?)\s*$", value)
    return (
        int(printed.group(1)) if printed else None,
        section.group(1) if section else None,
    )


def _hebrew_compact(value: str) -> str:
    return "".join(re.findall(r"[א-ת]", normalize_hebrew_search(value)))


def _compact_candidate(text: str, term: str) -> bool:
    """Cheap prefilter; a phrase may differ by one glyph, never by a rewrite."""
    haystack, needle = _hebrew_compact(text), _hebrew_compact(term)
    if not needle:
        return False
    if needle in haystack:
        return True
    if len(needle) < 8:
        return False
    return any(
        sum(left != right for left, right in zip(needle, haystack[offset:offset + len(needle)])) <= 1
        for offset in range(max(0, len(haystack) - len(needle) + 1))
    )


def _controlled_hebrew_context(text: str, term: str):
    context = literal_context(text, term)
    normalized = normalize_hebrew_search(term)
    if context is not None or " " in normalized:
        return context
    for token in re.findall(r"[\u0590-\u05ff\ufb1d-\ufb4f]+", text):
        candidate = normalize_hebrew_search(token)
        if candidate.startswith(normalized) and candidate[len(normalized):] in {"א", "י", "ים"}:
            return literal_context(text, token)
    return None


def _hebrew_number(value: str) -> int:
    scores = {"א": 1, "ב": 2, "ג": 3, "ד": 4, "ה": 5, "ו": 6, "ז": 7, "ח": 8, "ט": 9,
              "י": 10, "כ": 20, "ל": 30, "מ": 40, "נ": 50, "ס": 60, "ע": 70, "פ": 80, "צ": 90,
              "ק": 100, "ר": 200, "ש": 300, "ת": 400}
    return sum(scores.get(char, 0) for char in value)


def _scripture_reference(value: str) -> tuple[str, int, int] | None:
    hebrew = re.search(r"מלכים\s+א\s+([א-ת]+)\s+([א-ת]+)", normalize_hebrew_search(value))
    if hebrew:
        return "1_kings", _hebrew_number(hebrew.group(1)), _hebrew_number(hebrew.group(2))
    spanish = re.search(r"(?i)Reyes\s+1\s*,\s*(\d+)\s*:\s*(\d+)", value)
    if spanish:
        return "1_kings", int(spanish.group(1)), int(spanish.group(2))
    english = re.search(r"(?i)1\s+Kings\s+(\d+)\s*:\s*(\d+)", value)
    if english:
        return "1_kings", int(english.group(1)), int(english.group(2))
    return None


async def _fetch_lm_xv(conn, term: str, limit: int) -> list[tuple[dict, str, str]]:
    """Search validated LM XV zones through a Unicode-safe derived projection."""
    is_hebrew = bool(HEBREW_LETTER_RE.search(term))
    latin_filter = "" if is_hebrew else " AND coalesce(b.text,f.text_quote,'') ILIKE %s"
    row_limit = "" if is_hebrew else " LIMIT %s"
    async with conn.cursor() as cursor:
        await cursor.execute(
            """SELECT p.id::text page_anchor_id,p.document_id::text,p.source_run_id,
                      p.pdf_page,p.printed_page,p.text_hash,
                      b.id::text content_node_id,b.bbox,b.text block_text,
                      f.id::text parent_zone_id,f.zone_type,f.zone_role,
                      f.authority_level,f.text_quote,f.confidence,
                      s.document_part,s.evidence_quote,
                      d.source_filename physical_file_name,d.source_sha256,d.source_path
               FROM library_lm_xv_kdp_pages_v1 p
               JOIN library_documents d ON d.id=p.document_id
               JOIN library_lm_xv_kdp_structural_classifications_v1 s
                 ON s.document_id=p.document_id AND s.pdf_page=p.pdf_page
                AND s.source_run_id=p.source_run_id
               JOIN library_lm_xv_kdp_fine_zones_v1 f
                 ON f.document_id=p.document_id AND f.pdf_page=p.pdf_page
                AND f.source_run_id=p.source_run_id
               JOIN library_lm_xv_kdp_page_blocks_v1 b ON b.id=f.parent_block_id
               WHERE f.validation_status IN ('validated','candidate')
               """ + latin_filter + " ORDER BY p.pdf_page,f.block_index" + row_limit,
            () if is_hebrew else (f"%{term}%", max(limit * 4, 20)),
        )
        rows = await cursor.fetchall()
    results: list[tuple[dict, str, str]] = []
    normalized_term = normalize_hebrew_search(term)
    for source in rows:
        persisted = str(source.get("block_text") or source.get("text_quote") or "")
        if not is_hebrew and normalized_term not in normalize_hebrew_search(persisted):
            continue
        if is_hebrew and source.get("zone_type") != "main_text_hebrew":
            continue
        if is_hebrew and not _compact_candidate(persisted, term):
            continue
        canonical = readable_pdf_block(
            str(source["source_path"]), int(source["pdf_page"]), source.get("bbox")
        ) or persisted
        context = None
        if is_hebrew:
            context = literal_context(canonical, term)
            if context is None:
                continue
        printed, section = _lm_xv_location(source.get("evidence_quote"))
        decision = classify_source_layer(
            canonical,
            zone_type=source.get("zone_type"),
            zone_role=source.get("zone_role"),
            document_part=source.get("document_part"),
            matched_text=term,
        )
        row = dict(source)
        row.update({
            "printed_page": source.get("printed_page") or printed,
            "physical_pdf_page": source["pdf_page"],
            "quote": canonical,
            "record": source.get("zone_type") or "unknown",
            "zone": source.get("zone_type"),
            "note": None,
            "surface": None,
            "section": section,
            "source_layer": decision.source_layer,
            "source_layer_confidence": decision.confidence,
            "source_layer_rationale": decision.rationale,
            "match_context": context,
            "match_position": normalize_hebrew_search(canonical).find(normalized_term),
            "page_anchor_kind": "library_lm_xv_kdp_pages_v1",
        })
        reference = _scripture_reference(canonical) if decision.source_layer == "biblical_quote_in_lesson" else None
        parallels = []
        if reference:
            for candidate in rows:
                candidate_printed, candidate_section = _lm_xv_location(candidate.get("evidence_quote"))
                candidate_text = str(candidate.get("block_text") or candidate.get("text_quote") or "")
                if (
                    candidate.get("zone_type") == "main_text_spanish"
                    and abs(int(candidate["pdf_page"]) - int(source["pdf_page"])) <= 2
                    and candidate_section == section
                    and _scripture_reference(candidate_text) == reference
                ):
                    parallels.append({
                        "language": "es",
                        "source_layer": "editorial_translation",
                        "text": candidate_text,
                        "physical_pdf_page": int(candidate["pdf_page"]),
                        "printed_page": candidate.get("printed_page") or candidate_printed,
                    })
                    break
        row["parallel_candidates"] = parallels
        results.append((row, WORK_TITLES["lm_xv"], "library_lm_xv_kdp_fine_zones_v1"))
        if len(results) >= limit:
            break
    return results


async def _fetch_lmii_hebrew(conn, term: str, limit: int) -> list[tuple[dict, str, str]]:
    """Recover LM II Hebrew pages despite presentation-form storage glyphs."""
    from modules.library.likutey_moharan_ii_layout import readable_page_text

    async with conn.cursor() as cursor:
        await cursor.execute(
            """SELECT content_node_id::text,pdf_page_number pdf_page,
                      printed_page_number printed_page,literal_text quote,
                      'page_literal' record,NULL::text zone,NULL::text note,
                      NULL::text surface,lesson_number
               FROM library_lmii_search_ready_v2
               ORDER BY pdf_page_number"""
        )
        rows = await cursor.fetchall()
    results = []
    seen_pages: set[int] = set()
    for source in rows:
        page = int(source["pdf_page"])
        if page in seen_pages or not _compact_candidate(str(source["quote"]), term):
            continue
        readable = readable_page_text(page)
        context = _controlled_hebrew_context(readable or "", term)
        if not readable or context is None:
            continue
        row = dict(source)
        row["quote"] = readable
        row["section"] = f"LIKUTEY MOHARÁN II #{source['lesson_number']}" if source.get("lesson_number") else None
        row["match_context"] = context
        row["source_layer"] = "unknown"
        row["source_layer_confidence"] = "low"
        row["source_layer_rationale"] = "page_level_bilingual_layout_requires_zone_review"
        row["physical_pdf_page"] = page
        results.append((row, WORK_TITLES["lmii"], "library_lmii_search_ready_v2"))
        seen_pages.add(page)
        if len(results) >= limit:
            break
    return results


async def _fetch(conn, work: str, term: str, limit: int) -> list[tuple[dict, str, str]]:
    if work == "lm_xv":
        return await _fetch_lm_xv(conn, term, limit)
    if work == "lmii" and HEBREW_LETTER_RE.search(term):
        return await _fetch_lmii_hebrew(conn, term, limit)
    if work == "lmi":
        normalized = normalize_hebrew_search(term)
        async with conn.cursor() as cursor:
            await cursor.execute(
                """SELECT pdf_page_number pdf_page,printed_page_number printed_page,
                          literal_text quote,'page_literal' record,NULL::text zone,
                          NULL::text note,NULL::text surface,document_id::text,
                          source_filename physical_file_name,source_sha256,
                          page_anchor_id::text,section_page_label section,
                          content_node_id::text,position(%s in normalized_text) match_position
                   FROM library_lmi_literal_search_v1
                   WHERE normalized_text LIKE %s
                   ORDER BY position(%s in normalized_text),pdf_page_number LIMIT %s""",
                (normalized, f"%{normalized}%", normalized, limit),
            )
            rows = await cursor.fetchall()
        return [(row, WORK_TITLES[work], "library_lmi_literal_search_v1") for row in rows]
    config = {
        "kitzur": ("select null::int pdf_page,null::int printed_page,content quote,'chunk' record,null::text zone,null::text note,null::text surface from library_document_chunks c join library_documents d on d.id=c.document_id where d.title='KITZUR' and content ilike %s limit %s", "Kitzur", "library_document_chunks"),
        "lmii": ("select pdf_page_number pdf_page,printed_page_number printed_page,literal_text quote,'page_literal' record,null::text zone,null::text note,null::text surface from library_lmii_search_ready_v2 where literal_text ilike %s limit %s", "Likutey Moharán II", "library_lmii_search_ready_v2"),
        "lh": ("select pdf_page,printed_page,coalesce(resolution_quote,nominal_reference_quote,note_source_quote,fine_zone_quote,page_text) quote,search_record_type record,fine_zone_type zone,visible_note_number::text note,surface_form surface,document_id::text,unit_label section,document_part,final_page_status from library_likutey_halajot_investigative_search_v1 where coalesce(resolution_quote,nominal_reference_quote,note_source_quote,fine_zone_quote,page_text,'') ilike %s limit %s", "Likutey Halajot", "library_likutey_halajot_investigative_search_v1"),
        "potencia_plegaria": ("select pdf_page,null::int printed_page,quote,search_record_type record,zone_type zone,note_number::text note,surface_form surface from library_la_potencia_plegaria_investigative_search_v1 where quote ilike %s limit %s", "La Potencia de la Plegaria", "library_la_potencia_plegaria_investigative_search_v1"),
    }
    sql, title, view = config[work]
    async with conn.cursor() as cursor:
        await cursor.execute(sql, (f"%{term}%", limit))
        rows = await cursor.fetchall()
    return [(row, title, view) for row in rows]


async def _phrase_fetch(conn, work: str, phrase: str, limit: int) -> list[tuple[dict, str, str]]:
    """Search for the exact phrase as a whole, not individual terms."""
    if work in {"lmi", "lm_xv"} or (work == "lmii" and HEBREW_LETTER_RE.search(phrase)):
        return await _fetch(conn, work, phrase, limit)
    phrase_config = {
        "kitzur": ("select null::int pdf_page,null::int printed_page,content quote,'chunk' record,null::text zone,null::text note,null::text surface from library_document_chunks c join library_documents d on d.id=c.document_id where d.title='KITZUR' and content ilike %s limit %s", "Kitzur", "library_document_chunks"),
        "lmii": ("select pdf_page_number pdf_page,printed_page_number printed_page,literal_text quote,'page_literal' record,null::text zone,null::text note,null::text surface from library_lmii_search_ready_v2 where literal_text ilike %s limit %s", "Likutey Moharán II", "library_lmii_search_ready_v2"),
        "lh": ("select pdf_page,printed_page,coalesce(resolution_quote,nominal_reference_quote,note_source_quote,fine_zone_quote,page_text) quote,search_record_type record,fine_zone_type zone,visible_note_number::text note,surface_form surface,document_id::text,unit_label section,document_part,final_page_status from library_likutey_halajot_investigative_search_v1 where coalesce(resolution_quote,nominal_reference_quote,note_source_quote,fine_zone_quote,page_text,'') ilike %s limit %s", "Likutey Halajot", "library_likutey_halajot_investigative_search_v1"),
        "potencia_plegaria": ("select pdf_page,null::int printed_page,quote,search_record_type record,zone_type zone,note_number::text note,surface_form surface from library_la_potencia_plegaria_investigative_search_v1 where quote ilike %s limit %s", "La Potencia de la Plegaria", "library_la_potencia_plegaria_investigative_search_v1"),
    }
    sql, title, view = phrase_config[work]
    async with conn.cursor() as cursor:
        await cursor.execute(sql, (f"%{phrase}%", limit))
        rows = await cursor.fetchall()
    return [(row, title, view) for row in rows]


async def _resolve_pdf_spaced_literal(
    conn,
    works: list[str],
    analysis: HebrewLiteralQuery,
    limit: int,
) -> tuple[str | None, list[str]]:
    """Resolve lost word boundaries using bounded candidates and the corpus.

    The compact lookup is used only when PDF glyph spacing was detected. It
    selects a segmentation; normal indexed phrase retrieval remains the
    authority for evidence and ranking.
    """
    attempted = list(analysis.candidates[:64])
    corpus_segmentations: list[str] = []
    if "lmi" in works and analysis.compact_letters:
        async with conn.cursor() as cursor:
            await cursor.execute(
                """SELECT normalized_text
                   FROM library_lmi_literal_search_v1
                   WHERE regexp_replace(normalized_text, '[^א-ת]', '', 'g') LIKE %s
                   ORDER BY pdf_page_number
                   LIMIT %s""",
                (f"%{analysis.compact_letters}%", max(20, limit * 4)),
            )
            for row in await cursor.fetchall():
                corpus_segmentations.extend(
                    _normalized_token_segmentations(str(row["normalized_text"]), analysis.compact_letters)
                )
    if "lm_xv" in works and analysis.compact_letters:
        async with conn.cursor() as cursor:
            await cursor.execute(
                """SELECT p.pdf_page,b.bbox,b.text,d.source_path
                   FROM library_lm_xv_kdp_fine_zones_v1 f
                   JOIN library_lm_xv_kdp_page_blocks_v1 b ON b.id=f.parent_block_id
                   JOIN library_lm_xv_kdp_pages_v1 p
                     ON p.document_id=f.document_id AND p.pdf_page=f.pdf_page
                    AND p.source_run_id=f.source_run_id
                   JOIN library_documents d ON d.id=f.document_id
                   WHERE f.zone_type='main_text_hebrew'
                   ORDER BY p.pdf_page,f.block_index"""
            )
            for row in await cursor.fetchall():
                if analysis.compact_letters not in _hebrew_compact(str(row["text"])):
                    continue
                readable = readable_pdf_block(str(row["source_path"]), int(row["pdf_page"]), row["bbox"])
                if readable:
                    corpus_segmentations.extend(
                        _normalized_token_segmentations(readable, analysis.compact_letters)
                    )
    for candidate in dict.fromkeys(corpus_segmentations):
        if candidate not in attempted:
            attempted.append(candidate)
        for work in works:
            if work in {"lmi", "lm_xv"} and await _phrase_fetch(conn, work, candidate, 1):
                return candidate, attempted[:64]

    # Generic bounded fallback for other corpus views. It never changes the
    # source text and accepts a segmentation only after a literal DB match.
    for candidate in attempted[:16]:
        if not candidate or candidate == analysis.compact_letters:
            continue
        for work in works:
            if await _phrase_fetch(conn, work, candidate, 1):
                return candidate, attempted[:64]
    return None, attempted[:64]


def _hebrew_term_score(term: str) -> int:
    """Score how meaningful a Hebrew term is for search (higher = better)."""
    if len(term) >= 4:
        return 3
    if len(term) >= 3:
        return 2
    return 1


def display_snippet(text: str, limit: int = 900) -> str:
    """Presentation-only clipping; ``quote`` keeps the canonical retrieved text."""
    value = text.strip()
    clipped_start = bool(value and value[0].islower())
    if len(value) > limit:
        boundary = max(value.rfind(mark, 0, limit) for mark in (". ", "? ", "! ", "\n"))
        if boundary < limit // 2:
            boundary = value.rfind(" ", 0, limit)
        value = value[: boundary if boundary > 0 else limit].rstrip() + "…"
    if clipped_start:
        value = "…" + value
    return value


def literal_context_snippet(text: str, matched_terms: list[str], limit: int = 900) -> str:
    """Select complete source lines around a normalized literal match."""
    normalized_terms = sorted(
        {normalize_hebrew_search(term) for term in matched_terms if normalize_hebrew_search(term)},
        key=len,
        reverse=True,
    )
    lines = text.splitlines()
    for index, line in enumerate(lines):
        normalized_line = normalize_hebrew_search(line)
        if any(term in normalized_line for term in normalized_terms):
            start = max(0, index - 1)
            end = min(len(lines), index + 2)
            return display_snippet("\n".join(lines[start:end]), limit)
    return display_snippet(text, limit)


def _literal_strength(record: str, nominal: bool, note: bool) -> Literal["strong", "medium", "weak"]:
    if nominal or note or record in {"fine_zone", "main_text_spanish", "main_text_hebrew"}:
        return "strong"
    return "medium"


def _relation_strength(relevance: str) -> Literal["strong", "medium", "weak", "insufficient"]:
    if relevance == "direct_relation":
        return "strong"
    if relevance in {"same_fragment_both_terms", "same_section_relation"}:
        return "medium"
    if relevance in {"same_page_both_terms", "thematic_parallel", "inferred_relation"}:
        return "weak"
    return "insufficient"


def _detect_hit_language(quote: str) -> str:
    he_count = len(HEBREW_LETTER_RE.findall(quote))
    if he_count >= 10:
        return "he"
    total = len(quote.strip())
    if total and he_count / total > 0.3:
        return "he"
    return "es"


def _compute_language_match(hit_lang: str, primary_lang: str, secondary: list[str]) -> Literal["exact", "primary", "secondary", "fallback"]:
    if hit_lang == primary_lang:
        return "exact"
    if hit_lang in secondary:
        return "secondary"
    return "fallback"


def _compute_literal_match_kind(quote: str, terms: list[str], primary_lang: str) -> Literal["none", "exact_phrase", "normalized", "no_niqqud", "single_term", "semantic"]:
    if primary_lang == "he" and HEBREW_LETTER_RE.search(quote):
        he_terms = [t for t in terms if HEBREW_LETTER_RE.search(t) and len(t) >= 3]
        for term in he_terms:
            if term in quote:
                return "exact_phrase"
            normalized_term = normalize_hebrew_search(term)
            if normalized_term and normalized_term in normalize_hebrew_search(quote):
                has_marks = any(unicodedata.combining(char) for char in unicodedata.normalize("NFD", term))
                return "normalized" if has_marks else "no_niqqud"
        if he_terms:
            return "single_term"
    latin_terms = [t for t in terms if LATIN_LETTER_RE.search(t)]
    quote_flat = " ".join(quote.split())
    latin_flat = [re.sub(r"\s+", " ", t) for t in latin_terms]
    if len(latin_terms) >= 2 and all(t.lower() in quote_flat.lower() for t in latin_flat):
        return "exact_phrase"
    if len(latin_terms) >= 2:
        clean_terms = [re.sub(r"[,\"\'«»“”]", "", t).strip().lower() for t in latin_flat]
        clean_quote = re.sub(r"[,\"\'«»“”]", "", quote_flat).lower()
        if all(t in clean_quote for t in clean_terms):
            return "exact_phrase"
    if latin_terms and any(t.lower() in quote_flat.lower() for t in latin_flat):
        return "single_term"
    return "semantic"


def _compute_retrieval_tier(language_match: str, literal_match_kind: str) -> int:
    if literal_match_kind in {"named_topic_exact", "named_topic_normalized", "named_topic_alias"}:
        return 0
    if literal_match_kind in {"named_topic_translation", "named_topic_hebrew_equivalent"}:
        return 1
    if literal_match_kind == "named_topic_partial":
        return 2
    if language_match == "exact" and literal_match_kind in ("exact_phrase", "normalized", "no_niqqud"):
        return 0
    if language_match == "exact" and literal_match_kind == "single_term":
        return 1
    if language_match in ("primary", "exact") and literal_match_kind in ("semantic", "single_term"):
        return 2
    if language_match == "secondary":
        return 3
    return 4


def _classify_named_topic_match(
    quote: str,
    matched_terms: list[str],
    resolution: NamedTopicResolution,
) -> tuple[str, str | None, str | None, str | None]:
    quote_key = normalize_named_topic_candidate(quote)
    entry = next(item for item in load_named_topic_glossary() if item.canonical_id == resolution.canonical_id)
    aliases = {normalize_named_topic_candidate(alias.value): alias for alias in entry.aliases}
    candidates = sorted(
        (term for term in matched_terms if normalize_named_topic_candidate(term) in quote_key),
        key=lambda term: len(normalize_named_topic_candidate(term)),
        reverse=True,
    )
    if not candidates:
        return "named_topic_partial", None, None, None
    variant = candidates[0]
    variant_key = normalize_named_topic_candidate(variant)
    alias = aliases.get(variant_key)
    query_key = normalize_named_topic_candidate(resolution.matched_alias_catalog_value)
    canonical_key = normalize_named_topic_candidate(resolution.canonical_label)
    if variant_key == canonical_key and query_key == canonical_key:
        kind = "named_topic_exact"
    elif variant_key == query_key:
        kind = "named_topic_normalized"
    elif alias and alias.script == "Hebrew":
        kind = "named_topic_hebrew_equivalent"
    elif alias and alias.language in {"es", "en"} and alias.language != resolution.language:
        kind = "named_topic_translation"
    else:
        kind = "named_topic_alias"
    return kind, variant, alias.language if alias else None, alias.script if alias else None


def classify(
    work: str,
    row: dict,
    matched_terms: list[str],
    matched_concepts: list[str],
    view: str,
    primary_language: str = "es",
    secondary_languages: list[str] | None = None,
    named_topic: NamedTopicResolution | None = None,
) -> Hit:
    record = row["record"]
    nominal = bool(row["surface"])
    note = bool(row["note"])
    evidence_type = (
        "validated_nominal_reference" if nominal else
        "validated_numbered_note" if note else
        "validated_fine_zone_quote" if record in {"fine_zone", "main_text_spanish", "main_text_hebrew"} else
        "literal_same_page"
    )
    relevance = "same_fragment_both_terms" if len(matched_concepts) >= 2 else "single_term_literal"
    quote = str(row["quote"] or "")
    match_context = row.get("match_context")
    snippet = (
        match_context.paragraph_text if match_context is not None else
        literal_context_snippet(quote, matched_terms) if work == "lmi" else
        display_snippet(quote)
    )
    display_quote = None
    display_normalization = None
    if work == "lmii" and row["pdf_page"] is not None and len(HEBREW_LETTER_RE.findall(quote)) >= 100:
        from modules.library.likutey_moharan_ii_layout import readable_page_text

        display_quote = readable_page_text(int(row["pdf_page"]))
        if display_quote:
            display_normalization = "pdf_glyph_geometry_nfc_v1"
    warning = ["pdf_page_null_for_kitzur_chunk"] if work == "kitzur" and row["pdf_page"] is None else []
    evidence_text = display_quote if display_quote and _detect_hit_language(display_quote) == "he" else quote
    if display_quote and evidence_text == display_quote:
        snippet = display_snippet(display_quote)
    hit_lang = _detect_hit_language(evidence_text)
    sec_langs = secondary_languages or ["he", "en"]
    language_match = _compute_language_match(hit_lang, primary_language, sec_langs)
    literal_match_kind = _compute_literal_match_kind(evidence_text, matched_terms, primary_language)
    if match_context is not None:
        literal_match_kind = match_context.match_kind
    matched_variant = match_language = match_script = None
    if named_topic is not None:
        literal_match_kind, matched_variant, match_language, match_script = _classify_named_topic_match(
            evidence_text, matched_terms, named_topic,
        )
        if literal_match_kind != "named_topic_partial":
            relevance = "direct_relation"
    retrieval_tier = _compute_retrieval_tier(language_match, literal_match_kind)
    source_layer = row.get("source_layer")
    if source_layer not in SOURCE_LAYERS:
        record = row.get("record")
        zone = row.get("zone")
        source_layer = (
            "rebbe_lesson_text" if zone == "main_text_hebrew" else
            "editorial_translation" if zone == "main_text_spanish" else
            "section_heading" if record in {"structural_page", "heading"} or zone in {"halakhah_header", "section_heading"} else
            "source_reference" if record == "nominal_reference" else
            "footnote" if note else
            "source_reference" if nominal else
            "unknown"
        )
    source_layer_confidence = row.get("source_layer_confidence", "low")
    source_layer_rationale = row.get("source_layer_rationale", "insufficient_structural_evidence")
    if work == "lh" and record == "page_literal" and source_layer == "unknown":
        source_layer_confidence = "low"
        source_layer_rationale = "page_literal_only_without_validated_zone"
    hit_id = (
        f"{work}-{row['content_node_id']}" if row.get("content_node_id")
        else f"{work}-{stable_hash(work + '|' + quote)[:12]}"
    )
    parallel_texts = [ParallelText(
        **candidate,
        linked_to_evidence_id=hit_id,
        link_type="parallel_translation",
    ) for candidate in row.get("parallel_candidates", [])]

    # ── Sanitize snippet for display ─────────────────────────────────
    matched_phrase = matched_variant or (" ".join(matched_terms) if matched_terms else None)
    sanitized = sanitize_evidence_snippet(
        snippet,
        matched_phrase=matched_phrase,
        max_length=1200,
        context_lines=2,
    )
    display_snippet_value = sanitized["display_snippet"]
    snippet_sanitized = sanitized["sanitization_applied"]
    reason_codes = sanitized["sanitization_reason_codes"]

    # ── Author quote status from source layer ───────────────────────
    author_status = AUTHOR_QUOTE_MAP.get(source_layer, "not_confirmed")
    attribution_value = ATTRIBUTION_LABELS.get(author_status, "Coincidencia literal en la edición")

    return Hit(
        hit_id=hit_id,
        work_code=work,
        work_title=WORK_TITLES[work],
        pdf_page=row["pdf_page"],
        printed_page=row["printed_page"],
        quote=quote[:4000],
        snippet=snippet,
        display_quote=display_quote[:4000] if display_quote else None,
        display_snippet=display_snippet_value,
        display_normalization=display_normalization,
        source_view=view,
        search_record_type=record,
        source_layer=source_layer,
        source_layer_confidence=source_layer_confidence,
        source_layer_rationale=source_layer_rationale,
        zone_type=row["zone"],
        note_number=row["note"],
        surface_form=row["surface"],
        matched_terms=matched_terms,
        matched_concepts=matched_concepts,
        evidence_type=evidence_type,
        literal_strength=_literal_strength(record, nominal, note),
        evidence_strength="strong" if named_topic is not None and literal_match_kind != "named_topic_partial" else _relation_strength(relevance),
        relation_relevance=relevance,
        language_match=language_match,
        literal_match_kind=literal_match_kind,
        match_kind=literal_match_kind,
        direct_support=bool(named_topic is not None and literal_match_kind != "named_topic_partial"),
        match_strength="strong" if named_topic is not None and literal_match_kind != "named_topic_partial" else _relation_strength(relevance),
        single_term=not bool(named_topic is not None and literal_match_kind != "named_topic_partial"),
        canonical_topic_id=named_topic.canonical_id if named_topic else None,
        matched_variant=matched_variant,
        match_language=match_language,
        match_script=match_script,
        retrieval_tier=retrieval_tier,
        warnings=warning,
        document_id=row.get("document_id"),
        physical_file_name=row.get("physical_file_name"),
        source_sha256=row.get("source_sha256"),
        page_anchor_id=row.get("page_anchor_id"),
        section=row.get("section"),
        retrieval_position=row.get("match_position"),
        physical_pdf_page=row.get("physical_pdf_page", row.get("pdf_page")),
        match_text=match_context.match_text if match_context else "",
        sentence_text=match_context.sentence_text if match_context else "",
        paragraph_text=match_context.paragraph_text if match_context else snippet,
        context_before=match_context.context_before if match_context else "",
        context_after=match_context.context_after if match_context else "",
        language=hit_lang,
        direction="rtl" if hit_lang == "he" else "ltr",
        source_original_language="he" if hit_lang == "he" else "unknown",
        is_original_language=(hit_lang == "he" and source_layer in {
            "rebbe_lesson_text", "biblical_quote_in_lesson", "rabbinic_quote_in_lesson"
        }),
        is_primary_language_match=hit_lang == primary_language,
        is_translation=source_layer == "editorial_translation",
        is_editorial_commentary=source_layer in {"editorial_commentary", "editorial_note", "footnote"},
        parent_zone_id=row.get("parent_zone_id"),
        content_node_id=row.get("content_node_id"),
        evidence_id=hit_id,
        page_anchor_kind=row.get("page_anchor_kind"),
        ingestion_run_id=row.get("source_run_id"),
        parallel_texts=parallel_texts,
        author_quote_status=author_status,
        attribution_label=attribution_value,
        raw_snippet=quote[:4000],
        snippet_sanitized=snippet_sanitized,
        sanitization_reason_codes=reason_codes,
    )


def _mark_same_page(hits: list[Hit]) -> None:
    page_concepts: dict[tuple[str, int], set[str]] = defaultdict(set)
    for hit in hits:
        if hit.pdf_page is not None:
            page_concepts[(hit.work_code, hit.pdf_page)].update(hit.matched_concepts)
    for hit in hits:
        if hit.relation_relevance == "single_term_literal" and hit.pdf_page is not None and len(page_concepts[(hit.work_code, hit.pdf_page)]) >= 2:
            hit.relation_relevance = "same_page_both_terms"
            hit.evidence_strength = "weak"
            hit.relation_level = "contextual"


def _sort_key(hit: Hit) -> tuple:
    return (
        hit.retrieval_tier,
        source_layer_priority(hit.source_layer),
        RELATION_PRIORITY[hit.relation_relevance],
        -len(hit.matched_concepts),
        hit.retrieval_position if hit.retrieval_position is not None else 10**9,
        hit.work_code,
        hit.pdf_page or 10**9,
        hit.hit_id,
    )


_STRUCTURAL_PRIORITY = {"lh": 0, "lmii": 1, "lmi": 1, "lm_xv": 1, "kitzur": 2, "potencia_plegaria": 3}

def _structural_ref_sort_key(hit: Hit) -> tuple:
    return (
        _STRUCTURAL_PRIORITY.get(hit.work_code, 9),
        source_layer_priority(hit.source_layer),
        -(1 if hit.section else 0),
        -(1 if hit.pdf_page is not None else 0),
        hit.pdf_page or 10**9,
        hit.hit_id,
    )


def _normalize_claims(raw_claims: list[dict], hits: list[Hit], required_concepts: int = 1) -> list[dict]:
    allowed = {hit.hit_id: hit for hit in hits}
    claims = []
    for index, raw in enumerate(raw_claims):
        text = str(raw.get("text") or raw.get("claim") or "").strip()
        evidence_ids = list(dict.fromkeys(str(value) for value in raw.get("evidence_ids", []) if str(value) in allowed))
        if required_concepts >= 2:
            direct_ids = [value for value in evidence_ids if len(allowed[value].matched_concepts) >= required_concepts]
            if not direct_ids:
                continue
            evidence_ids = direct_ids
        if not text or not evidence_ids:
            continue
        requested_primary = str(raw.get("primary_evidence_id") or "")
        primary = requested_primary if requested_primary in evidence_ids else evidence_ids[0]
        claims.append({
            "claim_id": str(raw.get("claim_id") or f"claim_{index + 1}"),
            "text": text,
            "strength": str(raw.get("strength") or _relation_strength(allowed[primary].relation_relevance)),
            "evidence_ids": evidence_ids,
            "primary_evidence_id": primary,
        })
    return claims


def validate_grounded_render(value: dict, hits: list[Hit], required_concepts: int = 1) -> tuple[str | None, list[dict]]:
    """Validate narrative and claim associations against the authoritative hit set."""
    allowed = {hit.hit_id for hit in hits}
    used = {str(item) for item in value.get("used_evidence_ids", [])}
    text = str(value.get("answer_markdown", ""))
    raw_claims = value.get("claims", [])
    if not used or not used.issubset(allowed) or not text or not isinstance(raw_claims, list):
        return None, []
    claims = _normalize_claims(raw_claims, hits, required_concepts)
    if not claims or any(not set(claim["evidence_ids"]).issubset(allowed) for claim in claims):
        return None, []
    pages = {str(hit.pdf_page) for hit in hits if hit.pdf_page is not None}
    if any(page not in pages for page in re.findall(r"(?i)(?:página|pdf p\.)\s*(\d+)", text)):
        return None, []
    if re.search(r"(?i)(demuestra|dependencia doctrinal|prueba doctrinal)", text):
        return None, []
    return text, claims


async def _ai_render(question: str, hits: list[Hit]) -> tuple[str | None, list[str], list[dict]]:
    if not LITELLM_API_KEY:
        return None, ["ai_render_fallback:litellm_key_missing"], []
    context = [{
        "id": hit.hit_id,
        "work": hit.work_title,
        "page": hit.pdf_page,
        "quote": hit.snippet,
        "matched_concepts": hit.matched_concepts,
        "relation_relevance": hit.relation_relevance,
        "literal_strength": hit.literal_strength,
        "warnings": hit.warnings,
    } for hit in hits[:20]]
    try:
        async with httpx.AsyncClient(timeout=LITELLM_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{LITELLM_BASE_URL}/v1/chat/completions",
                headers={"Authorization": f"Bearer {LITELLM_API_KEY}"},
                json={
                    "model": RESEARCH_CONVERSATION_MODEL,
                    "messages": [
                        {"role": "system", "content": "Return JSON only: answer_markdown, used_evidence_ids, claims. Each claim must contain claim_id, text, strength, evidence_ids, primary_evidence_id. Use only supplied IDs. Prefer evidence containing every requested concept. A single-term literal is not strong evidence for a relation. Never invent quotes/pages/works and never assert doctrinal dependency."},
                        {"role": "user", "content": json.dumps({"question": question, "evidence": context}, ensure_ascii=False)},
                    ],
                    "temperature": 0,
                    "max_tokens": 1400,
                    "response_format": {"type": "json_object"},
                },
            )
        value = json.loads(response.json()["choices"][0]["message"]["content"])
        text, claims = validate_grounded_render(value, hits, len(relation_concepts(question)))
        if text is None:
            return None, ["ai_render_rejected_grounding_validation"], []
        return text, [], claims
    except Exception as exc:
        return None, [f"ai_render_fallback:{type(exc).__name__}"], []


def _cap_hits_with_language_coverage(
    hits: list[Hit],
    max_hits_per_work: int,
    requested_languages: list[str],
) -> list[Hit]:
    """Keep the ranked cap while preserving one readable Hebrew result when requested."""
    def readable_hebrew(hit: Hit) -> bool:
        if hit.display_normalization != "pdf_glyph_geometry_nfc_v1" or not hit.display_snippet:
            return False
        return len(HEBREW_LETTER_RE.findall(hit.display_snippet)) >= max(
            1,
            len(LATIN_LETTER_RE.findall(hit.display_snippet)),
        )

    selected_ids: set[str] = set()
    for work in dict.fromkeys(hit.work_code for hit in hits):
        work_hits = [hit for hit in hits if hit.work_code == work]
        selected = work_hits[:max_hits_per_work]
        if "he" in requested_languages and max_hits_per_work >= 2:
            has_hebrew = any(readable_hebrew(hit) for hit in selected)
            best_hebrew = next((hit for hit in work_hits if readable_hebrew(hit)), None)
            if not has_hebrew and best_hebrew is not None:
                selected = [*selected[:-1], best_hebrew]
        selected_ids.update(hit.hit_id for hit in selected)
    return [hit for hit in hits if hit.hit_id in selected_ids]


def _deterministic_claims(
    question: str,
    hits: list[Hit],
    intent: str = "concept_lookup",
    literal_search_normalized: str | None = None,
    concept_count: int | None = None,
    instruction_language: str = "es",
    named_topic: NamedTopicResolution | None = None,
) -> list[dict]:
    if named_topic is not None and hits:
        direct_hits = [hit for hit in hits if hit.direct_support]
        if not direct_hits:
            return []
        primary = direct_hits[0]
        location = ", ".join(filter(None, [
            f"PDF p. {primary.pdf_page}" if primary.pdf_page is not None else None,
            f"página impresa {primary.printed_page}" if primary.printed_page is not None else None,
            f"sección {primary.section}" if primary.section else None,
        ]))
        text = (
            f"Interpreté «{named_topic.subject_raw}» como «{named_topic.canonical_label}». "
            f"La expresión aparece en {primary.work_title}{', ' + location if location else ''}. "
            f"El fragmento menciona explícitamente «{primary.match_text or primary.matched_variant or named_topic.canonical_label}»."
        )
        return [{
            "claim_id": "named_topic_primary",
            "text": text,
            "strength": "strong",
            "evidence_ids": [primary.hit_id],
            "primary_evidence_id": primary.hit_id,
        }]
    if intent in {"literal_lookup", "translation_or_explanation"} and hits:
        phrases = _extract_literal_phrases(question)
        literal_query = literal_search_normalized or (
            normalize_hebrew_search(str(phrases[0]["text"])) if phrases else ""
        )
        literal_hits = [hit for hit in hits if hit.literal_match_kind in {
            "exact_phrase", "normalized", "no_niqqud"
        } and hit.is_primary_language_match]
        if not literal_hits:
            return []
        primary = literal_hits[0]
        location = " · ".join(filter(None, [
            f"PDF p. {primary.pdf_page}" if primary.pdf_page is not None else None,
            f"página impresa {primary.printed_page}" if primary.printed_page is not None else None,
            primary.section,
        ]))
        layer = {
            "biblical_quote_in_lesson": {
                "es": "Capa: cita bíblica incluida en la lección del Rebe.",
                "en": "Layer: biblical quotation included in the Rebbe's lesson.",
                "he": "שכבה: ציטוט מקראי המשולב בשיעורו של הרבי.",
            },
            "rabbinic_quote_in_lesson": {
                "es": "Capa: cita rabínica incluida en la lección del Rebe.",
                "en": "Layer: rabbinic quotation included in the Rebbe's lesson.",
                "he": "שכבה: ציטוט חז״לי המשולב בשיעורו של הרבי.",
            },
            "rebbe_lesson_text": {
                "es": "Capa: texto original de la lección del Rebe.",
                "en": "Layer: original text of the Rebbe's lesson.",
                "he": "שכבה: הטקסט המקורי של שיעור הרבי.",
            },
        }.get(primary.source_layer, {
            "es": "Capa editorial no confirmada; requiere revisión.",
            "en": "Editorial layer is unconfirmed and requires review.",
            "he": "השכבה העריכתית לא אושרה ודורשת בדיקה.",
        })
        additional = [
            h for h in literal_hits[1:]
            if h.work_code != primary.work_code
        ]
        additional_note = ""
        if additional:
            extra = " · ".join(
                f"{h.work_title} (p. {h.pdf_page})" if h.pdf_page else h.work_title
                for h in additional[:3]
            )
            additional_note = {
                "es": f" También aparece en {extra}.",
                "en": f" It also appears in {extra}.",
                "he": f" מופיע גם ב{extra}.",
            }.get(instruction_language if instruction_language in {"es", "en", "he"} else "es", "")
        locale = instruction_language if instruction_language in {"es", "en", "he"} else "es"
        all_evidence_ids = [primary.hit_id] + [h.hit_id for h in additional]
        attribution_es = f" Atribución: {primary.attribution_label}." if primary.attribution_label else ""
        texts = {
            "es": f"La frase aparece literalmente en {primary.physical_file_name or primary.work_title}{' — ' + location if location else ''}. {layer['es']}{attribution_es}{additional_note}",
            "en": f"The phrase appears literally in {primary.physical_file_name or primary.work_title}{' — ' + location if location else ''}. {layer['en']}{additional_note}",
            "he": f"הביטוי מופיע במפורש ב־{primary.physical_file_name or primary.work_title}{' — ' + location if location else ''}. {layer['he']}{additional_note}",
        }
        return [{
            "claim_id": "claim_1",
            "text": texts[locale],
            "strength": "strong",
            "evidence_ids": all_evidence_ids,
            "primary_evidence_id": primary.hit_id,
        }]
    if intent == "structural_reference_lookup" and hits:
        structural_hits = [hit for hit in hits if hit.literal_match_kind in {"exact_phrase", "normalized", "no_niqqud"}]
        if structural_hits:
            structural_hits.sort(key=_structural_ref_sort_key)
            primary = structural_hits[0]
            location = " · ".join(filter(None, [
                f"PDF p. {primary.pdf_page}" if primary.pdf_page is not None else None,
                f"página impresa {primary.printed_page}" if primary.printed_page is not None else None,
                primary.section,
            ]))
            locale = instruction_language if instruction_language in {"es", "en", "he"} else "es"
            texts = {
                "es": f"Interpreté la consulta como referencia estructural. La referencia aparece en {primary.physical_file_name or primary.work_title}{' — ' + location if location else ''}.",
                "en": f"Interpreted the query as a structural reference. The reference appears in {primary.physical_file_name or primary.work_title}{' — ' + location if location else ''}.",
                "he": f"השאלה פורשה כהפניה מבנית. ההפניה מופיעה ב־{primary.physical_file_name or primary.work_title}{' — ' + location if location else ''}.",
            }
            return [{
                "claim_id": "claim_1",
                "text": texts[locale],
                "strength": "strong",
                "evidence_ids": [primary.hit_id],
                "primary_evidence_id": primary.hit_id,
            }]
    candidates = [hit for hit in hits if hit.relation_relevance in {"same_fragment_both_terms", "same_section_relation", "same_page_both_terms"}]
    required = concept_count if concept_count is not None else len(relation_concepts(question))
    if not candidates and required == 1 and hits:
        candidates = [hits[0]]
    if not candidates:
        return []
    primary = candidates[0]
    return [{
        "claim_id": "claim_1",
        "text": f"Se encontró evidencia contextual para la consulta «{question}»; la fuente debe leerse sin asumir dependencia doctrinal.",
        "strength": _relation_strength(primary.relation_relevance),
        "evidence_ids": [primary.hit_id],
        "primary_evidence_id": primary.hit_id,
    }]


def _apply_claim_traceability(hits: list[Hit], claims: list[dict]) -> list[str]:
    primary_ids = list(dict.fromkeys(claim["primary_evidence_id"] for claim in claims))
    primary_order = {evidence_id: index for index, evidence_id in enumerate(primary_ids)}
    by_id = {hit.hit_id: hit for hit in hits}
    strength_order = {"insufficient": 0, "weak": 1, "medium": 2, "strong": 3}
    claim_strengths: dict[str, str] = {}
    for claim in claims:
        strength = str(claim.get("strength", "strong"))
        if strength not in strength_order:
            strength = "weak"
        for evidence_id in claim["evidence_ids"]:
            current = claim_strengths.get(evidence_id, "insufficient")
            if evidence_id not in claim_strengths or strength_order[strength] > strength_order[current]:
                claim_strengths[evidence_id] = strength
    for evidence_id, strength in claim_strengths.items():
        hit = by_id[evidence_id]
        hit.relation_relevance = "direct_relation"
        hit.evidence_strength = strength
        hit.relation_level = "literal"
        hit.is_primary = evidence_id in primary_ids
    hits.sort(key=lambda hit: (0, primary_order[hit.hit_id]) if hit.hit_id in primary_order else (1, _sort_key(hit)))
    return primary_ids


def _counts(hits: list[Hit], primary_ids: list[str]) -> dict[str, int]:
    primary = set(primary_ids)
    contextual_types = {"same_fragment_both_terms", "same_section_relation", "same_page_both_terms", "thematic_parallel", "inferred_relation"}
    return {
        "primary": len(primary),
        "contextual": sum(hit.hit_id not in primary and hit.relation_relevance in contextual_types for hit in hits),
        "additional_literal": sum(hit.relation_relevance in {"single_term_literal", "unrelated_literal_noise"} for hit in hits),
    }


def _is_source_layer_followup(question: str) -> bool:
    folded = _fold(question)
    spanish = bool(
        re.search(r"\bes\b.*\b(?:texto|parte|cita|comentario|nota|traduccion|original)\b", folded)
        or re.search(r"\b(?:que|cual)\s+(?:es\s+la\s+)?(?:capa|naturaleza|tipo\s+de\s+fuente)\b", folded)
    )
    english = bool(
        re.search(r"\bis\b.*\b(?:lesson|quote|quotation|commentary|note|translation|original)\b", folded)
        or re.search(r"\bwhat\s+(?:source\s+)?(?:layer|kind\s+of\s+source)\b", folded)
    )
    hebrew = bool(
        re.search(r"(?:האם|זה).*(?:שיעור|ציטוט|הערה|פירוש|תרגום|מקור)", question)
        or re.search(r"(?:איזו|מהי).*(?:שכבה|מקור)", question)
    )
    return spanish or english or hebrew


def _source_layer_followup_claims(hits: list[Hit], instruction_language: str) -> list[dict]:
    if not hits:
        return []
    primary = next((
        hit for hit in hits
        if hit.is_primary_language_match
        and hit.literal_match_kind in {"exact_phrase", "normalized", "no_niqqud"}
    ), hits[0])
    locale = instruction_language if instruction_language in {"es", "en", "he"} else "es"
    messages = {
        "rebbe_lesson_text": {
            "es": "Sí. Es texto original de la lección del Rebe. No es una cita ni una nota editorial.",
            "en": "Yes. It is original text from the Rebbe's lesson. It is not a quotation or an editorial note.",
            "he": "כן. זהו הטקסט המקורי של שיעור הרבי, ולא ציטוט או הערת עורך.",
        },
        "biblical_quote_in_lesson": {
            "es": "Sí. Es una cita bíblica incluida dentro de la lección del Rebe. No es una nota editorial.",
            "en": "Yes. It is a biblical quotation included in the Rebbe's lesson. It is not an editorial note.",
            "he": "כן. זהו ציטוט מקראי המשולב בשיעורו של הרבי, ולא הערת עורך.",
        },
        "rabbinic_quote_in_lesson": {
            "es": "Sí. Es una cita rabínica incluida dentro de la lección del Rebe. No es una nota editorial.",
            "en": "Yes. It is a rabbinic quotation included in the Rebbe's lesson. It is not an editorial note.",
            "he": "כן. זהו ציטוט חז״לי המשולב בשיעורו של הרבי, ולא הערת עורך.",
        },
        "editorial_translation": {
            "es": "No. Es una traducción editorial; no es el texto original de la lección.",
            "en": "No. It is an editorial translation, not the original lesson text.",
            "he": "לא. זהו תרגום עריכתי, ולא הטקסט המקורי של השיעור.",
        },
        "editorial_commentary": {
            "es": "No. Es un comentario editorial; no es el texto original de la lección.",
            "en": "No. It is editorial commentary, not the original lesson text.",
            "he": "לא. זהו פירוש עריכתי, ולא הטקסט המקורי של השיעור.",
        },
        "editorial_note": {
            "es": "No. Es una nota editorial; no es el texto original de la lección.",
            "en": "No. It is an editorial note, not the original lesson text.",
            "he": "לא. זוהי הערת עורך, ולא הטקסט המקורי של השיעור.",
        },
        "footnote": {
            "es": "No. Es una nota al pie editorial; no es el texto original de la lección.",
            "en": "No. It is an editorial footnote, not the original lesson text.",
            "he": "לא. זוהי הערת שוליים עריכתית, ולא הטקסט המקורי של השיעור.",
        },
        "source_reference": {
            "es": "No. Es una referencia de fuente; no es el cuerpo original de la lección.",
            "en": "No. It is a source reference, not the original body of the lesson.",
            "he": "לא. זוהי הפניית מקור, ולא גוף השיעור המקורי.",
        },
        "section_heading": {
            "es": "No. Es un encabezado de sección; no es el cuerpo original de la lección.",
            "en": "No. It is a section heading, not the original body of the lesson.",
            "he": "לא. זוהי כותרת סעיף, ולא גוף השיעור המקורי.",
        },
        "page_heading": {
            "es": "No. Es un encabezado de página; no es el cuerpo original de la lección.",
            "en": "No. It is a page heading, not the original body of the lesson.",
            "he": "לא. זוהי כותרת עמוד, ולא גוף השיעור המקורי.",
        },
        "introduction": {
            "es": "No. Pertenece a la introducción; no es el cuerpo original de la lección.",
            "en": "No. It belongs to the introduction, not the original body of the lesson.",
            "he": "לא. זהו חלק מן המבוא, ולא גוף השיעור המקורי.",
        },
        "unknown": {
            "es": "No confirmado. La capa editorial de este fragmento requiere revisión.",
            "en": "Not confirmed. The editorial layer of this fragment requires review.",
            "he": "לא אושר. השכבה העריכתית של הקטע דורשת בדיקה.",
        },
    }
    confidence_strength = {"high": "strong", "medium": "medium", "low": "insufficient"}
    return [{
        "claim_id": "source_layer_followup",
        "text": messages[primary.source_layer][locale],
        "strength": confidence_strength[primary.source_layer_confidence],
        "evidence_ids": [primary.hit_id],
        "primary_evidence_id": primary.hit_id,
    }]


def render(
    question: str,
    claims: list[dict],
    hits: list[Hit],
    warnings: list[str],
    intent: str = "concept_lookup",
    *,
    source_layer_followup: bool = False,
    named_topic: NamedTopicResolution | None = None,
) -> str:
    lines = ["## Síntesis investigativa"]
    if claims:
        lines.extend(f"- {claim['text']}" for claim in claims)
    elif intent in {"literal_lookup", "translation_or_explanation"}:
        lines.append(f"No se encontró una coincidencia literal para «{question}».")
    elif intent in {"structural_reference_lookup"}:
        lines.append(f"No se encontró una referencia estructural para la consulta «{question}».")
    elif named_topic is not None:
        variants = [
            value for value in named_topic.variants_searched
            if value != named_topic.canonical_label
        ][:3]
        suffix = f" También busqué las variantes {', '.join(f'«{item}»' for item in variants)}." if variants else ""
        lines.append(
            f"No encontré referencias verificables a «{named_topic.canonical_label}» en el corpus consultado.{suffix}"
        )
    elif intent in {"concept_lookup", "concept_cooccurrence", "reference_lookup", "follow_up", "book_scope_query", "source_request"}:
        lines.append(f"No se encontró evidencia para el concepto o fuente solicitada en «{question}».")
    else:
        lines.append(f"No se encontró evidencia suficiente para establecer la relación solicitada en «{question}».")
    lines.extend(["", "## Evidencia principal"])
    for hit in [item for item in hits if item.is_primary][:5]:
        lang_label = {"exact": "", "primary": "", "secondary": " [Traducción]", "fallback": " [Otro idioma]"}.get(hit.language_match, "")
        literal_label = {
            "exact_phrase": "Coincidencia exacta", "normalized": "Coincidencia normalizada",
            "no_niqqud": "Sin niqqud", "single_term": "Término individual", "semantic": "Semántica", "none": "",
            "named_topic_exact": "Tema nominal exacto", "named_topic_normalized": "Tema nominal normalizado",
            "named_topic_alias": "Alias nominal", "named_topic_translation": "Equivalente traducido",
            "named_topic_hebrew_equivalent": "Equivalente hebreo", "named_topic_partial": "Tema nominal parcial",
        }.get(hit.literal_match_kind, "")
        labels = " · ".join(filter(None, [lang_label, literal_label]))
        relevance_label = {
            "direct_relation": "Respaldo directo",
            "same_fragment_both_terms": "Mismo fragmento",
            "same_page_both_terms": "Misma página",
            "same_section_relation": "Misma sección",
            "single_term_literal": "Coincidencia de un término",
            "thematic_parallel": "Paralelo temático",
            "inferred_relation": "Relación inferida",
            "unrelated_literal_noise": "Coincidencia no relacionada",
        }[hit.relation_relevance]
        strength_label = {
            "strong": "Fuerte", "medium": "Media", "weak": "Débil", "insufficient": "Insuficiente",
        }[hit.evidence_strength]
        display_text = hit.display_snippet or hit.snippet
        layer_labels = {
            "rebbe_lesson_text": "Texto original de la lección",
            "biblical_quote_in_lesson": "Cita bíblica dentro de la lección",
            "rabbinic_quote_in_lesson": "Cita rabínica dentro de la lección",
            "editorial_translation": "Traducción editorial",
            "editorial_commentary": "Comentario editorial",
            "editorial_note": "Nota editorial",
            "footnote": "Pie de página",
            "source_reference": "Referencia de fuente",
            "section_heading": "Encabezado de sección",
            "page_heading": "Encabezado de página",
            "introduction": "Introducción",
            "unknown": "Capa editorial no confirmada; requiere revisión",
        }
        layer_text = layer_labels.get(hit.source_layer, hit.source_layer)
        lines.extend([
                f"### {hit.work_title}{' — PDF p. ' + str(hit.pdf_page) if hit.pdf_page is not None else ''}",
                f"> {display_text}",
                f"**Relevancia:** {relevance_label} · **Fuerza relacional:** {strength_label}{' · ' + labels if labels else ''}",
                f"**Capa:** {layer_text} · **Atribución:** {hit.attribution_label}",
                "",
            ])
    additional_appearances = [
        hit for hit in hits
        if not hit.is_primary
        and hit.literal_match_kind in {"exact_phrase", "normalized", "no_niqqud"}
        and hit.work_code != (hits[0].work_code if hits else None)
    ]
    if additional_appearances:
        lines.extend(["", "## Apariciones adicionales"])
        for hit in additional_appearances[:3]:
            loc = " · ".join(filter(None, [
                f"PDF p. {hit.pdf_page}" if hit.pdf_page is not None else None,
                f"página impresa {hit.printed_page}" if hit.printed_page is not None else None,
                hit.section,
            ]))
            lines.append(f"- **{hit.work_title}**{f' — {loc}' if loc else ''}.")
    if source_layer_followup:
        lines.extend(["## Alcance", "- La clasificación responde a la capa editorial estructurada de la evidencia seleccionada."])
    elif named_topic is not None:
        lines.extend(["## Alcance", "- La equivalencia nominal proviene del glosario controlado; la evidencia y sus páginas provienen de PostgreSQL."])
    elif intent in {"literal_lookup", "translation_or_explanation"}:
        lines.extend(["## Límites", "- La coincidencia se informa como literal o normalizada; no se sustituye por una traducción."])
    else:
        lines.extend(["## Límites", "- Una coincidencia literal de un solo término no establece la relación consultada.", "- Los paralelos entre obras no demuestran dependencia o equivalencia doctrinal."])
    narrative_warnings = [
        warning for warning in warnings
        if not warning.startswith("evidence_snippet_sanitized:")
    ]
    if narrative_warnings:
        lines.extend(["", "## Advertencias", *[f"- {warning}" for warning in sorted(set(narrative_warnings))]])
    return "\n".join(lines)


def _retrieval_inputs(interpretation: QueryInterpretation) -> tuple[list[dict], list[dict]]:
    """Map validated interpretation fields to the legacy deterministic retriever."""
    subjects = list(interpretation.query_subjects)
    if interpretation.relations:
        subjects = [
            side
            for relation in interpretation.relations
            for side in (relation.left, relation.right)
        ]
    concepts = []
    for subject in subjects:
        terms = [item.value for item in subject.variants]
        if subject.script == "latin":
            alias_key = next(
                (key for key in ALIASES if _fold(key) == _fold(subject.normalized)),
                None,
            )
            if alias_key:
                terms.extend(ALIASES[alias_key])
        concepts.append({
            "label": subject.normalized,
            "terms": list(dict.fromkeys(terms)),
        })
    literal_phrases = [{
        "text": phrase.raw,
        "language": phrase.language,
        "script": "Hebrew" if HEBREW_LETTER_RE.search(phrase.raw) else "Latin",
        "word_count": len(phrase.normalized.split()),
        "content_words": phrase.normalized.split(),
        "search_normalized": phrase.normalized,
    } for phrase in interpretation.literal_phrases]
    if literal_phrases and not concepts:
        concepts = [{
            "label": literal_phrases[0]["search_normalized"],
            "terms": [literal_phrases[0]["search_normalized"]],
        }]
    return concepts, literal_phrases


@dataclass(frozen=True)
class PreparedQuery:
    structured: QueryInterpretation
    named_topic: NamedTopicResolution | None
    warnings: tuple[str, ...]
    preprocessing: dict
    glossary_duration_ms: float


async def prepare_query(data: QaRequest) -> PreparedQuery:
    """Interpret and validate a query without consulting corpus evidence."""
    glossary_started = time.perf_counter()
    named_topic = resolve_named_topic(data.question)
    glossary_duration_ms = round((time.perf_counter() - glossary_started) * 1000, 2)
    history = (
        data.conversation.get("history", [])
        if isinstance(data.conversation.get("history", []), list)
        else []
    )
    preprocessing = preprocess_query(data.question)
    structured, interpretation_warnings = await interpret_query(
        preprocessing,
        history,
        data.works,
        data.languages,
        ai_enabled=data.ai.enabled,
    )
    if named_topic is None:
        named_topic_subject = next(
            (subject for subject in structured.query_subjects if subject.kind == "named_topic"),
            None,
        )
        if named_topic_subject is not None:
            named_topic = resolve_named_topic(named_topic_subject.raw)
    if structured.intent in {"relation_query", "comparison_query"}:
        # A named topic may be one side of a relation, but must not replace the
        # complete validated relation contract.
        named_topic = None
    return PreparedQuery(
        structured=structured,
        named_topic=named_topic,
        warnings=tuple(interpretation_warnings),
        preprocessing=preprocessing.model_dump(),
        glossary_duration_ms=glossary_duration_ms,
    )


def query_understanding_contract(data: QaRequest, prepared: PreparedQuery) -> dict:
    structured = prepared.structured
    named_topic = prepared.named_topic
    subject = structured.query_subjects[0] if structured.query_subjects else None
    operation_by_intent = {
        "literal_lookup": "locate_literal_phrase",
        "translation_or_explanation": "locate_literal_phrase",
        "structural_reference_lookup": "locate_reference",
        "reference_lookup": "locate_reference",
        "concept_cooccurrence": "find_related_concepts",
        "relation_query": "investigate_relation",
        "comparison_query": "compare_subjects",
        "concept_lookup": "find_concept",
        "location_lookup": "locate_subject",
        "book_scope_query": "locate_subject",
        "source_request": "locate_source",
        "follow_up": "resolve_follow_up",
        "unknown": "investigate_query",
    }
    operation = (
        "find_named_topic"
        if named_topic is not None and structured.intent == "concept_lookup"
        else structured.operation
        if structured.operation is not None
        else operation_by_intent.get(structured.intent, "investigate_query")
    )
    typo_resolution = (
        {
            "applied": True,
            "original_fragment": structured.colloquial_normalizations[0].original_fragment,
            "interpreted_as": structured.colloquial_normalizations[0].interpreted_as,
            "reason": structured.colloquial_normalizations[0].reason,
            "confidence": structured.colloquial_normalizations[0].confidence,
        }
        if structured.colloquial_normalizations
        else None
    )
    return {
        "original_query": data.question,
        "intent": structured.intent,
        "operation": operation,
        "instruction_span": structured.instruction_span,
        "subject_span": structured.subject_span,
        "subject": {
            "raw": named_topic.subject_raw if named_topic is not None else (
                subject.raw if subject is not None else data.question
            ),
            "canonical": named_topic.canonical_label if named_topic is not None else (
                subject.canonical or subject.normalized if subject is not None else data.question
            ),
            "normalized": named_topic.subject_normalized if named_topic is not None else (
                subject.normalized if subject is not None else data.question.casefold()
            ),
            "subject_type": "named_topic" if named_topic is not None else (
                subject.subject_type or subject.kind if subject is not None else "query"
            ),
        },
        "typo_resolution": typo_resolution,
        "reason_codes": structured.reason_codes,
        "confidence": min(
            structured.confidence,
            named_topic.confidence if named_topic is not None else 1.0,
        ),
        "ai_used": structured.ai_used,
        "fallback_used": structured.fallback_used,
    }


def display_interpretation(data: QaRequest, prepared: PreparedQuery) -> str:
    """Render controlled Spanish copy exclusively from validated fields."""
    structured = prepared.structured
    named_topic = prepared.named_topic
    if structured.intent in {"relation_query", "comparison_query"} and structured.relations:
        relation = structured.relations[0]
        left = relation.left.canonical or relation.left.raw
        right = relation.right.canonical or relation.right.raw
        if structured.intent == "comparison_query":
            return f"Interpreté que desea comparar «{left}» y «{right}»."
        return f"Interpreté que desea investigar la relación entre «{left}» y «{right}»."
    if named_topic is not None:
        return f"Interpreté que desea investigar referencias sobre {named_topic.canonical_label}."
    if structured.intent in {"literal_lookup", "translation_or_explanation"} and structured.literal_phrases:
        return f"Interpreté que desea localizar la frase «{structured.literal_phrases[0].raw}»."
    if structured.intent == "structural_reference_lookup" and structured.structural_reference:
        return (
            "Interpreté que desea localizar la referencia estructural "
            f"«{structured.structural_reference.raw}»."
        )
    if structured.query_subjects:
        subject = structured.query_subjects[0]
        value = subject.canonical or subject.normalized
        if structured.intent == "concept_cooccurrence":
            return f"Interpreté que desea investigar con qué conceptos se relaciona {value}."
        if structured.intent in {"reference_lookup", "location_lookup"}:
            return f"Interpreté que desea localizar la referencia «{value}»."
        return f"Interpreté que desea investigar el concepto «{value}»."
    return f"Interpreté que desea investigar «{data.question}»."


async def interpret_only(data: QaRequest) -> tuple[PreparedQuery, dict]:
    prepared = await prepare_query(data)
    understanding = query_understanding_contract(data, prepared)
    return prepared, {
        "phase": "interpretation",
        "status": "awaiting_confirmation",
        "original_query": data.question,
        "display_interpretation": display_interpretation(data, prepared),
        "query_understanding": understanding,
        "actions": ["analyze", "modify"],
        "warnings": list(prepared.warnings),
        "execution": {
            "model": RESEARCH_CONVERSATION_MODEL,
            "ai_used": prepared.structured.ai_used,
            "fallback_used": prepared.structured.fallback_used,
            "interpretation_duration_ms": prepared.structured.duration_ms,
            "glossary_duration_ms": prepared.glossary_duration_ms,
            "retrieval_executed": False,
        },
    }


async def run(
    conn,
    data: QaRequest,
    *,
    prepared: PreparedQuery | None = None,
) -> dict:
    started = time.perf_counter()
    warnings: list[str] = []
    prepared = prepared or await prepare_query(data)
    named_topic = prepared.named_topic
    glossary_duration_ms = prepared.glossary_duration_ms
    structured = prepared.structured
    interpretation_warnings = list(prepared.warnings)
    preprocessing = prepared.preprocessing
    intent = structured.intent
    literal_analysis = extract_literal_segments(data.question)
    resolved_question = structured.resolved_context or data.question
    concepts, literal_phrases = _retrieval_inputs(structured)
    named_topic_plan = named_topic_retrieval_plan(named_topic) if named_topic is not None else None
    if named_topic is not None and named_topic_plan is not None:
        named_topic.variants_searched = named_topic_plan["variants_searched"]
        concepts = [{
            "label": named_topic.canonical_label,
            "terms": named_topic_plan["variants_searched"],
            "concept_id": named_topic.canonical_id,
        }]

    # ── Query resolution: typo tolerance / suggestions ──────────────
    # Resolve against the primary extracted subject (not the full question).
    resolution_target = data.question
    if structured.query_subjects:
        resolution_target = structured.query_subjects[-1].raw
    resolution_norm, suggestion_candidates, autoapply_id = resolve_query(resolution_target)
    # Always expand to catalog entry when found (pulls in all corpus forms)
    if autoapply_id and named_topic is None:
        entry = get_concept(autoapply_id)
        if entry:
            concept_terms = [entry.canonical_label, *entry.aliases, *entry.transliterations]
            if entry.hebrew:
                concept_terms.append(entry.hebrew)
            concept_terms = list(dict.fromkeys(concept_terms))
            concepts = [{"label": entry.canonical_label, "terms": concept_terms, "concept_id": entry.concept_id}]
            was_typo = suggestion_candidates and suggestion_candidates[0].suggestion_type != "exact_match"
            if was_typo:
                interpretation_warnings.append(f"suggestion_autoapplied:{entry.concept_id}")
    query_resolution = build_suggestion_contract(data.question, resolution_norm, suggestion_candidates, autoapply_id)
    # ────────────────────────────────────────────────────────────────

    interpretation = structured.model_dump()
    interpretation.update({
        "detected_language": structured.language,
        "normalized_question": data.question,
        "requires_cross_corpus": not bool(structured.requested_works),
        "concepts": [item["label"] for item in concepts],
        "preprocessing": preprocessing,
    })
    warnings.extend(interpretation_warnings)
    requested_works = [work for work in data.works if work in WORKS]
    interpreted_works = [work for work in structured.requested_works if work in requested_works]
    plan_works = interpreted_works or requested_works
    selected_literal: str | None = None
    segmentation_candidates: list[str] = []
    if (
        intent in {"literal_lookup", "translation_or_explanation"}
        and literal_analysis is not None
        and literal_analysis.pdf_glyph_spacing_detected
    ):
        selected_literal, segmentation_candidates = await _resolve_pdf_spaced_literal(
            conn,
            plan_works,
            literal_analysis,
            data.max_hits_per_work,
        )
    has_hebrew_subject = named_topic is not None and named_topic.script == "Hebrew" or any(
        HEBREW_LETTER_RE.search(str(concept["label"]))
        for concept in concepts
    ) or any(HEBREW_LETTER_RE.search(str(item["text"])) for item in literal_phrases)
    primary_language = "he" if has_hebrew_subject else (
        structured.language if structured.language in {"es", "en"} else "es"
    )
    secondary_languages = [
        item for item in ("he", "es", "en") if item != primary_language
    ]
    if selected_literal and literal_analysis is not None:
        reconstructed = reconstruct_pdf_spaced_hebrew(
            literal_analysis.literal_raw,
            selected_literal,
        )
        literal_phrases = [{
            "text": reconstructed,
            "language": "he",
            "script": "Hebrew",
            "word_count": len(selected_literal.split()),
            "content_words": selected_literal.split(),
            "reconstructed": True,
            "search_normalized": selected_literal,
        }]
        concepts = [{"label": selected_literal, "terms": [selected_literal]}]
        interpretation["concepts"] = [selected_literal]
    resolved_literal_query = selected_literal or (
        str(literal_phrases[0].get("search_normalized") or literal_phrases[0]["text"])
        if literal_phrases else None
    )
    interpretation["interface_language"] = structured.language
    interpretation["query_language"] = "he" if has_hebrew_subject else structured.language
    interpretation["primary_retrieval_language"] = primary_language
    interpretation["literal_phrases"] = literal_phrases
    interpretation["intent"] = intent
    if named_topic is not None:
        interpretation.update({
            "operation": "find_named_topic",
            "subject_type": "named_topic",
            "subject_raw": named_topic.subject_raw,
            "subject_canonical": named_topic.canonical_label,
            "alias_resolution": named_topic.model_dump(),
            "language_analysis": {
                "interface_language": structured.language,
                "query_language": "he" if named_topic.script == "Hebrew" else "latin_transliteration",
                "canonical_language": "es",
                "available_scripts": ["Latin", "Hebrew"],
            },
        })
    if literal_analysis is not None and intent in {"literal_lookup", "translation_or_explanation"}:
        interpretation.update({
            "literal_raw": literal_analysis.literal_raw,
            "literal_reconstructed": (
                reconstruct_pdf_spaced_hebrew(literal_analysis.literal_raw, selected_literal)
                if selected_literal else literal_analysis.literal_reconstructed
            ),
            "literal_search_normalized": resolved_literal_query,
            "instruction": literal_analysis.instruction,
            "instruction_language": literal_analysis.instruction_language,
            "pdf_glyph_spacing_detected": literal_analysis.pdf_glyph_spacing_detected,
            "candidate_count": len(segmentation_candidates or literal_analysis.candidates),
            "selected_candidate": selected_literal,
        })
    plan = {
        "queries": [term for concept in concepts for term in concept["terms"]],
        "concept_groups": concepts,
        "works": plan_works,
        "languages": data.languages,
        "primary_language": primary_language,
        "secondary_languages": secondary_languages,
        "literal_phrases": literal_phrases,
        "layers": ["page_literal", "fine_zone", "note_source_unit", "nominal_reference"],
        "include_audit": False,
        "retrieval_mode": "sql_literal_relation_ranked",
        "literal_first": intent in {"literal_lookup", "translation_or_explanation"},
        "include_fts": True,
        "include_trigram": True,
        "include_semantic": data.include_thematic,
        "intent": intent,
        "literal_search_normalized": resolved_literal_query,
        "candidate_count": len(segmentation_candidates or (literal_analysis.candidates if literal_analysis else ())),
        "final_max_hits_per_work": data.max_hits_per_work,
    }
    if named_topic_plan is not None:
        plan.update(named_topic_plan)
    retrieval_started = time.perf_counter()
    candidates: dict[str, dict] = {}
    phrase_matched: set[str] = set()
    if literal_phrases:
        phrase = literal_phrases[0]["text"]
        for work in plan["works"]:
            for row, _title, view in await _phrase_fetch(conn, work, phrase, data.max_hits_per_work * 2):
                key = f"{work}:{stable_hash(str(row['quote']))}"
                entry = candidates.setdefault(key, {"work": work, "row": row, "view": view, "terms": [phrase], "concepts": [phrase]})
                phrase_matched.add(key)
    for work in plan["works"]:
        hebrew_terms_seen: set[str] = set()
        for concept in concepts:
            for term in concept["terms"]:
                if HEBREW_LETTER_RE.search(term) and len(term) < 3:
                    if term in hebrew_terms_seen:
                        continue
                    hebrew_terms_seen.add(term)
                for row, _title, view in await _fetch(conn, work, term, data.max_hits_per_work * 2):
                    key = f"{work}:{stable_hash(str(row['quote']))}"
                    entry = candidates.setdefault(key, {"work": work, "row": row, "view": view, "terms": [], "concepts": []})
                    if term not in entry["terms"]:
                        entry["terms"].append(term)
                    if concept["label"] not in entry["concepts"]:
                        entry["concepts"].append(concept["label"])
    hits = [classify(
        entry["work"], entry["row"], entry["terms"], entry["concepts"], entry["view"],
        primary_language=primary_language,
        secondary_languages=secondary_languages,
        named_topic=named_topic,
    ) for entry in candidates.values()]
    for hit in hits:
        if hit.hit_id and any(hit.quote == c.get("row", {}).get("quote", "") for c_key, c in candidates.items() if c_key in phrase_matched):
            if hit.literal_match_kind == "none":
                object.__setattr__(hit, "literal_match_kind", "exact_phrase")
            if hit.language_match == "fallback":
                object.__setattr__(hit, "language_match", "exact")
            object.__setattr__(hit, "retrieval_tier", 0)
    _mark_same_page(hits)
    hits.sort(key=_sort_key)
    hits = _cap_hits_with_language_coverage(hits, data.max_hits_per_work, data.languages)
    generative_intents = {"relation_query", "comparison_query", "translation_or_explanation"}
    ai_markdown, render_warnings, claims = await _ai_render(resolved_question, hits) if data.ai.enabled and hits and intent in generative_intents else (None, [], [])
    warnings.extend(render_warnings)
    source_layer_followup = intent == "follow_up" and _is_source_layer_followup(data.question)
    claims = _source_layer_followup_claims(hits, structured.instruction_language) if source_layer_followup else (
        claims or _deterministic_claims(
            resolved_question,
            hits,
            intent,
            resolved_literal_query,
            len(concepts),
            structured.instruction_language,
            named_topic,
        )
    )
    primary_ids = _apply_claim_traceability(hits, claims)
    counts = _counts(hits, primary_ids)
    warnings.extend(warning for hit in hits for warning in hit.warnings)
    for hit in hits:
        if hit.snippet_sanitized:
            warnings.append(f"evidence_snippet_sanitized:{hit.hit_id}")
    status = "ok" if primary_ids else "no_evidence"
    narrative_question = data.question if source_layer_followup else resolved_question
    markdown = ai_markdown or render(
        narrative_question,
        claims,
        hits,
        warnings,
        intent,
        source_layer_followup=source_layer_followup,
        named_topic=named_topic,
    )
    retrieval_duration_ms = round((time.perf_counter() - retrieval_started) * 1000, 2)
    summary = build_summary(counts["primary"], counts["contextual"], counts["additional_literal"])
    matrix = [{
        "work_code": work,
        "hits": sum(hit.work_code == work for hit in hits),
        "primary_hits": sum(hit.work_code == work and hit.is_primary for hit in hits),
        "contextual_hits": sum(hit.work_code == work and hit.relation_relevance not in {"single_term_literal", "unrelated_literal_noise"} and not hit.is_primary for hit in hits),
        "additional_literal_hits": sum(hit.work_code == work and hit.relation_relevance in {"single_term_literal", "unrelated_literal_noise"} for hit in hits),
    } for work in plan["works"] if sum(hit.work_code == work for hit in hits) > 0]
    if query_resolution and query_resolution.get("suggestion_applied"):
        warnings.append(
            f"No encontré una coincidencia exacta para "
            f"«{data.question}». "
            f"Busqué la variante probable "
            f"«{query_resolution['suggested_query']}»."
        )

    response_intent = "source_layer_question" if source_layer_followup else intent
    target_evidence_id = primary_ids[0] if source_layer_followup and primary_ids else None
    return {
        "question": data.question,
        "intent": response_intent,
        "target_evidence_id": target_evidence_id,
        "same_primary_evidence": bool(target_evidence_id) if source_layer_followup else None,
        "status": status,
        "answer_text": markdown,
        "answer_markdown": markdown,
        "summary": summary,
        "conversation": {"conversation_id": data.conversation.get("conversation_id"), "turn_id": data.conversation.get("turn_id"), "resolved_context": [resolved_question] if resolved_question != data.question else []},
        "query_resolution": query_resolution,
        "query_understanding": {
            "original_query": data.question,
            "intent": intent,
            "operation": "find_named_topic" if named_topic is not None else None,
            "subject_type": "named_topic" if named_topic is not None else (
                structured.query_subjects[0].kind if structured.query_subjects else None
            ),
            "subject_raw": named_topic.subject_raw if named_topic is not None else (
                structured.query_subjects[0].raw if structured.query_subjects else None
            ),
            "subject_canonical": named_topic.canonical_label if named_topic is not None else None,
            "ai_used": structured.ai_used,
            "ai_accepted": structured.ai_used and not structured.fallback_used,
            "fallback_used": structured.fallback_used,
            "requires_clarification": named_topic.requires_clarification if named_topic is not None else False,
        },
        "named_topic": ({
            "canonical_id": named_topic.canonical_id,
            "canonical_label": named_topic.canonical_label,
            "topic_type": named_topic.topic_type,
            "matched_alias": named_topic.matched_alias,
            "alias_match_kind": named_topic.match_kind,
            "match_language": named_topic.language,
            "match_script": named_topic.script,
            "variants_searched": named_topic.variants_searched,
        } if named_topic is not None else None),
        "interpretation": interpretation,
        "search_plan": plan,
        "works_consulted": plan["works"],
        "hits": [hit.model_dump() for hit in hits],
        "evidence_matrix": matrix,
        "cross_corpus_matrix": [],
        "claims": claims,
        "primary_evidence_ids": primary_ids,
        "evidence_counts": counts,
        "not_found": [] if primary_ids else [item["label"] for item in concepts],
        "warnings": list(dict.fromkeys(warnings)),
        "execution": {
            "pipeline_version": "investigative_qa_v1_traceable",
            "model": RESEARCH_CONVERSATION_MODEL,
            "used_ai_interpretation": structured.ai_used,
            "ai_used": structured.ai_used,
            "fallback_used": structured.fallback_used,
            "interpretation_duration_ms": structured.duration_ms,
            "glossary_duration_ms": glossary_duration_ms,
            "retrieval_duration_ms": retrieval_duration_ms,
            "interpreted_intent": structured.intent,
            "interpreted_language": structured.language,
            "subject_count": len(structured.query_subjects) or len(concepts),
            "retrieval_modes": ["literal", "phrase", "fts", "trigram"],
            "used_ai_rendering": bool(ai_markdown),
            "ai_render_validated": bool(ai_markdown),
            "used_deterministic_fallback": not bool(ai_markdown),
            "used_vector": False,
            "used_external_sources": False,
            "used_ocr": False,
            "database": "postgresql",
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        },
    }
