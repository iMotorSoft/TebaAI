"""Conservative offline V2 proof validator; never imported by the worker.

Reuses V1 candidate discovery and forward serialization, NOT its zone verdicts.
Only explicitly anchored, locally closed LTR note flows are supported. Missing
cross-page identity remains unresolved: page-local ownership is not completion.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
import hashlib
from pathlib import Path

from modules.library.automatic_region_certification import (
    CertifiedPage, RegionCertificate, _intersects, _tokens, certify_layout_page as discover,
    native_evidence,
)
from modules.library.editorial_evidence_v2 import detect_footnote_number
from modules.library.region_markdown_provenance import _identity, _plain

VERSION = "automatic-region-certification-v2"
REQUIRED_NOTE_PROOFS = ("zone", "direction", "ownership", "local_boundary", "order", "continuation")
MISSING_REASONS = {
    "zone": "ZONE_AMBIGUOUS", "direction": "DIRECTION_UNPROVEN",
    "ownership": "PROVENANCE_OVERLAP", "local_boundary": "BOUNDARY_UNPROVEN",
    "order": "COLUMN_AMBIGUOUS", "continuation": "CROSS_PAGE_CONTINUATION_UNRESOLVED",
}


@dataclass(frozen=True)
class Proof:
    name: str
    passed: bool
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class RegionCertificateV2(RegionCertificate):
    certificate_version: str = VERSION
    proofs: tuple[Proof, ...] = ()
    local_boundary: str = "UNRESOLVED"
    continuation_status: str = "UNRESOLVED_CONTINUATION"


def certify_layout_page(parsed, page, document_sha, *, native_page=None):
    """No caller-provided proof flags, thresholds, zone or direction overrides.

    The same identity/overlap/order predicates apply to both neighbors. Extractor
    header/footer/heading labels are candidates only, never zone evidence.
    """
    page = deepcopy(page)
    for b in page.boxes:
        b.textlines = b.textlines or []
    candidate = discover(parsed, page, document_sha, native_page=native_page)
    units = {u.region_id: u for u in candidate.provenance.units}
    lines = [l for b in page.boxes for l in b.textlines]
    identities = [_identity(l) for l in lines]
    headings = [l for l in lines if _plain(l).rstrip("\ufffd").strip() in
                {"Notas y Fuentes", "Notas y Fuentes:", "Notes and Sources"}]
    anchors = [l for b in page.boxes if b.boxclass == "footnote" for l in b.textlines
               if detect_footnote_number(_plain(l)) is not None]
    notes = [u for u in candidate.provenance.units if u.note_number is not None]
    numbers = [u.note_number for u in notes]
    ordered_numbers = bool(numbers) and all(b == a + 1 for a, b in zip(numbers, numbers[1:]))
    certificates = []
    for old in candidate.certificates:
        u = units[old.region_id]
        owned = {(p.source_line_ids, p.bbox) for p in u.parts}
        selected = [l for l in lines if _identity(l) in owned]
        native, visible = native_evidence(native_page, selected) if native_page is not None else ("", False)
        source = "\n".join(p.source_text for p in u.parts)
        # A region cannot borrow an extractor label or a single regex as proof.
        # A unique preceding editorial separator AND explicit note anchors AND
        # validated typography/column flow are all required.
        is_note = u.note_number is not None
        zone = (is_note and len(headings) == 1 and bool(anchors)
                and headings[0]["bbox"][3] <= min(l["bbox"][1] for l in anchors)
                and headings[0]["bbox"][3] <= u.parts[0].bbox[1]
                and u.status == "MAPPED")
        ownership = (bool(selected) and len(selected) == len(u.parts)
                     and all(identities.count(_identity(l)) == 1 for l in selected)
                     and not any(_intersects(p.bbox, tuple(l["bbox"]))
                                 for p in u.parts for l in lines if _identity(l) not in owned)
                     and not any(_intersects(a.bbox, b.bbox)
                                 for i, a in enumerate(u.parts) for b in u.parts[i+1:]))
        columns = {p.column for p in u.parts}
        order = (is_note and ordered_numbers and None not in columns and len(columns) <= 2
                 and old.provenance_status == "CERTIFIED")
        local = (is_note and u.status == "MAPPED" and bool(u.parts)
                 and detect_footnote_number(u.parts[0].source_text) == u.note_number
                 and u.end_reason in {"NEXT_NOTE_IN_COLUMN_FLOW", "PAGE_BOUNDARY"})
        complete = bool(local and u.end_reason == "NEXT_NOTE_IN_COLUMN_FLOW")
        # Native paint direction and exact native/source tokens corroborate
        # logical order. Script alone is NOT a direction certificate.
        direction = old.direction == "LTR" and visible and _tokens(native) == _tokens(source)
        proofs = (
            Proof("zone", bool(zone), ("UNIQUE_PRECEDING_NOTES_SEPARATOR", "EXPLICIT_NOTE_ANCHORS", "MAPPED_NOTE_FLOW") if zone else ()),
            Proof("direction", bool(direction), ("LTR_STRONG_SCRIPT", "VISIBLE_HORIZONTAL_NATIVE_TOKEN_ORDER") if direction else ()),
            Proof("ownership", bool(ownership), ("UNIQUE_SOURCE_IDENTITIES", "DISJOINT_SOURCE_LINE_GEOMETRY", "FORWARD_MARKDOWN_RANGES") if ownership else ()),
            Proof("local_boundary", bool(local), (u.end_reason,) if local else ()),
            Proof("order", bool(order), ("CONSECUTIVE_MARKERS", "DISJOINT_ONE_OR_TWO_COLUMN_FLOW") if order else ()),
            Proof("continuation", complete, ("NEXT_EXPLICIT_NOTE_MARKER",) if complete else ()),
        )
        reasons = [MISSING_REASONS[p.name] for p in proofs if not p.passed]
        if not is_note:
            reasons.append("LAYOUT_UNSUPPORTED")
        if "\ufffd" in source:
            reasons.append("CORRUPT_TEXT_SIGNAL")
        certified = all(p.passed for p in proofs) and "CORRUPT_TEXT_SIGNAL" not in reasons
        quality = old.quality_status if certified else "UNRESOLVED"
        if certified:
            reasons.extend(old.reason_codes)
        else:
            reasons.append("PROVENANCE_UNRESOLVED_QUALITY_UNRESOLVED")
        fields = {k: getattr(old, k) for k in RegionCertificate.__dataclass_fields__}
        fields.update(certificate_version=VERSION,
                      provenance_status="CERTIFIED" if certified else "UNRESOLVED",
                      quality_status=quality, reason_codes=tuple(dict.fromkeys(reasons)))
        certificates.append(RegionCertificateV2(**fields, proofs=proofs,
            local_boundary="KNOWN" if local else "UNRESOLVED",
            continuation_status="COMPLETE" if complete and certified else "UNRESOLVED_CONTINUATION"))
    return CertifiedPage(candidate.provenance, tuple(certificates))


def extract_pdf_region_certificates(path, *, pages=None):
    """Read-only PDF entrypoint. V1 remains unchanged; V2 outputs are versioned."""
    import pymupdf
    from pymupdf4llm.helpers.document_layout import parse_document

    sha = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    with pymupdf.open(path) as document:
        selected = list(pages) if pages is not None else list(range(1, len(document) + 1))
        if len(set(selected)) != len(selected) or any(n < 1 or n > len(document) for n in selected):
            raise ValueError("Unique physical page numbers in document range required")
        parsed = parse_document(document, pages=[n-1 for n in sorted(selected)], use_ocr=False)
        return tuple(certify_layout_page(parsed, page, sha, native_page=document[page.page_number-1])
                     for page in sorted(parsed.pages, key=lambda p: p.page_number))
