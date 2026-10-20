"""Offline V3: bounded ruled-panel body proof and adjacent-page note lineage.

V2 note verdicts are retained. No worker import, external service, OCR, semantic
judge or caller-supplied positive proof. Unsupported families remain unresolved.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
import unicodedata

from modules.library.automatic_region_certification import (
    CertifiedPage, _decoration_only, _intersects, _tokens, direction, native_evidence,
)
from modules.library.automatic_region_certification_v2 import (
    Proof, RegionCertificateV2, certify_layout_page as certify_v2,
)
from modules.library.editorial_evidence_v2 import detect_footnote_number
from modules.library.region_markdown_provenance import (
    ProvenancePage, UnresolvedLayout, _bbox, _identity, _plain, map_layout_page,
)

VERSION = "automatic-region-certification-v3"
SEPARATORS = {"Notas y Fuentes", "Notas y Fuentes:", "Notes and Sources"}


@dataclass(frozen=True)
class RegionCertificateV3(RegionCertificateV2):
    certificate_version: str = VERSION
    body_proof: tuple[Proof, ...] = ()
    editorial_unit_id: str | None = None
    continuation_state: str = "CONTINUATION_UNRESOLVED"
    continuation_proof: tuple[Proof, ...] = ()
    linked_region_ids: tuple[str, ...] = ()


def _lines(page):
    return [l for b in page.boxes for l in (b.textlines or [])]


def _selected(unit, page):
    keys = {(p.source_line_ids, p.bbox) for p in unit.parts}
    return sorted((l for l in _lines(page) if _identity(l) in keys),
                  key=lambda l: (l["bbox"][1], l["bbox"][0], _identity(l)))


def _ownership(unit, page):
    selected = _selected(unit, page)
    keys = [_identity(l) for l in _lines(page)]
    owned = {_identity(l) for l in selected}
    return (bool(selected) and len(selected) == len(unit.parts)
            and all(keys.count(k) == 1 for k in owned)
            and not any(_intersects(p.bbox, tuple(l["bbox"]))
                        for p in unit.parts for l in _lines(page) if _identity(l) not in owned)
            and not any(_intersects(a.bbox, b.bbox)
                        for i, a in enumerate(unit.parts) for b in unit.parts[i+1:]))


def _rules(native):
    if native is None:
        return []
    rules = []
    for drawing in native.get_drawings():
        # This supported family has exactly two broad, opaque, stroked rules.
        if drawing.get("type") != "s" or drawing.get("stroke_opacity") != 1:
            continue
        for item in drawing["items"]:
            if item[0] == "l":
                a, b = item[1:3]
                if a.y == b.y and abs(b.x-a.x) > native.rect.width / 2:
                    rules.append((min(a.x,b.x), a.y, max(a.x,b.x), b.y))
    return sorted(set(rules), key=lambda r: r[1])


def _family(page, native):
    """Recognize only a main panel bounded by two physical editorial rules.

    The lower rule must intersect the unique historical notes separator and
    precede explicit anchored notes. The upper rule must have a centered small
    caption; no caption vocabulary, font name or corpus identity is trusted.
    """
    rules = _rules(native)
    separators = [l for l in _lines(page) if _plain(l).rstrip("\ufffd").strip() in SEPARATORS]
    if len(rules) != 2 or len(separators) != 1:
        return None
    upper, lower = rules
    sep = separators[0]
    if not sep["bbox"][1] <= lower[1] <= sep["bbox"][3]:
        return None
    # One point is the PDF geometric alignment tolerance, not a confidence score.
    if abs((upper[2]-upper[0])-(lower[2]-lower[0])) > 1:
        return None
    captions = [l for l in _lines(page) if l["bbox"][1] <= upper[1] <= l["bbox"][3]
                and abs((l["bbox"][0]+l["bbox"][2]) / 2-(upper[0]+upper[2])/2) <= 1]
    if len(captions) != 1:
        return None
    anchors = [l for b in page.boxes if b.boxclass == "footnote" for l in (b.textlines or [])
               if detect_footnote_number(_plain(l)) is not None and l["bbox"][1] > sep["bbox"][3]]
    if not anchors:
        return None
    note_size = max(s["size"] for l in anchors for s in l["spans"])
    if max(s["size"] for s in captions[0]["spans"]) >= note_size:
        return None
    return upper, lower, sep, note_size


def _quality(unit, mapped, page, native):
    lines = _selected(unit, page)
    text = "\n".join(p.source_text for p in unit.parts)
    actual, visible = native_evidence(native, lines) if native is not None else ("", False)
    return (direction(lines) == "LTR" and visible and _tokens(actual) == _tokens(text)
            and unit.transformation_status == "ALLOWLIST_ONLY"
            and _decoration_only(text, mapped.markdown[unit.markdown_start:unit.markdown_end])
            and not any(unicodedata.category(c) == "Cc" and c not in "\n\r\t" for c in text)
            and "\ufffd" not in text)


def _editorial_id(sha, page, region_id):
    payload = json.dumps([VERSION, sha, page, region_id], separators=(",", ":"))
    return "editorial-" + hashlib.sha256(payload.encode()).hexdigest()[:24]


def certify_layout_page(parsed, page, document_sha, *, native_page=None):
    """Page-local V2 plus explicit body proof; page cuts never mean completion."""
    page = deepcopy(page)
    for b in page.boxes:
        b.textlines = b.textlines or []
    candidate = certify_v2(parsed, page, document_sha, native_page=native_page)
    family = _family(page, native_page)
    units = {u.region_id: u for u in candidate.provenance.units}
    result = []
    for old in candidate.certificates:
        fields = {k: getattr(old, k) for k in RegionCertificateV2.__dataclass_fields__}
        fields["certificate_version"] = VERSION
        c = RegionCertificateV3(**fields)
        u = units[c.region_id]
        if c.provenance_status == "CERTIFIED" and c.note_number is not None:
            c = replace(c, editorial_unit_id=_editorial_id(document_sha, page.page_number, c.region_id),
                        continuation_state="COMPLETE_LOCAL")
        if u.role != "text" or u.note_number is not None:
            result.append(c)
            continue
        lines = _selected(u, page)
        zone = order = boundary = False
        if family and lines:
            upper, lower, sep, note_size = family
            # Independent inset/full-width panel only. Narrow marginal material
            # and unresolved multiple columns are deliberately not supported.
            frame_width = upper[2]-upper[0]
            zone = (u.source_bbox[1] > upper[1] and u.source_bbox[3] < sep["bbox"][1]
                    and u.source_bbox[0] >= min(upper[0], lower[0])-1
                    and u.source_bbox[2] <= max(upper[2], lower[2])+4
                    and u.source_bbox[2]-u.source_bbox[0] > frame_width / 2
                    and all(max(s["size"] for s in l["spans"]) > note_size for l in lines)
                    and all(round(s["size"],3) == round(max(t["size"] for l in lines for t in l["spans"]),3)
                            or s.get("flags",0) & 1 for l in lines for s in l["spans"])
                    and not any(detect_footnote_number(_plain(l)) is not None for l in lines))
            boundary = (u.status == "MAPPED" and _ownership(u, page)
                        and not any(_intersects(u.source_bbox, (b.x0,b.y0,b.x1,b.y1))
                                    for b in page.boxes if b.boxclass != "text"))
            ids = [min(p.source_line_ids) for p in u.parts]
            order = (ids == sorted(ids) and len(set(ids)) == len(ids)
                     and all(a.bbox[3] <= b.bbox[1]+1 for a,b in zip(u.parts,u.parts[1:])))
        native, visible = native_evidence(native_page, lines) if native_page is not None else ("", False)
        source = "\n".join(p.source_text for p in u.parts)
        # Provenance/order and textual quality are distinct: native trace
        # proves painted horizontal direction, source IDs + geometry prove
        # sequence. Token equivalence is required separately for ACCEPTED.
        direct = bool(lines and direction(lines) == "LTR" and visible)
        proofs = (
            Proof("BODY_ZONE_PROOF", bool(zone), ("TWO_NATIVE_RULES", "CENTERED_UPPER_CAPTION", "ANCHORED_LOWER_NOTES_SEPARATOR", "MAIN_PANEL_WIDTH_AND_TYPOGRAPHY") if zone else ()),
            Proof("OWNERSHIP_PROOF", _ownership(u, page), ("UNIQUE_DISJOINT_SOURCE_IDENTITIES",)),
            Proof("ORDER_PROOF", bool(order and direct), ("SOURCE_IDS_GEOMETRY_NATIVE_HORIZONTAL_DIRECTION",) if order and direct else ()),
            Proof("BOUNDARY_PROOF", bool(boundary), ("FORWARD_MARKDOWN_RANGES", "NO_CONFLICTING_BOX") if boundary else ()),
        )
        certified = all(p.passed for p in proofs) and "\ufffd" not in source
        reasons = tuple(p.name+"_MISSING" for p in proofs if not p.passed)
        if certified:
            quality = "ACCEPTED" if _quality(u, candidate.provenance, page, native_page) else "UNRESOLVED"
            c = replace(c, zone_type="MAIN_BODY", provenance_status="CERTIFIED", quality_status=quality,
                        reason_codes=("SUPPORTED_RULED_MAIN_PANEL", "ALL_BODY_PROOFS_PRESENT") + (() if quality == "ACCEPTED" else ("QUALITY_EVIDENCE_INSUFFICIENT",)),
                        body_proof=proofs)
        else:
            c = replace(c, body_proof=proofs, reason_codes=c.reason_codes+reasons)
        result.append(c)
    return CertifiedPage(candidate.provenance, tuple(result))


def _note_zone(page, native):
    family = _family(page, native)
    if family is None:
        return None
    sep = family[2]
    boxes = [b for b in page.boxes if b.textlines and _bbox(b.textlines)[1] > sep["bbox"][3]]
    if not boxes or any(b.boxclass not in {"text", "footnote", "page-footer"} for b in boxes):
        return None
    return boxes


def _styles(lines):
    return {(s["font"], round(s["size"],3)) for l in lines for s in l["spans"]}


def certify_document(parsed, document_sha, *, native_pages):
    """Deterministic adjacent-page links with independently retained segments.

    A relation is emitted only when the previous open segment has every V2
    proof except completion and the next ruled notes panel has compatible
    typography, a leading unmarked segment and the next consecutive marker.
    The full note flow must pass the existing column adapter unchanged.
    """
    layouts = {p.page_number: p for p in parsed.pages}
    if len(layouts) != len(parsed.pages):
        raise ValueError("Duplicate physical pages")
    results = {n: certify_layout_page(parsed, p, document_sha, native_page=native_pages.get(n))
               for n,p in sorted(layouts.items())}
    for n in sorted(layouts):
        if n+1 not in layouts:
            continue
        previous = results[n]
        terminals = [c for c in previous.certificates if c.note_number is not None and c.end_reason == "PAGE_BOUNDARY"]
        if len(terminals) != 1:
            continue
        terminal = terminals[0]
        if not all(p.passed for p in terminal.proofs if p.name != "continuation"):
            continue
        boxes = _note_zone(layouts[n+1], native_pages.get(n+1))
        if boxes is None:
            continue
        lines = [l for b in boxes for l in b.textlines]
        prior_unit = next(u for u in previous.provenance.units if u.region_id == terminal.region_id)
        styles = _styles(_selected(prior_unit, layouts[n]))
        if not _styles(lines) <= styles:
            continue
        try:
            continuation = map_layout_page(parsed, replace(layouts[n+1], boxes=deepcopy(boxes)), document_sha,
                note_direction="ltr", note_zone_bbox=_bbox(lines), continued_from=previous.provenance)
        except UnresolvedLayout:
            continue
        first = continuation.units[0]
        if (first.continuation_of != terminal.region_id or first.end_reason != "NEXT_NOTE_IN_COLUMN_FLOW"
                or len(continuation.units) < 2 or continuation.units[1].note_number != terminal.note_number+1
                or detect_footnote_number(first.parts[0].source_text) is not None
                or not _ownership(first, layouts[n+1])):
            continue
        first_lines = _selected(first, layouts[n+1])
        native, visible = native_evidence(native_pages[n+1], first_lines)
        first_ids = [min(p.source_line_ids) for p in first.parts]
        if (direction(first_lines) != "LTR" or not visible
                or first_ids != sorted(first_ids) or len(set(first_ids)) != len(first_ids)):
            continue
        # Rebuild this page's immutable Markdown slices; never silently merge
        # cross-page text, retain every unsupported region and its own offsets.
        original = results[n+1]
        zone_keys = {_identity(l) for l in lines}
        retained = [u for u in original.provenance.units
                    if not any((p.source_line_ids,p.bbox) in zone_keys for p in u.parts)]
        removed = [u for u in original.provenance.units if u not in retained]
        removed_keys = {(p.source_line_ids,p.bbox) for u in removed for p in u.parts}
        if removed_keys != zone_keys:
            continue
        pieces = [(u, original.provenance) for u in retained]+[(u, continuation) for u in continuation.units]
        # Retained pre-note regions keep their existing order; note units keep
        # the adapter's column-major editorial sequence, not bbox-y sorting.
        md = canonical = ""
        merged_units = []
        for u, owner in pieces:
            fragment = owner.markdown[u.markdown_start:u.markdown_end]
            plain = owner.canonical_text[u.canonical_start:u.canonical_end]
            merged_units.append(replace(u, markdown_start=len(md), markdown_end=len(md)+len(fragment),
                                        canonical_start=len(canonical), canonical_end=len(canonical)+len(plain)))
            md += fragment
            canonical += plain
        merged = ProvenancePage(document_sha,n+1,md,canonical,tuple(merged_units))
        proof = (Proof("CONTINUATION_PROOF", True, ("ADJACENT_SAME_DOCUMENT", "TWO_RULE_NOTES_PANEL", "IDENTICAL_FONT_SIZE_FAMILY", "UNMARKED_LEADING_SEGMENT", "NEXT_CONSECUTIVE_MARKER", "DISJOINT_COLUMN_FLOW", "NATIVE_LTR_ORDER")),)
        eid = _editorial_id(document_sha,n,terminal.region_id)
        prior_quality = "ACCEPTED" if _quality(prior_unit, previous.provenance, layouts[n], native_pages.get(n)) else "UNRESOLVED"
        updated = replace(terminal, provenance_status="CERTIFIED", quality_status=prior_quality,
            editorial_unit_id=eid, continuation_state="CONTINUES_NEXT_PAGE", continuation_status="CROSS_PAGE_COMPLETE",
            continuation_proof=proof, linked_region_ids=(first.region_id,), reason_codes=("CROSS_PAGE_IDENTITY_PROVEN",))
        results[n] = replace(previous, certificates=tuple(updated if c.region_id == terminal.region_id else c for c in previous.certificates))
        old_by_id = {c.region_id:c for c in original.certificates}
        certificates = []
        for u in merged.units:
            ranges = ((u.markdown_start,u.markdown_end),)
            if u.region_id in old_by_id:
                certificates.append(replace(old_by_id[u.region_id], markdown_ranges=ranges))
                continue
            # Other discovered next-page notes are not promoted by a relation.
            is_first = u.region_id == first.region_id
            source_ids = tuple(k for p in u.parts for k in p.source_line_ids)
            certificates.append(RegionCertificateV3(document_sha,n+1,u.region_id,u.source_bbox,"note","LTR" if is_first else "UNRESOLVED",
                tuple(sorted({k[0] for k in source_ids})),source_ids,ranges,u.mapping_method,
                "CERTIFIED" if is_first else "UNRESOLVED",
                "ACCEPTED" if is_first and _quality(u,merged,layouts[n+1],native_pages[n+1]) else "UNRESOLVED",
                ("CROSS_PAGE_IDENTITY_PROVEN",) if is_first else ("INDEPENDENT_SEGMENT_PROOFS_REQUIRED",),
                note_number=u.note_number,end_reason=u.end_reason,continuation_of=u.continuation_of,
                local_boundary="KNOWN",editorial_unit_id=eid if is_first else None,
                continuation_state="CONTINUED_FROM_PREVIOUS" if is_first else "CONTINUATION_UNRESOLVED",
                continuation_status="CROSS_PAGE_COMPLETE" if is_first else "UNRESOLVED_CONTINUATION",
                continuation_proof=proof if is_first else (),linked_region_ids=(terminal.region_id,) if is_first else ()))
        results[n+1] = CertifiedPage(merged,tuple(certificates))
    return tuple(results[n] for n in sorted(results))


def extract_pdf_region_certificates(path, *, pages=None):
    import pymupdf
    from pymupdf4llm.helpers.document_layout import parse_document

    sha = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    with pymupdf.open(path) as document:
        selected = sorted(pages) if pages is not None else list(range(1,len(document)+1))
        if len(set(selected)) != len(selected) or any(n < 1 or n > len(document) for n in selected):
            raise ValueError("Unique physical page numbers in document range required")
        parsed = parse_document(document,pages=[n-1 for n in selected],use_ocr=False)
        return certify_document(parsed,sha,native_pages={n:document[n-1] for n in selected})
