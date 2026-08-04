"""Canonical bibliographic identity and scope contracts.

The contract separates the containing work from edition, source relations and
technical derivation. PostgreSQL document metadata is authoritative; filename
and document-code fallbacks are always marked as derived and never establish a
volume or source relation.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Literal

from modules.library.work_identity import resolve_from_filename

Confidence = Literal["explicit", "derived", "unresolved", "conflicting"]
SourceRelation = Literal[
    "develops", "comments_on", "quotes", "references", "paraphrases",
    "is_based_on", "same_topic",
]

FAMILY_CATALOG: dict[str, dict[str, Any]] = {
    "likutey_halajot": {
        "label": "Likutey Halajot",
        "work_code": "lh",
        "aliases": (
            "likutey halajot", "likutei halajot", "likutei halachot",
            "likutey halakhot", "likutey halachos", "lh", "ליקוטי הלכות",
        ),
    },
    "likutey_moharan_ii": {
        "label": "Likutey Moharán II",
        "work_code": "lmii",
        "aliases": (
            "likutey moharan ii", "likutei moharan ii", "lm ii",
            "likutey moharan tinyana", "ליקוטי מוהרן תנינא",
            'ליקוטי מוהר"ן תנינא',
        ),
    },
    "likutey_moharan_i": {
        "label": "Likutey Moharán I",
        "work_code": "lmi",
        "aliases": ("likutey moharan i", "likutei moharan i", "lm i"),
    },
    "kitzur_likutey_moharan": {
        "label": "Kitzur Likutey Moharán",
        "work_code": "kitzur",
        "aliases": ("kitzur likutey moharan", "kitzur"),
    },
    "la_potencia_de_la_plegaria": {
        "label": "La Potencia de la Plegaria",
        "work_code": "potencia_plegaria",
        "aliases": ("la potencia de la plegaria", "potencia de la plegaria"),
    },
}
WORK_CODE_TO_FAMILY = {
    value["work_code"]: code for code, value in FAMILY_CATALOG.items()
}


@dataclass(frozen=True)
class CanonicalValue:
    value: str | int | None
    confidence: Confidence
    source: str
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.value is None and self.confidence not in {"unresolved", "conflicting"}:
            raise ValueError("null metadata must be unresolved or conflicting")
        if self.value is not None and self.confidence == "unresolved":
            raise ValueError("non-null metadata cannot have unresolved confidence")

    def public(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "confidence": self.confidence,
            "source": self.source,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class SourceIdentity:
    work_code: str
    work_label: str
    lesson_number: int | None
    relation: SourceRelation
    confidence: Confidence
    source: str

    def public(self) -> dict[str, Any]:
        return {
            "source_work_code": self.work_code,
            "source_work": self.work_label,
            "source_lesson": self.lesson_number,
            "source_relation": self.relation,
            "source_confidence": self.confidence,
            "source_provenance": self.source,
        }


@dataclass(frozen=True)
class CanonicalDocumentIdentity:
    family_code: str
    family_label: str
    canonical_work_code: str
    canonical_work_label: str
    edition: CanonicalValue
    volume: CanonicalValue
    technical_version: CanonicalValue
    document_id: str | None
    document_title: str
    source_filename: str | None
    source_sha256: str | None
    document_status: str | None
    source_identities: tuple[SourceIdentity, ...] = ()
    metadata_warnings: tuple[str, ...] = ()

    @property
    def work_code(self) -> str:
        return str(FAMILY_CATALOG.get(self.family_code, {}).get("work_code") or "")

    def public(self) -> dict[str, Any]:
        primary_source = self.source_identities[0] if self.source_identities else None
        return {
            "work_code": self.work_code,
            "work_family_code": self.family_code,
            "work_family": self.family_label,
            "canonical_work_code": self.canonical_work_code,
            "canonical_work": self.canonical_work_label,
            "edition": self.edition.value,
            "edition_confidence": self.edition.confidence,
            "edition_source": self.edition.source,
            "volume_number": self.volume.value,
            "volume_confidence": self.volume.confidence,
            "volume_source": self.volume.source,
            "technical_version": self.technical_version.value,
            "technical_version_confidence": self.technical_version.confidence,
            "technical_version_source": self.technical_version.source,
            "source_work": primary_source.work_label if primary_source else None,
            "source_work_code": primary_source.work_code if primary_source else None,
            "source_lesson": primary_source.lesson_number if primary_source else None,
            "source_relation": primary_source.relation if primary_source else None,
            "source_confidence": primary_source.confidence if primary_source else "unresolved",
            "document_instance": {
                "document_id": self.document_id,
                "document_title": self.document_title,
                "source_filename": self.source_filename,
                "source_sha256": self.source_sha256,
                "status": self.document_status,
            },
            "document_title": self.document_title,
            "metadata_warnings": list(self.metadata_warnings),
        }


@dataclass(frozen=True)
class CanonicalScope:
    family_codes: tuple[str, ...] = ()
    edition: str | None = None
    document_sha256: str | None = None
    source_work_code: str | None = None
    source_lesson: int | None = None
    cross_family: bool = False
    ambiguous: bool = False
    warnings: tuple[str, ...] = ()
    resolution_method: str = "none"

    @property
    def active(self) -> bool:
        return bool(
            self.family_codes or self.edition or self.document_sha256
            or self.source_work_code or self.source_lesson or self.ambiguous
        )

    def public(self) -> dict[str, Any]:
        return {
            "scope_family": list(self.family_codes),
            "scope_edition": self.edition,
            "scope_document_sha256": self.document_sha256,
            "scope_source_work": self.source_work_code,
            "scope_source_lesson": self.source_lesson,
            "cross_family": self.cross_family,
            "scope_ambiguous": self.ambiguous,
            "warnings": list(self.warnings),
            "resolution_method": self.resolution_method,
        }


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.replace("׳", "'").replace("״", '"')
    return " ".join(normalized.casefold().split())


def _contains_alias(text: str, alias: str) -> bool:
    folded_text = _fold(text)
    folded_alias = _fold(alias)
    if re.search(r"[א-ת]", folded_alias):
        return folded_alias in folded_text
    return re.search(rf"(?<![a-z0-9]){re.escape(folded_alias)}(?![a-z0-9])", folded_text) is not None


def resolve_family_mentions(query: str) -> tuple[str, ...]:
    matches: list[tuple[int, str]] = []
    folded = _fold(query)
    for family_code, entry in FAMILY_CATALOG.items():
        positions = [folded.find(_fold(alias)) for alias in entry["aliases"] if _contains_alias(query, alias)]
        if positions:
            matches.append((min(position for position in positions if position >= 0), family_code))
    return tuple(code for _position, code in sorted(matches))


def _technical_version(row: dict[str, Any], contract: dict[str, Any]) -> CanonicalValue:
    configured = contract.get("technical_identity") or {}
    if configured.get("version"):
        return CanonicalValue(
            str(configured["version"]),
            configured.get("confidence", "explicit"),
            configured.get("source", "bibliographic_metadata.canonical_identity_v1"),
        )
    document_metadata = row.get("document_metadata") or row.get("metadata") or {}
    pipeline = str(document_metadata.get("pipeline") or "")
    if pipeline:
        match = re.search(r"(?:^|_)(v\d+)(?:$|_)", pipeline, re.I)
        return CanonicalValue(
            match.group(1).casefold() if match else pipeline,
            "derived",
            "library_documents.metadata.pipeline",
        )
    code = str(row.get("document_code") or "")
    match = re.search(r"(?:^|_)(v\d+)$", code, re.I)
    if match:
        return CanonicalValue(match.group(1).casefold(), "derived", "library_documents.document_code")
    return CanonicalValue(None, "unresolved", "unresolved")


def identity_from_document(row: dict[str, Any]) -> CanonicalDocumentIdentity:
    bibliographic = row.get("bibliographic_metadata") or row.get("document_bibliographic_metadata") or {}
    contract = bibliographic.get("canonical_identity_v1") or {}
    work = contract.get("work_identity") or {}
    family_code = str(work.get("family_code") or "")
    warnings: list[str] = []
    if not family_code:
        resolved, _metadata = resolve_from_filename(row.get("source_filename") or row.get("physical_file_name"))
        family_code = WORK_CODE_TO_FAMILY.get(str(resolved or ""), "")
        warnings.append("work_family_derived_from_filename")
    entry = FAMILY_CATALOG.get(family_code, {})
    family_label = str(work.get("family_label") or entry.get("label") or row.get("title") or row.get("work") or "")
    canonical_work_code = str(work.get("canonical_work_code") or family_code)
    canonical_work_label = str(work.get("canonical_work_label") or family_label)

    edition_data = contract.get("edition_identity") or {}
    edition_value = edition_data.get("edition_label")
    edition_confidence: Confidence = edition_data.get("edition_confidence", "unresolved" if edition_value is None else "derived")
    edition_source = str(edition_data.get("edition_source") or "unresolved")
    if edition_value is None:
        legacy_edition = row.get("edition") or bibliographic.get("edition")
        if legacy_edition:
            edition_value = str(legacy_edition)
            edition_confidence = "derived"
            edition_source = "legacy_bibliographic_metadata"
            warnings.append("edition_legacy_provenance_not_explicit")
    edition = CanonicalValue(edition_value, edition_confidence, edition_source)

    volume_value = edition_data.get("volume_number")
    volume_confidence: Confidence = edition_data.get("volume_confidence", "unresolved")
    volume_source = str(edition_data.get("volume_source") or "unresolved")
    if volume_source.startswith("technical") or volume_source.startswith("source_lesson"):
        raise ValueError("volume cannot be derived from technical version or source lesson")
    volume = CanonicalValue(volume_value, volume_confidence, volume_source)

    source_identities = tuple(
        SourceIdentity(
            work_code=str(item["source_work_code"]),
            work_label=str(item["source_work_label"]),
            lesson_number=(int(item["source_lesson"]) if item.get("source_lesson") is not None else None),
            relation=item["source_relation"],
            confidence=item.get("confidence", "explicit"),
            source=str(item.get("source") or "bibliographic_metadata.canonical_identity_v1"),
        )
        for item in (contract.get("source_identities") or [])
    )
    return CanonicalDocumentIdentity(
        family_code=family_code,
        family_label=family_label,
        canonical_work_code=canonical_work_code,
        canonical_work_label=canonical_work_label,
        edition=edition,
        volume=volume,
        technical_version=_technical_version(row, contract),
        document_id=str(row.get("document_id") or row.get("id") or "") or None,
        document_title=str(row.get("title") or row.get("work") or ""),
        source_filename=row.get("source_filename") or row.get("physical_file_name"),
        source_sha256=row.get("source_sha256"),
        document_status=row.get("status") or row.get("document_status"),
        source_identities=source_identities,
        metadata_warnings=tuple(warnings),
    )


def resolve_canonical_scope(
    query: str,
    identities: list[CanonicalDocumentIdentity],
    *,
    requested_work_codes: list[str] | None = None,
    scope_family: str | None = None,
    scope_edition: str | None = None,
    scope_document_sha256: str | None = None,
    scope_source_work: str | None = None,
    scope_source_lesson: int | None = None,
) -> CanonicalScope:
    query_families = list(resolve_family_mentions(query))
    explicit_family = resolve_family_mentions(scope_family or "") if scope_family else ()
    family_codes = list(explicit_family or query_families)
    if not family_codes and requested_work_codes:
        family_codes = [WORK_CODE_TO_FAMILY[code] for code in requested_work_codes if code in WORK_CODE_TO_FAMILY]

    folded = _fold(query)
    ambiguous = folded.strip(" ?¿") in {"likutey", "lm"}
    warnings: list[str] = ["scope_ambiguous"] if ambiguous else []
    cross = len(set(family_codes)) > 1 and bool(re.search(r"\b(compara|comparar|comparativa|con|entre|compare|versus|vs)\b", folded))

    edition = scope_edition
    if not edition:
        edition_labels = {
            str(identity.edition.value): identity.family_code
            for identity in identities if identity.edition.value
        }
        matches = [label for label in edition_labels if _contains_alias(query, label)]
        if len(matches) == 1:
            edition = matches[0]
            family_codes = [edition_labels[edition]]
        elif len(matches) > 1:
            ambiguous = True
            warnings.append("edition_scope_ambiguous")

    source_work_code = None
    if scope_source_work:
        source_mentions = resolve_family_mentions(scope_source_work)
        source_work_code = source_mentions[0] if source_mentions else scope_source_work
    elif "likutey_halajot" in family_codes and "likutey_moharan_ii" in family_codes and not cross:
        source_work_code = "likutey_moharan_ii"
        family_codes = ["likutey_halajot"]
    lesson = scope_source_lesson
    if lesson is None and (source_work_code or "likutey_moharan_ii" in family_codes):
        match = re.search(r"(?:#|lecci[oó]n\s*)?(\d{1,3})(?!\d)", query, re.I)
        lesson = int(match.group(1)) if match else None

    if cross:
        # Cross-family queries permit the original work plus documents that
        # explicitly declare the requested source relation.
        source_work_code = "likutey_moharan_ii" if "likutey_moharan_ii" in family_codes else source_work_code
    return CanonicalScope(
        family_codes=tuple(dict.fromkeys(family_codes)),
        edition=edition,
        document_sha256=scope_document_sha256,
        source_work_code=source_work_code,
        source_lesson=lesson,
        cross_family=cross,
        ambiguous=ambiguous,
        warnings=tuple(dict.fromkeys(warnings)),
        resolution_method="explicit_or_deterministic_alias" if any((family_codes, edition, scope_document_sha256, source_work_code, lesson, ambiguous)) else "none",
    )


def content_query_without_scope_surfaces(
    query: str,
    scope: CanonicalScope,
    identities: list[CanonicalDocumentIdentity],
) -> str:
    """Remove only recognized scope labels from lexical/structural variants.

    The intact original query remains the semantic embedding input and audit
    surface. This helper prevents an explicit edition suffix from becoming part
    of a heading or literal phrase.
    """
    result = query
    surfaces: list[str] = []
    if scope.edition:
        surfaces.append(scope.edition)
    for family_code in scope.family_codes:
        entry = FAMILY_CATALOG.get(family_code) or {}
        surfaces.extend(str(alias) for alias in entry.get("aliases", ()))
    for surface in sorted(set(surfaces), key=len, reverse=True):
        if not surface:
            continue
        result = re.sub(
            rf"(?i)(?<![\w]){re.escape(surface)}(?![\w])",
            " ",
            result,
        )
    result = re.sub(r"(?i)\b(?:solo\s+)?(?:en|de|del)\s*(?=[?¿.!,:;]|$)", " ", result)
    result = re.sub(
        r"(?i)^\s*[¿?]*\s*(?:donde|dónde|where)\s+(?:aparece|esta|está|is)\s+",
        "",
        result,
    )
    result = " ".join(result.split()).strip(" ¿?.,:;")
    content_tokens = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿא-ת]{3,}", result)
    return result if content_tokens else query


def document_matches_scope(identity: CanonicalDocumentIdentity, scope: CanonicalScope) -> bool:
    if scope.ambiguous:
        return False
    if scope.document_sha256 and identity.source_sha256 != scope.document_sha256:
        return False
    if scope.edition and _fold(str(identity.edition.value or "")) != _fold(scope.edition):
        return False
    family_match = not scope.family_codes or identity.family_code in scope.family_codes
    source_match = False
    if scope.source_work_code:
        source_match = any(
            source.work_code == scope.source_work_code
            and (scope.source_lesson is None or source.lesson_number == scope.source_lesson)
            for source in identity.source_identities
        )
        if scope.cross_family or not scope.family_codes:
            source_match = source_match or identity.family_code == scope.source_work_code
        elif scope.family_codes and not family_match:
            return False
        if not source_match:
            return False
    elif scope.source_lesson is not None:
        # A lesson requested inside the original work scopes that work; it is
        # not a document-level source relation. Commentary families require an
        # explicit source identity instead.
        original_work_match = "likutey_moharan_ii" in scope.family_codes and identity.family_code == "likutey_moharan_ii"
        source_match = original_work_match or any(
            source.lesson_number == scope.source_lesson
            for source in identity.source_identities
        )
        if not source_match:
            return False
    return family_match or (scope.cross_family and source_match)


def filter_documents_for_scope(
    rows: list[dict[str, Any]], scope: CanonicalScope
) -> tuple[list[dict[str, Any]], dict[str, CanonicalDocumentIdentity]]:
    identities = {
        str(row.get("document_id") or row.get("id")): identity_from_document(row)
        for row in rows
    }
    if not scope.active:
        return rows, identities
    filtered = [
        row for row in rows
        if document_matches_scope(
            identities[str(row.get("document_id") or row.get("id"))], scope
        )
    ]
    return filtered, identities
