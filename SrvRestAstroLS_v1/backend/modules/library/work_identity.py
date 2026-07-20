"""Canonical work identity resolver and section parser.

Separates canonical_work_title, part, volume, edition, physical_filename,
lesson_number, and subsection_number. Never infers volume from section
numbers like #2:6.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

ROMAN_NUMERAL_RE = re.compile(r"(?i)^\s*(?:I{1,3}|IV|V|IX|X{1,2}|XV|XX)\s*$")
SECTION_LABEL_RE = re.compile(
    r"(?i)"
    r"(?:LIKUTEY\s+MOHAR[ÁA]N)"
    r"(?:\s+(I{1,3}|XV))?"
    r"\s*#\s*(\d+)"
    r"(?:\s*:\s*(\d+))?"
)
LM_XV_SECTION_RE = re.compile(
    r"(?i)"
    r"LIKUTEY\s+MOHAR[ÁA]N\s+II\s+#\s*(\d+)(?:\s*:\s*(\d+))?"
)
SIMPLE_SECTION_RE = re.compile(r"(?i)#\s*(\d+)(?:\s*:\s*(\d+))?")


@dataclass(frozen=True)
class WorkIdentity:
    canonical_work_id: str = ""
    canonical_work_title: str = ""
    part: str | None = None
    volume: str | None = None
    edition_label: str | None = None
    physical_filename: str | None = None
    document_id: str | None = None
    language: str = "es"
    display_title: str = ""


@dataclass(frozen=True)
class SectionLocation:
    lesson_number: int | None = None
    subsection_number: int | None = None
    section_label: str | None = None
    pdf_page: int | None = None
    printed_page: int | None = None
    part_in_label: str | None = None
    confidence: Literal["high", "medium", "low"] = "high"
    warnings: list[str] = field(default_factory=list)


WORK_METADATA: dict[str, dict] = {
    "lm_xv": {
        "canonical_work_id": "likutey_moharan",
        "canonical_work_title": "Likutey Moharán",
        "part": None,
        "volume": "XV",
        "edition_label": "KDP",
        "language": "es",
        "display_title": "Likutey Moharán XV KDP",
    },
}

WORK_BY_FILENAME_PREFIX: list[tuple[re.Pattern, str, dict]] = [
    (re.compile(r"LIKUTEY\s+MOHAR[ÁA]N\s+XV\b"), "lm_xv", {
        "volume": "XV", "edition_label": "KDP",
    }),
    (re.compile(r"LIKUTEY\s+MOHAR[ÁA]N\s+I\s+int\b"), "lmi", {
        "part": "I", "edition_label": "int (imprenta)",
    }),
    (re.compile(r"LIKUTEY\s+MOHAR[ÁA]N\s+II\b(?!\s*#)"), "lmii", {
        "part": "II",
    }),
    (re.compile(r"LIKUTEY\s+MOHAR[ÁA]N\s+I\b(?!\s*#)"), "lmi", {
        "part": "I",
    }),
    (re.compile(r"LIKUTEY\s+HALAJOT\b"), "lh", {}),
    (re.compile(r"KITZUR\b"), "kitzur", {}),
    (re.compile(r"POTENCIA\b"), "potencia_plegaria", {}),
]

WORK_CODES = frozenset({"kitzur", "lmi", "lmii", "lh", "lm_xv", "potencia_plegaria"})

WORK_TITLES_CANONICAL: dict[str, str] = {
    "kitzur": "Kitzur",
    "lmi": "Likutey Moharán I",
    "lmii": "Likutey Moharán II",
    "lh": "Likutey Halajot",
    "lm_xv": "Likutey Moharán XV KDP",
    "potencia_plegaria": "La Potencia de la Plegaria",
}

WORK_TITLES_VERBOSE: dict[str, str] = {
    "kitzur": "Kitzur Likutey Moharán",
    "lmi": "Likutey Moharán I — edición española BRI",
    "lmii": "Likutey Moharán II",
    "lh": "Likutey Halajot",
    "lm_xv": "Likutey Moharán XV KDP",
    "potencia_plegaria": "La Potencia de la Plegaria",
}


def resolve_from_filename(physical_filename: str | None) -> tuple[str | None, dict]:
    if not physical_filename:
        return None, {}
    for pattern, work_code, metadata in WORK_BY_FILENAME_PREFIX:
        if pattern.search(physical_filename):
            return work_code, metadata
    return None, {}


def resolve_work_identity(
    work_code: str | None = None,
    physical_filename: str | None = None,
    document_id: str | None = None,
    section_label: str | None = None,
) -> WorkIdentity:
    if work_code and work_code in WORK_METADATA:
        meta = WORK_METADATA[work_code]
        return WorkIdentity(
            canonical_work_id=meta["canonical_work_id"],
            canonical_work_title=meta["canonical_work_title"],
            part=meta.get("part"),
            volume=meta.get("volume"),
            edition_label=meta.get("edition_label"),
            physical_filename=physical_filename,
            document_id=document_id,
            language=meta.get("language", "es"),
            display_title=meta.get("display_title", WORK_TITLES_CANONICAL.get(work_code, work_code or "")),
        )
    if physical_filename:
        resolved_code, meta = resolve_from_filename(physical_filename)
        if resolved_code:
            part = meta.get("part") if meta.get("part") else None
            volume = meta.get("volume") if meta.get("volume") else None
            edition = meta.get("edition_label") if meta.get("edition_label") else None
            return WorkIdentity(
                canonical_work_id="likutey_moharan",
                canonical_work_title="Likutey Moharán",
                part=part,
                volume=volume,
                edition_label=edition or _infer_edition(physical_filename),
                physical_filename=physical_filename,
                document_id=document_id,
                display_title=WORK_TITLES_CANONICAL.get(resolved_code, resolved_code),
            )
    if work_code and work_code in WORK_TITLES_CANONICAL:
        return WorkIdentity(
            canonical_work_id="likutey_moharan" if work_code in {"lmi", "lmii", "lm_xv"} else work_code,
            canonical_work_title=WORK_TITLES_CANONICAL.get(work_code, work_code),
            display_title=WORK_TITLES_CANONICAL.get(work_code, work_code),
            physical_filename=physical_filename,
            document_id=document_id,
        )
    return WorkIdentity(
        canonical_work_title=WORK_TITLES_CANONICAL.get(work_code or "", work_code or "") or "Unknown Work",
        display_title=work_code or "unknown",
        physical_filename=physical_filename,
        document_id=document_id,
    )


def _infer_edition(filename: str) -> str | None:
    parts = filename.replace("(", "").replace(")", "").split()
    for token in parts:
        if token in {"int", "imprenta", "kdp", "hebrewbooks"}:
            return token
    return None


def parse_section_label(section_label: str | None) -> SectionLocation:
    if not section_label:
        return SectionLocation(confidence="low", warnings=["no_section_label"])
    match = SECTION_LABEL_RE.search(section_label)
    if match:
        part_raw = match.group(1)
        lesson = int(match.group(2))
        subsection = int(match.group(3)) if match.group(3) else None
        confidence: Literal["high", "medium", "low"] = "high"
        warnings: list[str] = []
        if part_raw and ROMAN_NUMERAL_RE.match(part_raw):
            pass
        elif part_raw:
            warnings.append(f"unexpected_part_format:{part_raw}")
            confidence = "medium"
        return SectionLocation(
            lesson_number=lesson,
            subsection_number=subsection,
            section_label=section_label,
            part_in_label=part_raw,
            confidence=confidence,
            warnings=warnings,
        )
    simple = SIMPLE_SECTION_RE.search(section_label)
    if simple:
        lesson = int(simple.group(1))
        subsection = int(simple.group(2)) if simple.group(2) else None
        return SectionLocation(
            lesson_number=lesson,
            subsection_number=subsection,
            section_label=section_label,
            confidence="medium",
            warnings=["part_not_declared_in_section_label"],
        )
    return SectionLocation(
        section_label=section_label,
        confidence="low",
        warnings=["section_label_not_parsed"],
    )
