"""Deterministic concept expansion, evidence classification and source mapping."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from modules.library.relation_qa_schemas import EvidenceType, RelationQASource


CONCEPT_EXPANSIONS: dict[str, list[str]] = {
    "sangre": ["sangre", "blood", "דם", "dam"],
    "blood": ["blood", "sangre", "דם", "dam"],
    "דם": ["דם", "dam", "sangre", "blood"],
    "habla": [
        "habla", "hablar", "palabra", "dibur", "dibbur", "speech",
        "speaking", "דיבור", "דבור", "דבר", "פה", "plegaria",
    ],
    "speech": [
        "speech", "speaking", "word", "habla", "palabra", "dibur",
        "dibbur", "דיבור", "דבור", "דבר", "פה",
    ],
    "דיבור": [
        "דיבור", "דבור", "דבר", "dibur", "dibbur", "habla", "speech",
        "palabra", "פה",
    ],
    "puntos buenos": [
        "puntos buenos", "punto bueno", "poco de bien", "Azamra",
        "aún un poco de bien", "Likutey Moharán 282", "ועוד מעט",
    ],
    "poco de bien": [
        "poco de bien", "aún un poco de bien", "puntos buenos", "Azamra",
        "Likutey Moharán 282", "ועוד מעט",
    ],
    "noche": [
        "noche", "medianoche", "jatzot", "chatzot", "Tikún Jatzot",
        "חצות", "חצות לילה", "לילה",
    ],
    "jatzot": [
        "jatzot", "chatzot", "medianoche", "Tikún Jatzot", "Tikun Chatzot",
        "dividiendo la noche", "חצות", "חצות לילה",
    ],
    "tzafón": ["tzafón", "tzafon", "tzafun", "norte", "north", "צפון", "מצפון"],
    "tzafon": ["tzafon", "tzafón", "tzafun", "norte", "north", "צפון", "מצפון"],
    "mal": ["mal", "evil", "הרעה", "רע", "Jeremías 1:14", "Yirmiyahu 1:14"],
    "elevar": ["elevar", "elevando", "elevación", "levantar", "עלה"],
    "dibur": ["dibur", "dibbur", "habla", "palabra", "דיבור", "דבור", "פה"],
    "bereshit rabah": [
        "Bereshit Rabah", "Bereshit Rabbah", "Bereishit Rabbah",
        "Bereshit Rabba", "Midrash Rabah", "Midrash Rabbah", "בראשית רבה",
    ],
    "midrash": ["midrash", "Midrash Rabah", "Midrash Rabbah", "Bereshit Rabah", "מדרש"],
}

_RABBINIC_PATTERN = re.compile(
    r"\b(midrash|bereshit rabb?a?h|guemará|gemara|talmud|zohar|avot|rash[ií])\b|"
    r"בראשית רבה|מדרש|תלמוד|זוהר",
    re.IGNORECASE,
)
_BIBLICAL_PATTERN = re.compile(
    r"\b(salmos?|tehilim|jerem[ií]as|yirmiyahu|g[eé]nesis|bereshit|"
    r"[ée]xodo|shemot|deuteronomio|devarim|proverbios|mishl[eé])\b"
    r"(?:\s+\d{1,3}(?::\d{1,3})?)?",
    re.IGNORECASE,
)
_REMEZ_PATTERN = re.compile(r"\b(remez|alusi[oó]n|indicio)\b|רמז", re.IGNORECASE)
_DERASH_PATTERN = re.compile(
    r"\b(derash|drash|interpretaci[oó]n simb[oó]lica|explica simb[oó]licamente)\b|דרש",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class EvidenceClassification:
    primary: EvidenceType
    types: tuple[EvidenceType, ...]
    editorial_role: str
    is_final_citation: bool


def _normalized(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in folded if not unicodedata.combining(char))


def expand_concept_variants(concept: str, language: str) -> list[str]:
    """Expand a concept through the validated editorial vocabulary."""
    label = concept.strip()
    key = _normalized(label)
    variants = CONCEPT_EXPANSIONS.get(key)
    if variants is None:
        variants = next(
            (
                values
                for candidate, values in CONCEPT_EXPANSIONS.items()
                if key == _normalized(candidate)
                or any(key == _normalized(value) for value in values)
            ),
            [label],
        )
    ordered = [label, *variants]
    return list(dict.fromkeys(value.strip() for value in ordered if value.strip()))


def extract_concepts_from_question(question: str) -> tuple[str, str]:
    """Extract two concepts with bounded deterministic relation patterns."""
    value = question.strip().rstrip("?.!")
    patterns = (
        r"(?:conexi[oó]n|relaci[oó]n)\s+entre\s+(.+?)\s+y\s+(.+)$",
        r"(?:connection|relation)\s+between\s+(.+?)\s+and\s+(.+)$",
        r"(?:קשר|חיבור)\s+בין\s+(.+?)\s+(?:ו|לבין)\s*(.+)$",
    )
    for pattern in patterns:
        match = re.search(pattern, value, re.IGNORECASE)
        if match:
            return match.group(1).strip(), match.group(2).strip()

    tokens = re.findall(r"[\w\u0590-\u05ffáéíóúüñÁÉÍÓÚÜÑ]+", value)
    stop = {
        "donde", "dónde", "aparece", "esta", "está", "que", "qué", "como",
        "cómo", "idea", "ensenanza", "enseñanza", "the", "where", "what",
        "is", "are", "and", "entre", "sobre", "corpus", "breslov",
    }
    meaningful = [token for token in tokens if token.casefold() not in stop and len(token) > 2]
    if len(meaningful) >= 2:
        return meaningful[-2], meaningful[-1]
    if meaningful:
        return meaningful[0], meaningful[0]
    return "concepto A", "concepto B"


def build_relation_patterns(
    concept_a_variants: Sequence[str],
    concept_b_variants: Sequence[str],
) -> list[str]:
    """Build bounded literal phrases for PG relation-pattern retrieval."""
    patterns: list[str] = []
    for concept_a in concept_a_variants[:3]:
        for concept_b in concept_b_variants[:3]:
            patterns.extend(
                [
                    f"conexión entre {concept_a} y {concept_b}",
                    f"relación entre {concept_a} y {concept_b}",
                    f"{concept_a} se relaciona con {concept_b}",
                    f"{concept_a} corresponde a {concept_b}",
                    f"{concept_a} es aspecto de {concept_b}",
                    f"{concept_a} es paralelo de {concept_b}",
                    f"{concept_a} está conectado con {concept_b}",
                    f"{concept_a} está asociado con {concept_b}",
                    f"connection between {concept_a} and {concept_b}",
                    f"relation between {concept_a} and {concept_b}",
                    f"{concept_a} is linked to {concept_b}",
                    f"{concept_a} is associated with {concept_b}",
                    f"{concept_a} corresponds to {concept_b}",
                    f"{concept_a} is an aspect of {concept_b}",
                    f"קשר בין {concept_a} ו{concept_b}",
                    f"חיבור בין {concept_a} ו{concept_b}",
                    f"{concept_a} בחינת {concept_b}",
                    f"{concept_a} שייך ל{concept_b}",
                ]
            )
    return list(dict.fromkeys(patterns))


def _contains_any(text: str, variants: Sequence[str]) -> bool:
    normalized_text = _normalized(text)
    for value in variants:
        normalized_value = _normalized(value)
        if len(normalized_value) < 2:
            continue
        has_hebrew = any("\u0590" <= char <= "\u05ff" for char in value)
        if has_hebrew:
            if normalized_value in normalized_text:
                return True
        elif re.search(rf"(?<!\w){re.escape(normalized_value)}(?!\w)", normalized_text):
            return True
    return False


def _contains_explicit_relation(
    text: str,
    concept_a_variants: Sequence[str],
    concept_b_variants: Sequence[str],
) -> bool:
    normalized_text = _normalized(text)
    return any(
        _normalized(pattern) in normalized_text
        for pattern in build_relation_patterns(concept_a_variants, concept_b_variants)
    )


def classify_evidence(
    row: dict[str, Any],
    concept_a_variants: Sequence[str],
    concept_b_variants: Sequence[str],
) -> EvidenceClassification:
    """Classify canonical PG evidence without promoting inference to literal."""
    text = str(row.get("content") or "")
    block_type = str(row.get("block_type") or "")
    block_subtype = str(row.get("block_subtype") or "")
    evidence_role = str(row.get("evidence_role") or "")
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    citable = bool(row.get("citable", True))
    types: list[EvidenceType] = []

    has_a = _contains_any(text, concept_a_variants)
    has_b = _contains_any(text, concept_b_variants)
    ambiguous_davar = "דבר" in text and not any(token in text for token in ("דיבור", "דבור"))

    if block_type == "composite_page_context" or evidence_role == "composite_for_retrieval":
        types.append(EvidenceType.excluded_false_positive)
        citable = False
    if block_type == "internal_cross_reference":
        types.append(EvidenceType.internal_cross_reference)
    if block_type == "source_hebrew":
        types.append(EvidenceType.source_hebrew)
    if block_type == "footnote":
        types.append(EvidenceType.footnote_reference)
    if block_type == "marginal_source":
        types.append(EvidenceType.marginal_source)
    if block_type == "main_explanation_es" or evidence_role == "commentary":
        types.append(EvidenceType.editorial_explanation)
    if block_subtype == "biblical_citation" or _BIBLICAL_PATTERN.search(text):
        types.append(EvidenceType.biblical_citation)
    if block_subtype == "rabbinic_reference" or _RABBINIC_PATTERN.search(text):
        types.append(EvidenceType.rabbinic_source)
    if block_subtype == "breslov_teaching" or evidence_role in {"source_text", "direct_quote"}:
        types.append(EvidenceType.breslov_text)
    if row.get("document_status") == "ready" and not block_type:
        types.append(EvidenceType.breslov_text)
    if block_subtype == "halachic_derash" or evidence_role == "halachic_derash" or _DERASH_PATTERN.search(text):
        types.append(EvidenceType.derash_interpretation)
    if _REMEZ_PATTERN.search(text):
        types.append(EvidenceType.remez_hint)
    if block_subtype == "paraphrase" or evidence_role == "paraphrase":
        types.append(EvidenceType.paraphrase)
    if metadata.get("source_refs"):
        types.append(EvidenceType.explicit_reference)

    if has_a and has_b and _contains_explicit_relation(
        text, concept_a_variants, concept_b_variants
    ):
        types.append(EvidenceType.literal_relation)
    elif has_a and has_b:
        types.append(EvidenceType.cooccurrence_same_chunk)
    elif has_a or has_b:
        types.append(EvidenceType.literal_phrase)
    elif "vector" in row.get("retrieval_methods", []):
        types.append(EvidenceType.thematic_relation)
    else:
        types.append(EvidenceType.not_found)

    if ambiguous_davar:
        types.append(EvidenceType.ambiguous)

    types = list(dict.fromkeys(types))
    priority = (
        EvidenceType.excluded_false_positive,
        EvidenceType.literal_relation,
        EvidenceType.biblical_citation,
        EvidenceType.rabbinic_source,
        EvidenceType.footnote_reference,
        EvidenceType.marginal_source,
        EvidenceType.source_hebrew,
        EvidenceType.internal_cross_reference,
        EvidenceType.editorial_explanation,
        EvidenceType.breslov_text,
        EvidenceType.derash_interpretation,
        EvidenceType.remez_hint,
        EvidenceType.cooccurrence_same_chunk,
        EvidenceType.literal_phrase,
        EvidenceType.thematic_relation,
        EvidenceType.ambiguous,
        EvidenceType.not_found,
    )
    primary = next(value for value in priority if value in types)
    editorial_role = evidence_role or {
        "footnote": "bibliographic_note",
        "marginal_source": "marginal_citation",
        "source_hebrew": "source_text",
        "main_explanation_es": "editorial_explanation",
        "internal_cross_reference": "cross_reference",
    }.get(block_type, "breslov_text")
    return EvidenceClassification(
        primary=primary,
        types=tuple(types),
        editorial_role=editorial_role,
        is_final_citation=citable and block_type != "composite_page_context",
    )


def merge_candidate_rows(*groups: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate by chunk_id while preserving retrieval signals and best score."""
    merged: dict[str, dict[str, Any]] = {}
    for group in groups:
        for row in group:
            chunk_id = str(row.get("chunk_id") or "")
            if not chunk_id:
                continue
            methods = list(row.get("retrieval_methods") or [])
            if chunk_id not in merged:
                row["retrieval_methods"] = methods
                merged[chunk_id] = row
                continue
            current = merged[chunk_id]
            current["retrieval_methods"] = list(
                dict.fromkeys([*current.get("retrieval_methods", []), *methods])
            )
            current["score"] = max(
                float(current.get("score") or 0.0), float(row.get("score") or 0.0)
            )
    return list(merged.values())


def _snippet(content: str, variants: Sequence[str], max_chars: int) -> str:
    text = " ".join(content.split())
    if len(text) <= max_chars:
        return text
    normalized = _normalized(text)
    positions = [normalized.find(_normalized(value)) for value in variants if value]
    positions = [position for position in positions if position >= 0]
    center = min(positions) if positions else 0
    start = max(0, center - max_chars // 3)
    end = min(len(text), start + max_chars)
    return ("…" if start else "") + text[start:end].strip() + ("…" if end < len(text) else "")


def _metadata_refs(metadata: dict[str, Any], key: str) -> list[dict[str, Any]]:
    raw = metadata.get(key, [])
    if key == "internal_cross_refs" and not raw:
        raw = metadata.get("cross_refs", [])
    if not isinstance(raw, list):
        return []
    return [value for value in raw if isinstance(value, dict)]


def build_source_map(
    rows: Sequence[dict[str, Any]],
    concept_a_variants: Sequence[str],
    concept_b_variants: Sequence[str],
    evidence_depth: str,
    top_k: int,
) -> list[RelationQASource]:
    """Map canonical PG rows to auditable source objects."""
    max_chars = {"compact": 180, "standard": 300, "full": 500}[evidence_depth]
    variants = [*concept_a_variants, *concept_b_variants]
    sources: list[RelationQASource] = []
    for row in rows:
        content = str(row.get("content") or "")
        chunk_id = str(row.get("chunk_id") or "")
        if not content or not chunk_id or not row.get("document_id"):
            continue
        classification = classify_evidence(row, concept_a_variants, concept_b_variants)
        if classification.primary == EvidenceType.not_found:
            continue
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        methods = list(row.get("retrieval_methods") or ["postgresql"])
        sources.append(
            RelationQASource(
                source_id=f"src_{chunk_id.replace('-', '')}",
                document_id=str(row["document_id"]),
                document_title=str(row.get("document_title") or ""),
                document_status=str(row.get("document_status") or ""),
                page_number=row.get("page_start"),
                section=str(row.get("section") or ""),
                chapter=str(row.get("chapter") or ""),
                subtitle=str(row.get("subtitle") or ""),
                node_path=str(row.get("node_path") or ""),
                block_type=str(row.get("block_type") or ""),
                language=str(row.get("language") or ""),
                chunk_id=chunk_id,
                evidence_type=classification.primary,
                evidence_types=list(classification.types),
                editorial_role=classification.editorial_role,
                retrieval_method="+".join(methods),
                score=round(float(row.get("score") or 0.0), 4),
                citable=bool(row.get("citable", True)),
                is_final_citation=classification.is_final_citation,
                snippet=_snippet(content, variants, max_chars),
                source_refs=_metadata_refs(metadata, "source_refs"),
                internal_cross_refs=_metadata_refs(metadata, "internal_cross_refs"),
            )
        )
    priority = {
        EvidenceType.literal_relation: 0,
        EvidenceType.biblical_citation: 1,
        EvidenceType.rabbinic_source: 2,
        EvidenceType.footnote_reference: 3,
        EvidenceType.marginal_source: 4,
        EvidenceType.source_hebrew: 5,
        EvidenceType.editorial_explanation: 6,
        EvidenceType.breslov_text: 7,
        EvidenceType.cooccurrence_same_chunk: 8,
        EvidenceType.literal_phrase: 9,
        EvidenceType.thematic_relation: 10,
        EvidenceType.ambiguous: 11,
        EvidenceType.not_found: 12,
        EvidenceType.excluded_false_positive: 13,
    }
    sources.sort(key=lambda item: (priority.get(item.evidence_type, 10), -item.score))
    return sources[:top_k]


def validate_sources_resolve_to_pg(sources: Sequence[RelationQASource]) -> None:
    """Fail closed when a final source is not canonical or violates citation rules."""
    seen: set[str] = set()
    for source in sources:
        if not source.chunk_id or not source.document_id or not source.snippet:
            raise ValueError("Every relation QA source must resolve to canonical PostgreSQL text")
        if source.chunk_id in seen:
            raise ValueError("Duplicate chunk_id in relation QA source map")
        seen.add(source.chunk_id)
        if source.block_type == "composite_page_context" and source.is_final_citation:
            raise ValueError("composite_page_context cannot be a final citation")
        if "content_preview" in source.retrieval_method:
            raise ValueError("Milvus content_preview cannot be a final source")
