"""Offline quality contract. Not connected to the ingestion worker.

A clean-looking string is NOT a certificate. Positive evidence of text, order
and structure is required. Diagnostics reject; they never repair content.
"""
from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum

QUALITY_POLICY_VERSION = "region-quality-v1"


class RegionState(StrEnum):
    ACCEPTED = "ACCEPTED"
    PLATFORM_EXTRACTION_ERROR = "PLATFORM_EXTRACTION_ERROR"
    SOURCE_PDF_ERROR = "SOURCE_PDF_ERROR"
    UNRESOLVED = "UNRESOLVED"


class AggregateState(StrEnum):
    FULL = "FULL"
    PARTIAL = "PARTIAL"
    UNUSABLE = "UNUSABLE"


class Remediation(StrEnum):
    SAFE_RECONNECT = "SAFE_RECONNECT"
    QUARANTINE_REQUIRED = "QUARANTINE_REQUIRED"
    SOURCE_ERROR = "SOURCE_ERROR"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True)
class RegionCandidate:
    source_sha256: str
    pdf_page: int
    region_id: str
    markdown: str
    source_method: str
    evidence_refs: tuple[str, ...]
    bbox: tuple[float, float, float, float] | None = None
    visual_good: bool | None = None
    text_verified: bool = False
    order_verified: bool = False
    structure_verified: bool = False
    diagnostics: tuple[str, ...] = ()
    safe_reconnect_available: bool = False

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[0-9a-f]{64}", self.source_sha256):
            raise ValueError("Source SHA-256 is required")
        if self.pdf_page < 1 or not self.region_id or not self.source_method:
            raise ValueError("Source location and method are required")
        if self.bbox is not None:
            x0, y0, x1, y1 = self.bbox
            if not all(math.isfinite(v) for v in self.bbox) or x0 >= x1 or y0 >= y1:
                raise ValueError("Invalid region geometry")


@dataclass(frozen=True)
class ClassifiedRegion:
    candidate: RegionCandidate
    state: RegionState
    remediation: Remediation | None
    reasons: tuple[str, ...]

    @property
    def accepted_markdown(self) -> str:
        return self.candidate.markdown if self.state == RegionState.ACCEPTED else ""

    def metadata(self) -> dict:
        c = self.candidate
        # No rejected text in operational metadata: hash + source location is
        # sufficient to trace/re-evaluate, without creating a search surface.
        return {
            "quality_policy_version": QUALITY_POLICY_VERSION,
            "source_sha256": c.source_sha256, "pdf_page": c.pdf_page,
            "region_id": c.region_id, "bbox": list(c.bbox) if c.bbox else None,
            "coordinate_system": "PDF points; top-left; unrotated" if c.bbox else None,
            "classification": self.state.value,
            "remediation": self.remediation.value if self.remediation else None,
            "reason": list(self.reasons), "source_method": c.source_method,
            "diagnostic_summary": list(c.diagnostics),
            "evidence_refs": list(c.evidence_refs),
            "candidate_sha256": hashlib.sha256(c.markdown.encode()).hexdigest(),
            "candidate_length": len(c.markdown),
        }


def classify_region(candidate: RegionCandidate) -> ClassifiedRegion:
    c = candidate
    problems = list(c.diagnostics)
    if c.source_method != "pymupdf4llm":
        problems.append("noncanonical_source_method")
    if "\ufffd" in c.markdown:
        problems.append("replacement_character")
    if any(unicodedata.category(ch) == "Cc" and ch not in "\n\r\t" for ch in c.markdown):
        problems.append("unexpected_control_character")
    if not c.markdown.strip():
        problems.append("no_textual_evidence")
    if c.visual_good is False and c.evidence_refs:
        return ClassifiedRegion(c, RegionState.SOURCE_PDF_ERROR, Remediation.SOURCE_ERROR,
                                ("visible_source_defect", *dict.fromkeys(problems)))
    verified = c.text_verified and c.order_verified and c.structure_verified
    if c.evidence_refs and c.visual_good is True and verified and not problems:
        return ClassifiedRegion(c, RegionState.ACCEPTED, None, ("verified_text_order_structure",))
    extraction_defect = bool(problems)
    if not verified:
        problems.append("text_order_structure_not_verified")
    if not c.evidence_refs:
        problems.append("missing_evidence_provenance")
    if c.visual_good is True and c.evidence_refs and extraction_defect:
        return ClassifiedRegion(
            c, RegionState.PLATFORM_EXTRACTION_ERROR,
            Remediation.SAFE_RECONNECT if c.safe_reconnect_available else Remediation.QUARANTINE_REQUIRED,
            tuple(dict.fromkeys(problems)),
        )
    return ClassifiedRegion(c, RegionState.UNRESOLVED, Remediation.UNRESOLVED,
                            tuple(dict.fromkeys([*problems, "source_or_extraction_unresolved"])))


def aggregate(states: tuple[RegionState, ...]) -> AggregateState:
    accepted = sum(state == RegionState.ACCEPTED for state in states)
    if not accepted:
        return AggregateState.UNUSABLE
    return AggregateState.FULL if accepted == len(states) else AggregateState.PARTIAL


@dataclass(frozen=True)
class QualityPage:
    """Ordered, complete region inventory supplied by a provenance adapter.

    This module cannot prove inventory completeness or region reading order.
    An adapter must certify those before using it in the real pipeline.
    """
    regions: tuple[ClassifiedRegion, ...]

    def __post_init__(self) -> None:
        locations = {(r.candidate.source_sha256, r.candidate.pdf_page) for r in self.regions}
        ids = [r.candidate.region_id for r in self.regions]
        if len(locations) > 1 or len(ids) != len(set(ids)):
            raise ValueError("A page needs unique regions from one source location")

    @property
    def quality(self) -> AggregateState:
        return aggregate(tuple(r.state for r in self.regions))

    @property
    def canonical_markdown(self) -> str:
        # No warning placeholder in evidence; partiality lives in metadata.
        return "\n\n".join(r.accepted_markdown for r in self.regions if r.accepted_markdown)

    @property
    def evidence_units(self) -> tuple[tuple[str, str], ...]:
        # Chunk each unit separately. Never bridge a quarantined gap with
        # paragraph overlap or build a quote spanning disconnected regions.
        return tuple((r.candidate.region_id, r.accepted_markdown)
                     for r in self.regions if r.state == RegionState.ACCEPTED)

    def metadata(self) -> dict:
        return {"quality_policy_version": QUALITY_POLICY_VERSION,
                "quality": self.quality.value,
                "regions": [r.metadata() for r in self.regions]}


def document_quality(pages: tuple[QualityPage, ...]) -> AggregateState:
    return aggregate(tuple(r.state for p in pages for r in p.regions))


_NOTE_START = re.compile(
    r"(?m)^[ \t]*(?:>[ \t]*)?(?:\*\*)?(?P<number>\d{1,3})(?:\*\*)?[.)]?[ \t]+"
    r"(?=[*_]*[^\W\d_])"
)


@dataclass(frozen=True)
class NoteStart:
    number: int
    start: int
    body_start: int


def markdown_note_starts(markdown: str) -> tuple[NoteStart, ...]:
    """Reconnect numbered-start recognition, preserving original offsets.

    This is not a full note segmenter: terminal bounds, inline combined notes,
    anchors and multi-column order still need source-backed verification.
    """
    return tuple(NoteStart(int(m["number"]), m.start(), m.end())
                 for m in _NOTE_START.finditer(markdown))
