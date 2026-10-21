"""Publication boundary for existing forward-owned region certificates.

This consumer does not decide quality, repair text, or certify neighboring
regions. It filters BEFORE canonical concatenation and exposes separate chunk
inputs so overlap cannot create a quote across a quarantined gap. The durable
page-first worker consumes this boundary before canonical persistence/chunking.
Source-reference metadata alone is not a durable-storage guarantee; the gateway
preserves the original separately before deleting its temporary upload.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib

from modules.library.automatic_region_certification import CertifiedPage
from modules.library.region_quality import AggregateState

VERSION = "region-publication-v1"
PARTIAL_SOURCE_NOTICE = (
    "Esta página contiene regiones cuya extracción textual no es suficientemente "
    "confiable para búsqueda o citas. Pueden consultarse visualmente en la fuente "
    "original. El resto del contenido aceptado sí puede utilizarse."
)


@dataclass(frozen=True)
class PublicationRegion:
    region_id: str
    quality_status: str
    provenance_status: str
    reason_codes: tuple[str, ...]
    bbox: tuple
    markdown: str
    publishable: bool
    candidate_sha256: str


@dataclass(frozen=True)
class PublishedPage:
    source_sha256: str
    pdf_page: int
    source_reference: str
    regions: tuple[PublicationRegion, ...]

    @property
    def status(self) -> AggregateState:
        count = sum(region.publishable for region in self.regions)
        if not count:
            return AggregateState.UNUSABLE
        return AggregateState.FULL if count == len(self.regions) else AggregateState.PARTIAL

    @property
    def evidence_units(self) -> tuple[tuple[str, str], ...]:
        return tuple((r.region_id, r.markdown) for r in self.regions if r.publishable)

    @property
    def canonical_markdown(self) -> str:
        return "\n\n".join(text for _, text in self.evidence_units)

    def metadata(self) -> dict:
        """No rejected text in searchable JSON, summaries or citation metadata."""
        return {
            "publication_version": VERSION,
            "source_sha256": self.source_sha256,
            "pdf_page": self.pdf_page,
            "source_reference": self.source_reference,
            "page_status": self.status.value,
            "contains_quarantined_regions": any(not r.publishable for r in self.regions),
            "notice": PARTIAL_SOURCE_NOTICE if any(not r.publishable for r in self.regions) else None,
            "regions": [
                {
                    "region_id": r.region_id,
                    "bbox": list(r.bbox),
                    "quality_status": r.quality_status,
                    "provenance_status": r.provenance_status,
                    "publication_status": "ACCEPTED" if r.publishable else "QUARANTINED",
                    "reason_codes": list(r.reason_codes),
                    "candidate_sha256": r.candidate_sha256,
                    "textually_citable": r.publishable,
                    "visual_reference": {
                        "source_reference": self.source_reference,
                        "source_sha256": self.source_sha256,
                        "pdf_page": self.pdf_page,
                        "region_id": r.region_id,
                        "bbox": list(r.bbox),
                    },
                }
                for r in self.regions
            ],
        }


def publish_certified_page(page: CertifiedPage, *, source_reference: str) -> PublishedPage:
    """Consume internal certificates; never infer ACCEPTED from a clean string.

    CERTIFIED is the existing acceptable provenance contract. Missing or
    mismatched certificates quarantine only their owned unit. Offsets refer to
    this exact immutable forward Markdown, not the worker's other serializer.
    """
    if not source_reference.strip():
        raise ValueError("A source reference is required")
    provenance = page.provenance
    ids = [unit.region_id for unit in provenance.units]
    if len(ids) != len(set(ids)):
        raise ValueError("Ambiguous duplicate region ownership")
    if any(c.region_id not in ids for c in page.certificates):
        raise ValueError("Certificate has no owned source region")
    regions = []
    for unit in provenance.units:
        matches = [c for c in page.certificates if c.region_id == unit.region_id]
        certificate = matches[0] if len(matches) == 1 else None
        reasons = list(certificate.reason_codes) if certificate else ["MISSING_OR_DUPLICATE_CERTIFICATE"]
        start, end = unit.markdown_start, unit.markdown_end
        valid_range = 0 <= start < end <= len(provenance.markdown)
        fragment = provenance.markdown[start:end] if valid_range else ""
        bound = bool(
            certificate
            and certificate.document_sha == provenance.source_sha256
            and certificate.pdf_page == provenance.pdf_page == unit.pdf_page
            and tuple(certificate.bbox) == tuple(unit.source_bbox)
            and tuple(certificate.markdown_ranges) == ((start, end),)
            and unit.status == "MAPPED"
            and unit.transformation_status == "ALLOWLIST_ONLY"
            and valid_range
        )
        if not bound:
            reasons.append("OWNERSHIP_CERTIFICATE_MISMATCH")
        overlaps = any(
            other.region_id != unit.region_id
            and start < other.markdown_end and other.markdown_start < end
            for other in provenance.units
        )
        if overlaps:
            reasons.append("OVERLAPPING_MARKDOWN_OWNERSHIP")
        quality = certificate.quality_status if certificate else "UNRESOLVED"
        origin = certificate.provenance_status if certificate else "UNRESOLVED"
        publishable = bool(bound and not overlaps and quality == "ACCEPTED"
                           and origin == "CERTIFIED" and fragment.strip())
        if not publishable and not reasons:
            reasons.append("QUALITY_OR_PROVENANCE_NOT_ACCEPTED")
        regions.append(PublicationRegion(
            unit.region_id, quality, origin, tuple(dict.fromkeys(reasons)),
            unit.source_bbox, fragment if publishable else "", publishable,
            hashlib.sha256(fragment.encode()).hexdigest(),
        ))
    return PublishedPage(provenance.source_sha256, provenance.pdf_page,
                         source_reference, tuple(regions))
