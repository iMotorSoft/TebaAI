"""Bibliographic Query Planner V1.

Resolves bibliographic locator queries:
  "Azamra, ¿en qué tomo de Likutey Halajot está?"
  → intent=bibliographic_locator
  → subject=Azamra
  → scope=work:Likutey Halajot
  → return_dimension=volume

Builds on Page-First Evidence Contract V1.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# -- Enums and types ------------------------------------------------------


class Intent(str, Enum):
    UNKNOWN = "unknown"
    BIBLIOGRAPHIC_LOCATOR = "bibliographic_locator"
    CONCEPT_EXPLANATION = "concept_explanation"
    GENERAL_QUERY = "general_query"


class PresenceType(str, Enum):
    LITERAL_EXACT = "literal_exact"
    LITERAL_NORMALIZED = "literal_normalized"
    HEBREW_EXACT = "hebrew_exact"
    BIBLIOGRAPHIC_REFERENCE = "bibliographic_reference"
    THEMATIC_DEVELOPMENT = "thematic_development"
    UNKNOWN = "unknown"


class VolumeSource(str, Enum):
    EXPLICIT_METADATA = "explicit_metadata"
    DOCUMENT_TITLE = "document_title"
    DOCUMENT_CODE = "document_code"
    FILENAME = "filename"
    CATALOGUE = "catalogue"
    EDITION_LABEL = "edition_label"
    SECTION_PATH = "section_path"
    CONTROLLED_INFERENCE = "controlled_inference"
    UNRESOLVED = "unresolved"


class VolumeConfidence(str, Enum):
    EXACT = "exact"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNRESOLVED = "unresolved"


class ResolutionMethod(str, Enum):
    EXPLICIT_PAGE_ID = "explicit_page_id"
    PAGE_ANCHOR = "page_anchor"
    CHUNK_PAGE_START = "chunk_page_start"
    PAGE_MARKER_INFERENCE = "page_marker_inference"


# -- Domain models --------------------------------------------------------


@dataclass(frozen=True)
class BibliographicSubject:
    """The concept or subject being located."""
    surface: str
    canonical: str
    subject_type: str = "concept"
    variants: list[str] = field(default_factory=list)
    hebrew_variants: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    resolution_method: str = "literal"
    confidence: float = 1.0


@dataclass(frozen=True)
class BibliographicScope:
    """The work scope for the bibliographic query."""
    surface: str
    canonical_label: str
    resolved_work_id: str | None = None
    document_ids: list[str] = field(default_factory=list)
    canonical_label_variants: list[str] = field(default_factory=list)
    resolution_method: str = "literal"
    confidence: float = 1.0
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class QueryPlan:
    """Structured plan derived from the user question."""
    intent: Intent = Intent.UNKNOWN
    subject: BibliographicSubject | None = None
    scope: BibliographicScope | None = None
    return_dimensions: list[str] = field(default_factory=lambda: ["volume"])
    group_by: list[str] = field(default_factory=lambda: ["volume"])
    require_evidence: bool = True
    allow_thematic_secondary: bool = True
    warnings: list[str] = field(default_factory=list)
    plan_source: str = "deterministic"


@dataclass(frozen=True)
class ResolvedVolume:
    """A resolved volume/tome with bibliographic metadata."""
    volume_id: str | None = None
    volume_number: int | None = None
    volume_label: str | None = None
    volume_source: VolumeSource = VolumeSource.UNRESOLVED
    volume_confidence: VolumeConfidence = VolumeConfidence.UNRESOLVED
    document_id: str | None = None
    document_title: str | None = None
    edition_label: str | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class BibliographicOccurrence:
    """A single occurrence of the concept within a work/volume."""
    occurrence_id: str
    document_id: str
    document_title: str
    volume: ResolvedVolume
    presence_type: PresenceType
    pdf_page: int | None = None
    printed_page: int | None = None
    section_title: str | None = None
    heading_text: str | None = None
    exact_quote: str | None = None
    evidence_id: str | None = None
    chunk_id: str | None = None
    match_type: str = "literal"


@dataclass(frozen=True)
class BibliographicResult:
    """Grouped bibliographic result per volume."""
    work: str
    volume: ResolvedVolume | None = None
    occurrence_count: int = 0
    presence_types: list[str] = field(default_factory=list)
    primary_evidence_id: str | None = None
    evidence_ids: list[str] = field(default_factory=list)
    occurrences: list[BibliographicOccurrence] = field(default_factory=list)
    pages: list[int] = field(default_factory=list)
    sections: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class BibliographicAnswer:
    """Full bibliographic answer data."""
    query_plan: QueryPlan
    results: list[BibliographicResult] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    answer_text: str = ""
    answer_markdown: str = ""
    warnings: list[str] = field(default_factory=list)
    status: str = "complete"


# -- Intent classifier ----------------------------------------------------

# Patterns suggesting bibliographic locator intent
_BIBLIOGRAPHIC_PATTERNS = [
    re.compile(r"(?:en\s*qué|qué|cuál|dónde)\s*(?:tomo|volumen|parte|volume)", re.I),
    re.compile(r"(?:qué|cuál|dónde)\s*(?:tomo|volumen|parte)", re.I),
    re.compile(r"(?:tomo|volumen)\s*\d", re.I),
    re.compile(r"(?:en\s*qué|dónde)\s*est[áa]", re.I),
    re.compile(r"(?:en\s*qué)\s*(?:tomo|volumen|parte|obra|documento)", re.I),
    re.compile(r"(?:localiz[a-záéíóú]|ubic[a-záéíóú]|b[uú]scame|encontrar)", re.I),
]

# Subject extraction patterns (concept before comma/preposition, or after key question words)
_SUBJECT_PATTERNS = [
    # Subject before comma
    re.compile(r"^([A-Za-zÁÉÍÓÚÜÑáéíóúüñ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9\s\-]+?)[,;:]", re.I),
    # Subject before 'en', 'de', 'dentro' at start
    re.compile(r"^([A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{3,}(?:\s+[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{3,}){0,3})\s+(?:en|de|dentro)\s", re.I),
    # Subject after verbs like 'aparece', 'está', 'busca', 'encuentra'
    re.compile(r"(?:aparece|está|busca|encuentra|trata sobre|enseñanza de|concepto de|término)\s+([A-Za-zÁÉÍÓÚÜÑáéíóúüñ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9\s\-]{2,}?)(?:\s*[¿?]|\s+en|\s+de|\s+dentro|$)", re.I),
    # Subject at end after 'de'/'en' work reference (for reordered queries)
    re.compile(r"(?:de|en)\s+[A-Za-zÁÉÍÓÚÜÑáéíóúüñ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9\s\-]+?\s+(?:aparece|está|trata|encuentra|busca)\s+([A-Za-zÁÉÍÓÚÜÑáéíóúüñ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9\s\-]+?)(?:\s*[¿?]|$)", re.I),
    # Isolated capitalized word that's not at start (e.g. mid-sentence)
    re.compile(r"[\s,;:]\s*([A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+(?:\s+[A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+)?)(?:\s*[¿?,;]|$)", re.I),
]

# Stopwords that should never be treated as subjects
_STOPWORDS = {
    "qué", "cuál", "dónde", "cuántas", "cuántos", "cuánto",
    "cómo", "por qué", "en qué", "de qué", "para qué",
    "quién", "quiénes", "cuándo",
    # English
    "what", "which", "where", "how", "why", "when", "who",
    # Greetings and fillers
    "hola", "hey", "oye", "por favor", "gracias",
}

# Fallback: extract the first capitalized multi-word term as subject
_FALLBACK_SUBJECT = re.compile(r"([A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+(?:\s+[A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+)*)", re.I)

# Work extraction patterns
_WORK_STOP_WORDS = {
    "está", "esta", "aparece", "trata", "encuentra", "busca",
    "dónde", "donde", "cómo", "como", "qué", "que",
    "tomo", "volumen", "volume", "parte",
}

_WORK_PATTERNS = [
    # 'de Likutey Halajot' - work after 'de' preposition
    re.compile(r"\bde\s+((?:(?:[A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+)\s?){1,4})(?=\s*[¿?,;]|\s+est[áa]|\s+aparece|\s+trata|\s+en|\s+de|$)", re.I),
    # 'en Likutey Halajot' - work after 'en' preposition
    re.compile(r"\ben\s+((?:(?:[A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+)\s?){1,4})(?=\s*[¿?,;]|\s+est[áa]|\s+aparece|\s+trata|\s+de|$)", re.I),
    # 'obra Likutey Halajot' or 'libro'
    re.compile(r"(?:obra|libro|texto|documento)\s+((?:(?:[A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+)\s?){1,4})(?=\s*[¿?]|$)", re.I),
]

def _clean_work_candidate(candidate: str) -> str:
    """Clean a work candidate by removing trailing stop words."""
    words = candidate.strip().split()
    cleaned = []
    for w in words:
        if w.lower().strip("¿?,.;:!") in _WORK_STOP_WORDS:
            break
        cleaned.append(w.rstrip("¿?,.;:!"))
    result = " ".join(cleaned).strip()
    # Ensure at least 2 chars and at least one meaningful word
    if len(result) < 2:
        return ""
    return result


def classify_intent(query: str) -> tuple[Intent, dict[str, str]]:
    """Classify the research intent from the query string.

    Returns (intent, extracted_info) where info contains subject and work.
    """
    info: dict[str, str] = {}

    # Normalize query for pattern matching
    clean_q = query.strip().lstrip("¿").strip()

    # Check bibliographic patterns
    is_bibliographic = any(p.search(clean_q) for p in _BIBLIOGRAPHIC_PATTERNS)
    
    # Extract subject: try patterns first, then fallback to first capitalized word
    for pat in _SUBJECT_PATTERNS:
        m = pat.search(clean_q)
        if m:
            subject = m.group(1).strip()
            subject = re.sub(r'\s+(?:en|de|dentro|para|sobre)$', '', subject, flags=re.I).strip()
            if len(subject) >= 2:
                info["subject"] = subject
                break
    
    # Fallback: if no subject found, look for the first long word that isn't a stopword
    if "subject" not in info:
        words = re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{4,}", clean_q)
        for w in words:
            if w.lower() not in _STOPWORDS and w.lower() not in {
                "likutey", "halajot", "halachot", "halachos", "moharán", "moharan",
                "volumen", "volume", "tomo", "parte", "dónde", "donde",
            }:
                info["subject"] = w
                break
    
    # Extract work (after extracting subject to avoid conflicts)
    for pat in _WORK_PATTERNS:
        m = pat.search(clean_q)
        if m:
            work = _clean_work_candidate(m.group(1))
            if len(work) >= 2:
                info["work"] = work
                break
    
    # Detect volume keyword
    has_volume_keyword = bool(re.search(r'(?:tomo|volumen|volume|parte)\s', clean_q, re.I))
    has_donde_keyword = bool(re.search(r'(?:dónde|donde)\s+est[áa]', clean_q, re.I))

    if is_bibliographic or has_volume_keyword or (has_donde_keyword and info.get("subject")):
        return Intent.BIBLIOGRAPHIC_LOCATOR, info
    
    if info.get("subject") or info.get("work"):
        return Intent.GENERAL_QUERY, info
    
    return Intent.UNKNOWN, info


# -- Subject resolver -----------------------------------------------------


def resolve_subject(surface: str) -> BibliographicSubject:
    """Resolve a surface subject to canonical form.

    Handles known concept aliases and Hebrew variants.
    """
    clean = surface.strip().strip("¿?")
    canonical = clean
    variants: list[str] = []
    hebrew_variants: list[str] = []
    aliases: list[str] = []

    # Known concept registry
    CONCEPT_REGISTRY: dict[str, dict[str, Any]] = {
        "azamra": {
            "canonical": "Azamra",
            "variants": ["azamra", "AZAMRA"],
            "hebrew": ["אזמרה", "אֲזַמְּרָה"],
            "aliases": ["Likutey Moharán 282", "LM 282", "Torá 282",
                        "Likutey Moharan 282", "LM I, 282"],
        },
    }

    key = clean.lower().strip()
    if key in CONCEPT_REGISTRY:
        entry = CONCEPT_REGISTRY[key]
        canonical = entry["canonical"]
        variants = entry.get("variants", [])
        hebrew_variants = entry.get("hebrew", [])
        aliases = entry.get("aliases", [])
    else:
        # Check aliases
        for ckey, centry in CONCEPT_REGISTRY.items():
            if clean.lower() in [a.lower() for a in centry.get("aliases", [])]:
                canonical = centry["canonical"]
                variants = centry.get("variants", [])
                hebrew_variants = centry.get("hebrew", [])
                aliases = centry.get("aliases", [])
                break

    return BibliographicSubject(
        surface=clean,
        canonical=canonical,
        variants=list(set([surface] + variants)),
        hebrew_variants=hebrew_variants,
        aliases=aliases,
    )


# -- Work resolver --------------------------------------------------------


def resolve_work_scope(
    surface: str,
    document_rows: list[dict[str, Any]],
) -> BibliographicScope:
    """Resolve a work surface to canonical IDs and documents.

    Accepts document rows from the database with id, title, status, etc.
    """
    clean = surface.strip().strip("¿?")

    # Known work family
    WORK_FAMILIES: dict[str, dict[str, Any]] = {
        "likutey halajot": {
            "canonical": "Likutey Halajot",
            "variants": [
                "likutey halajot", "likutey halachot", "likutey halachos",
                "likutey halajot explicado",
            ],
        },
    }

    key = clean.lower().strip()
    family = None
    for fkey, fval in WORK_FAMILIES.items():
        if key == fkey or key in fval.get("variants", []):
            family = fval
            break

    if family is None:
        return BibliographicScope(
            surface=clean,
            canonical_label=clean,
            resolution_method="unresolved",
            confidence=0.0,
            warnings=["work_not_recognized"],
        )

    # Find matching documents
    canonical = family["canonical"]
    variants = family.get("variants", [])
    doc_ids: list[str] = []
    matched_docs: list[dict[str, Any]] = []

    for doc in document_rows:
        title = str(doc.get("title", "")).lower()
        if any(v in title for v in variants):
            doc_ids.append(str(doc.get("id", "")))
            matched_docs.append(doc)

    if not doc_ids:
        return BibliographicScope(
            surface=clean,
            canonical_label=canonical,
            resolution_method="not_in_corpus",
            confidence=0.0,
            warnings=["no_documents_found"],
        )

    return BibliographicScope(
        surface=clean,
        canonical_label=canonical,
        resolved_work_id=doc_ids[0] if len(doc_ids) == 1 else str(doc_ids),
        document_ids=doc_ids,
        canonical_label_variants=variants,
        resolution_method="document_match",
        confidence=1.0 if doc_ids else 0.0,
    )


# -- Volume resolver ------------------------------------------------------


def resolve_volume_for_document(
    doc: dict[str, Any],
    occurrence: dict[str, Any] | None = None,
) -> ResolvedVolume:
    """Resolve the volume metadata for a document.

    Resolution priority:
    1. explicit metadata['volume']
    2. metadata['volume_number']
    3. edition label
    4. document_code
    5. title parsing
    6. filename parsing
    7. section_path (from occurrence)
    8. controlled inference
    """
    doc_id = str(doc.get("id", ""))
    doc_title = str(doc.get("title", ""))
    metadata = doc.get("metadata", {}) or {}

    warnings_list: list[str] = []

    # 1. Explicit volume metadata
    vol = metadata.get("volume")
    if vol:
        try:
            vol_num = int(vol)
            return ResolvedVolume(
                volume_id=f"vol-{doc_id[:8]}-{vol_num}",
                volume_number=vol_num,
                volume_label=f"Tomo {vol_num}",
                volume_source=VolumeSource.EXPLICIT_METADATA,
                volume_confidence=VolumeConfidence.EXACT,
                document_id=doc_id,
                document_title=doc_title,
                edition_label=str(metadata.get("edition") or ""),
            )
        except (ValueError, TypeError):
            pass

    vol_num_raw = metadata.get("volume_number")
    if vol_num_raw is not None:
        try:
            vol_num = int(vol_num_raw)
            return ResolvedVolume(
                volume_id=f"vol-{doc_id[:8]}-{vol_num}",
                volume_number=vol_num,
                volume_label=f"Tomo {vol_num}",
                volume_source=VolumeSource.EXPLICIT_METADATA,
                volume_confidence=VolumeConfidence.EXACT,
                document_id=doc_id,
                document_title=doc_title,
                edition_label=str(metadata.get("edition") or ""),
            )
        except (ValueError, TypeError):
            pass

    # 2. Document code
    doc_code = doc.get("document_code") or ""
    vol_match = re.search(r"(?:vol|tomo|v)\s*[.\-]?\s*(\d+)", doc_code, re.I)
    if vol_match:
        vol_num = int(vol_match.group(1))
        return ResolvedVolume(
            volume_id=f"vol-{doc_id[:8]}-{vol_num}",
            volume_number=vol_num,
            volume_label=f"Tomo {vol_num}",
            volume_source=VolumeSource.DOCUMENT_CODE,
            volume_confidence=VolumeConfidence.MEDIUM,
            document_id=doc_id,
            document_title=doc_title,
        )

    # 3. Title parsing (before edition because explicit volume > edition label)
    title_match = re.search(r"(?:tomo|vol[.:]?\s*|parte)\s*(\d+)", doc_title, re.I)
    if title_match:
        vol_num = int(title_match.group(1))
        return ResolvedVolume(
            volume_id=f"vol-{doc_id[:8]}-{vol_num}",
            volume_number=vol_num,
            volume_label=f"Tomo {vol_num}",
            volume_source=VolumeSource.DOCUMENT_TITLE,
            volume_confidence=VolumeConfidence.MEDIUM,
            document_id=doc_id,
            document_title=doc_title,
        )

    # 4. Filename parsing
    filename = doc.get("source_filename") or ""
    fn_match = re.search(r"(?:vol|tomo|v|part)\s*[._\-]?\s*(\d+)", filename, re.I)
    if fn_match:
        vol_num = int(fn_match.group(1))
        return ResolvedVolume(
            volume_id=f"vol-{doc_id[:8]}-{vol_num}",
            volume_number=vol_num,
            volume_label=f"Tomo {vol_num} (inferido del nombre de archivo)",
            volume_source=VolumeSource.FILENAME,
            volume_confidence=VolumeConfidence.LOW,
            document_id=doc_id,
            document_title=doc_title,
            warnings=["volume_inferred_from_filename"],
        )

    # 5. Edition label (fallback when no explicit volume number)
    edition = doc.get("edition") or metadata.get("edition")
    if edition:
        return ResolvedVolume(
            volume_id=f"vol-{doc_id[:8]}-ed",
            volume_number=None,
            volume_label=edition,
            volume_source=VolumeSource.EDITION_LABEL,
            volume_confidence=VolumeConfidence.HIGH,
            document_id=doc_id,
            document_title=doc_title,
            edition_label=edition,
        )

    # 6. Unresolved — return single-volume default
    warnings_list.append("volume_not_determined")
    return ResolvedVolume(
        volume_id=f"vol-{doc_id[:8]}-single",
        volume_number=0,
        volume_label="Obra completa (un volumen)",
        volume_source=VolumeSource.UNRESOLVED,
        volume_confidence=VolumeConfidence.UNRESOLVED,
        document_id=doc_id,
        document_title=doc_title,
        warnings=warnings_list,
    )


# -- Presence classification ----------------------------------------------


def classify_presence(
    content: str,
    subject: BibliographicSubject,
    match_type: str = "",
) -> PresenceType:
    """Classify the type of presence of a concept in a chunk."""
    content_lower = content.lower()

    # Check literal exact (case-insensitive)
    for variant in subject.variants:
        if variant.lower() in content_lower:
            return PresenceType.LITERAL_EXACT

    # Check Hebrew exact
    for he_variant in subject.hebrew_variants:
        if he_variant in content:
            return PresenceType.HEBREW_EXACT

    # Check aliases (bibliographic references)
    for alias in subject.aliases:
        if alias.lower() in content_lower:
            return PresenceType.BIBLIOGRAPHIC_REFERENCE

    # Check normalized (subject stem)
    subject_stem = subject.canonical.lower()[:5]
    if subject_stem in content_lower:
        return PresenceType.LITERAL_NORMALIZED

    # Check structural heading match
    if match_type.startswith("structural_heading_"):
        return PresenceType.LITERAL_EXACT

    return PresenceType.THEMATIC_DEVELOPMENT


# -- Evidence ID generator ------------------------------------------------


def make_bibliographic_evidence_id(
    document_id: str,
    chunk_id: str,
    presence_type: str,
) -> str:
    """Generate stable evidence ID for bibliographic occurrence."""
    raw = f"biblio|{document_id}|{chunk_id}|{presence_type}"
    return f"ev-{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


# -- Planner pipeline -----------------------------------------------------


def build_query_plan(
    query: str,
    user_info: dict[str, str] | None = None,
) -> QueryPlan:
    """Build a structured query plan from the user's question."""
    intent, info = classify_intent(query)
    
    if user_info:
        info.update(user_info)

    if intent != Intent.BIBLIOGRAPHIC_LOCATOR:
        return QueryPlan(intent=intent, warnings=["not_a_bibliographic_query"])

    subject = resolve_subject(info.get("subject", query))
    
    scope_surface = info.get("work", "")
    scope = BibliographicScope(
        surface=scope_surface,
        canonical_label=scope_surface or "unknown",
        resolution_method="unresolved" if not scope_surface else "from_query",
        confidence=0.0 if not scope_surface else 0.5,
        warnings=["no_work_specified"] if not scope_surface else [],
    )

    return QueryPlan(
        intent=intent,
        subject=subject,
        scope=scope,
        return_dimensions=["volume"],
        group_by=["volume"],
        require_evidence=True,
        allow_thematic_secondary=True,
    )


def build_bibliographic_answer(
    plan: QueryPlan,
    occurrences: list[BibliographicOccurrence],
    original_query: str,
) -> BibliographicAnswer:
    """Build the final bibliographic answer from occurrences.

    Groups by volume, deduplicates, and constructs evidence.
    """
    # Group by volume label (deduplicating equivalent volumes from different docs)
    volume_groups: dict[str, list[BibliographicOccurrence]] = {}
    for occ in occurrences:
        vol_key = occ.volume.volume_label or occ.volume.volume_id or "unknown"
        if vol_key not in volume_groups:
            volume_groups[vol_key] = []
        volume_groups[vol_key].append(occ)

    results: list[BibliographicResult] = []
    evidence: list[dict[str, Any]] = []
    all_warnings: list[str] = list(plan.warnings)

    for vol_key, occs in volume_groups.items():
        vol = occs[0].volume
        presence_types = list(set(o.presence_type.value for o in occs))
        evidence_ids = [o.evidence_id for o in occs if o.evidence_id]
        pages = sorted(set(o.pdf_page for o in occs if o.pdf_page is not None))
        sections = list(dict.fromkeys(
            o.section_title for o in occs if o.section_title
        ))

        primary_eid = evidence_ids[0] if evidence_ids else None

        result = BibliographicResult(
            work=plan.scope.canonical_label if plan.scope else "unknown",
            volume=vol,
            occurrence_count=len(occs),
            presence_types=presence_types,
            primary_evidence_id=primary_eid,
            evidence_ids=evidence_ids,
            occurrences=occs,
            pages=pages,
            sections=sections,
            warnings=list(vol.warnings) if vol.warnings else [],
        )
        results.append(result)
        all_warnings.extend(result.warnings)

        # Build evidence entries for each occurrence
        for occ in occs:
            if occ.evidence_id:
                ev = {
                    "evidence_id": occ.evidence_id,
                    "document_id": occ.document_id,
                    "work": occ.document_title,
                    "title": occ.document_title,
                    "pdf_page": occ.pdf_page,
                    "printed_page": occ.printed_page,
                    "section": occ.heading_text or occ.section_title,
                    "exact_quote": occ.exact_quote,
                    "source_layer": "canonical_page",
                    "presence_type": occ.presence_type.value,
                    "location_precision": "exact",
                    "bibliographic": {
                        "volume_number": vol.volume_number,
                        "volume_label": vol.volume_label,
                        "volume_source": vol.volume_source.value,
                        "volume_confidence": vol.volume_confidence.value,
                    },
                }
                evidence.append(ev)
    
    # Deduplicate evidence by evidence_id
    seen_eids: set[str] = set()
    deduped_evidence = []
    for ev in evidence:
        eid = ev.get("evidence_id", "")
        if eid not in seen_eids:
            seen_eids.add(eid)
            deduped_evidence.append(ev)

    status = "complete" if results else "no_evidence"
    if not results:
        all_warnings.append("no_occurrences_found")

    return BibliographicAnswer(
        query_plan=plan,
        results=results,
        evidence=deduped_evidence,
        status=status,
        warnings=all_warnings,
    )


# -- Answer text generation prompt ----------------------------------------


def make_bibliographic_prompt(
    plan: QueryPlan,
    answer: BibliographicAnswer,
) -> str:
    """Generate the prompt context for the AI to create answer_markdown."""
    lines = [
        "Eres un asistente bibliográfico para un investigador de Breslov.",
        "",
        "Responde ÚNICAMENTE en base a la evidencia proporcionada.",
        "No inventes tomos, editoriales, ni datos bibliográficos.",
        "",
        f"Pregunta original: {plan.scope.surface if plan.scope else 'N/A'}",
        f"Concepto: {plan.subject.canonical if plan.subject else 'N/A'}",
        f"Obra: {plan.scope.canonical_label if plan.scope else 'N/A'}",
        "",
        "Evidencias recuperadas:",
    ]

    for ev in answer.evidence[:5]:
        lines.append(f"- Evidence ID: {ev.get('evidence_id', 'N/A')}")
        lines.append(f"  Obra: {ev.get('title', 'N/A')}")
        biblio = ev.get("bibliographic", {})
        vol_label = biblio.get("volume_label") or "Obra completa"
        vol_conf = biblio.get("volume_confidence") or "unknown"
        lines.append(f"  {'Tomo' if vol_label else 'Volumen'}: {vol_label} (confianza: {vol_conf})")
        if ev.get("pdf_page"):
            lines.append(f"  Página PDF: {ev['pdf_page']}")
        if ev.get("printed_page"):
            lines.append(f"  Página impresa: {ev['printed_page']}")
        if ev.get("section"):
            lines.append(f"  Sección: {ev['section']}")
        if ev.get("exact_quote"):
            lines.append(f"  Cita: {ev['exact_quote'][:200]}")
        lines.append(f"  Tipo de presencia: {ev.get('presence_type', 'unknown')}")
        lines.append("")

    if answer.warnings:
        lines.append("Advertencias:")
        for w in answer.warnings:
            lines.append(f"- {w}")
        lines.append("")

    result_count = len(answer.results)
    if result_count > 0:
        lines.append(f"Se encontraron {result_count} grupo(s) bibliográfico(s).")
        for r in answer.results:
            if r.volume:
                lines.append(
                    f"- {r.work}: {r.volume.volume_label or 'un volumen'} "
                    f"({r.occurrence_count} ocurrencia(s), "
                    f"{', '.join(r.presence_types)})"
                )
    else:
        lines.append("No se encontraron ocurrencias.")

    return "\n".join(lines)


# -- Public API -----------------------------------------------------------


def run_bibliographic_planner(
    query: str,
    chunks: list[dict[str, Any]],
    document_rows: list[dict[str, Any]],
    original_query: str | None = None,
) -> dict[str, Any]:
    """Main entry point: run the full bibliographic planner pipeline.

    Args:
        query: The user's question
        chunks: Retrieved chunks with content, page info, etc.
        document_rows: Document metadata rows from DB
        original_query: The original query (for answer consistency)

    Returns:
        Dict with bibliographic results or empty if not applicable
    """
    plan = build_query_plan(query)
    
    if plan.intent != Intent.BIBLIOGRAPHIC_LOCATOR:
        return {"query_plan": None, "bibliographic_results": [], "bibliographic_active": False}

    # Resolve work scope from document rows
    if plan.scope and plan.scope.surface:
        scope = resolve_work_scope(plan.scope.surface, document_rows)
        plan = QueryPlan(
            intent=plan.intent,
            subject=plan.subject,
            scope=scope,
            return_dimensions=plan.return_dimensions,
            group_by=plan.group_by,
            require_evidence=plan.require_evidence,
            allow_thematic_secondary=plan.allow_thematic_secondary,
            warnings=plan.warnings + scope.warnings,
        )

    subject = plan.subject
    if not subject:
        return {"query_plan": None, "bibliographic_results": [], "bibliographic_active": False}

    # Build occurrences from chunks
    occurrences: list[BibliographicOccurrence] = []
    seen_for_dedup: set[str] = set()

    for chunk in chunks:
        content = str(chunk.get("markdown") or chunk.get("content") or "")
        if not content:
            continue

        presence = classify_presence(content, subject, str(chunk.get("literal_match_type", "")))
        
        chunk_id = str(chunk.get("chunk_id") or chunk.get("id") or "")
        doc_id = str(chunk.get("document_id") or "")

        # Deduplicate: skip identical content within same doc
        dedup_key = f"{doc_id}:{content[:100]}"
        if dedup_key in seen_for_dedup:
            continue
        seen_for_dedup.add(dedup_key)

        # Resolve volume from the chunk's document
        doc_for_vol = {}
        for d in document_rows:
            if str(d.get("id", "")) == doc_id:
                doc_for_vol = d
                break
        volume = resolve_volume_for_document(doc_for_vol or {"id": doc_id}, chunk)

        evidence_id = make_bibliographic_evidence_id(doc_id, chunk_id, presence.value)

        occ = BibliographicOccurrence(
            occurrence_id=f"occ-{hashlib.md5(f'{doc_id}:{chunk_id}'.encode()).hexdigest()[:12]}",
            document_id=doc_id,
            document_title=str(chunk.get("work") or doc_for_vol.get("title", "")),
            volume=volume,
            presence_type=presence,
            pdf_page=chunk.get("pdf_page") or chunk.get("page_start"),
            printed_page=chunk.get("printed_page") or chunk.get("printed_page_label"),
            section_title=str(chunk.get("section_title") or chunk.get("section") or ""),
            heading_text=chunk.get("heading_original") or chunk.get("heading_text"),
            exact_quote=chunk.get("exact_quote") or content[:200],
            evidence_id=evidence_id,
            chunk_id=chunk_id,
            match_type=str(chunk.get("literal_match_type", "")),
        )
        occurrences.append(occ)

    answer = build_bibliographic_answer(plan, occurrences, original_query or query)

    return {
        "query_plan": {
            "intent": plan.intent.value,
            "subject": {
                "surface": subject.surface if subject else None,
                "canonical": subject.canonical if subject else None,
                "type": subject.subject_type if subject else None,
            },
            "scope": {
                "surface": plan.scope.surface if plan.scope else None,
                "canonical_label": plan.scope.canonical_label if plan.scope else None,
                "resolved_work_id": plan.scope.resolved_work_id if plan.scope else None,
                "document_ids": plan.scope.document_ids if plan.scope else [],
            },
            "return_dimensions": plan.return_dimensions,
            "group_by": plan.group_by,
        },
        "bibliographic_results": [
            {
                "work": r.work,
                "volume_number": r.volume.volume_number if r.volume else None,
                "volume_label": r.volume.volume_label if r.volume else None,
                "volume_source": r.volume.volume_source.value if r.volume else None,
                "volume_confidence": r.volume.volume_confidence.value if r.volume else None,
                "occurrence_count": r.occurrence_count,
                "presence_types": r.presence_types,
                "primary_evidence_id": r.primary_evidence_id,
                "evidence_ids": r.evidence_ids,
                "pages": r.pages,
                "sections": r.sections,
            }
            for r in answer.results
        ],
        "bibliographic_active": bool(answer.results),
    }
