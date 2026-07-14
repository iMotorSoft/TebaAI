"""Deterministic gate between AI zone proposals and any future promotion."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal

Decision = Literal['promote_candidate','keep_as_candidate','reject_candidate','needs_human_review']
@dataclass(frozen=True)
class ZoneCandidate:
    page_kind: str
    kind: str
    marker: str | None
    confidence: float
    quote: str | None = None
@dataclass(frozen=True)
class ZoneCandidatePageContext:
    pdf_page: int
    literal_text: str
    document_part: str = 'unknown'
    structural_status: str = 'unclassified'
    is_blank: bool = False
@dataclass(frozen=True)
class ZoneCandidateValidationDecision:
    decision: Decision
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
def validate_zone_candidate(candidate: ZoneCandidate, page_context: ZoneCandidatePageContext, policy=None) -> ZoneCandidateValidationDecision:
    """Reject structural contradictions; never writes corpus state."""
    kind=candidate.page_kind.casefold()
    if page_context.is_blank and kind not in {'blank','unknown'}:
        return ZoneCandidateValidationDecision('reject_candidate',['blank_page_contradiction'])
    if page_context.document_part in {'appendix','diagram'} and kind in {'lesson','religious_text'}:
        return ZoneCandidateValidationDecision('reject_candidate',['document_part_contradiction'])
    if candidate.quote and candidate.quote not in page_context.literal_text:
        return ZoneCandidateValidationDecision('reject_candidate',['unverifiable_quote'])
    if candidate.confidence < .50:
        return ZoneCandidateValidationDecision('keep_as_candidate',['low_ai_confidence'])
    if candidate.kind in {'probable_continuation','marginal_commentary'}:
        return ZoneCandidateValidationDecision('needs_human_review',['ambiguous_zone_requires_review'])
    if candidate.quote and candidate.confidence >= .85:
        return ZoneCandidateValidationDecision('promote_candidate',['quote_verified','no_structural_contradiction'])
    return ZoneCandidateValidationDecision('keep_as_candidate',['insufficient_deterministic_evidence'])
