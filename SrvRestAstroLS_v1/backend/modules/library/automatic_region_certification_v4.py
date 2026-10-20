"""V4: canonical source order, caption-framed body and separator note lineage.

V3 verdicts are retained where their order-sensitive proofs still hold. The
generic body frame uses only geometry, typography and an explicit notes
boundary. Bottom note panels are recognized from the historical explicit
separator even when the extractor labels their lines as generic text.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import MISSING, dataclass, fields, replace
import hashlib
import json
from pathlib import Path
import re
import statistics
import unicodedata

from modules.library.automatic_region_certification import (
    CertifiedPage, _decoration_only, _intersects, _tokens, direction, native_evidence,
    certify_layout_page as discover,
)
from modules.library.automatic_region_certification_v2 import (
    Proof, RegionCertificateV2, certify_layout_page as certify_v2,
)
from modules.library.automatic_region_certification_v3 import RegionCertificateV3
from modules.library.editorial_evidence_v2 import detect_footnote_number
from modules.library.region_markdown_provenance import (
    ProvenancePage, UnresolvedLayout, _bbox, _identity, _key, _plain, map_layout_page,
)

VERSION = "automatic-region-certification-v4"
SEPARATORS = {"Notas y Fuentes", "Notas y Fuentes:", "Notes and Sources"}
_NUMERIC_NOTE = re.compile(r"^(\d{1,3})[.)]?\s+\S")
_MISSING = {"zone": "ZONE_AMBIGUOUS", "direction": "DIRECTION_UNPROVEN",
            "ownership": "PROVENANCE_OVERLAP", "local_boundary": "BOUNDARY_UNPROVEN",
            "order": "COLUMN_AMBIGUOUS", "continuation": "CROSS_PAGE_CONTINUATION_UNRESOLVED"}


@dataclass(frozen=True)
class RegionCertificateV4(RegionCertificateV3):
    certificate_version: str = VERSION


@dataclass(frozen=True)
class BodyFrame:
    caption: dict
    notes_top: float
    content_left: float
    content_right: float
    note_size: float


def _lines(page):
    return [l for b in page.boxes for l in (b.textlines or [])]


def _line_key(line):
    return (line["bbox"][1], line["bbox"][0], line["bbox"][3], line["bbox"][2],
            _identity(line), _plain(line))


def _box_key(box):
    return (box.y0, box.x0, box.y1, box.x1, box.boxclass,
            tuple(_line_key(l) for l in (box.textlines or [])))


def canonicalize_page(page):
    page = deepcopy(page)
    for box in page.boxes:
        box.textlines = sorted(box.textlines or [], key=_line_key)
    page.boxes = sorted(page.boxes, key=_box_key)
    return page


def _part_lines(unit, page):
    by_identity = {_identity(l): l for l in _lines(page)}
    result = []
    for part in unit.parts:
        line = by_identity.get((part.source_line_ids, part.bbox))
        if line is not None:
            result.append(line)
    return result


def _selected(unit, page):
    return sorted(_part_lines(unit, page),
                  key=lambda l: (l["bbox"][1], l["bbox"][0], _identity(l)))


def _canonical_tokens(text):
    return _tokens(unicodedata.normalize("NFKC", text))


def _note_start(text):
    value = detect_footnote_number(text)
    if value is not None:
        return value
    match = _NUMERIC_NOTE.match(text)
    return int(match.group(1)) if match else None


def _separator(page):
    found = [l for l in _lines(page)
             if _plain(l).rstrip("\ufffd").strip() in SEPARATORS]
    return found[0] if len(found) == 1 else None


def _note_zone(page):
    sep = _separator(page)
    if sep is None:
        return None
    from pymupdf4llm.helpers.document_layout import LayoutBox

    top = sep["bbox"][3]
    boxes = []
    for box in page.boxes:
        kept = [l for l in (box.textlines or []) if l is not sep and l["bbox"][1] >= top - 1]
        if not kept:
            continue
        if box.boxclass not in {"text", "footnote", "page-footer", "section-header"}:
            return None
        boxes.append(LayoutBox(min(l["bbox"][0] for l in kept), min(l["bbox"][1] for l in kept),
                               max(l["bbox"][2] for l in kept), max(l["bbox"][3] for l in kept),
                               box.boxclass, textlines=deepcopy(kept)))
    if not boxes:
        return None
    lines = [l for b in boxes for l in b.textlines]
    if not any(_note_start(_plain(l)) is not None for l in lines):
        return None
    return boxes, top


def _map_note_zone(parsed, page, document_sha, boxes, *, continued_from=None,
                   leading_note=None):
    lines = [l for b in boxes for l in b.textlines]
    try:
        return map_layout_page(parsed, replace(page, boxes=boxes), document_sha,
                               note_direction="ltr", note_zone_bbox=_bbox(lines),
                               continued_from=continued_from, note_start=_note_start,
                               leading_note=leading_note)
    except UnresolvedLayout:
        return None


def _body_note_markers(page, zone_lines):
    zone_ids = {_identity(l) for l in zone_lines}
    text = "\n".join(_plain(l) for l in _lines(page) if _identity(l) not in zone_ids)
    return {int(value) for value in re.findall(r"\[(\d{1,3})\]", text)}


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


def _styles(lines):
    return {(s["font"], round(s["size"], 3)) for l in lines for s in l["spans"]}


def _quality_v4(unit, page, native):
    lines = _part_lines(unit, page)
    text = "\n".join(p.source_text for p in unit.parts)
    actual, visible = native_evidence(native, lines) if native is not None else ("", False)
    return (direction(lines) == "LTR" and visible and _tokens(actual) == _tokens(text)
            and unit.transformation_status == "ALLOWLIST_ONLY"
            and not any(unicodedata.category(c) == "Cc" and c not in "\n\r\t" for c in text)
            and "\ufffd" not in text)


def _editorial_id(sha, page, region_id):
    payload = json.dumps([VERSION, sha, page, region_id], separators=(",", ":"))
    return "editorial-" + hashlib.sha256(payload.encode()).hexdigest()[:24]


def _body_frame(page):
    zone = _note_zone(page)
    if zone is None:
        return None
    note_boxes, notes_top = zone
    note_lines = [l for b in note_boxes for l in b.textlines]
    anchors = [l for l in note_lines if _note_start(_plain(l)) is not None]
    if not anchors:
        return None
    ignored_roles = {"page-header", "page-footer"}
    content = [l for l in _lines(page)
               if l["bbox"][1] < notes_top - 1
               and not any(l is b for box in page.boxes if box.boxclass in ignored_roles
                           for b in (box.textlines or []))
               and _plain(l).rstrip("\ufffd").strip() not in SEPARATORS]
    if not content:
        return None
    left = min(l["bbox"][0] for l in content)
    right = max(l["bbox"][2] for l in content)
    width = right - left
    if width <= 0:
        return None
    note_size = max(s["size"] for l in anchors for s in l["spans"])
    captions = [l for l in content
                if l["bbox"][2] - l["bbox"][0] <= 0.35 * width
                and abs((l["bbox"][0] + l["bbox"][2]) / 2 - (left + right) / 2)
                <= max(2.0, 0.02 * width)
                and max(s["size"] for s in l["spans"]) <= note_size - 0.2
                and _note_start(_plain(l)) is None
                and l["bbox"][3] < notes_top - 1]
    if len(captions) != 1:
        return None
    return BodyFrame(captions[0], notes_top, left, right, note_size)


def _body_zone(unit, page, frame):
    if frame is None:
        return False, ()
    lines = _part_lines(unit, page)
    if not lines or len(lines) < 2 or unit.status != "MAPPED":
        return False, ()
    source = "\n".join(p.source_text for p in unit.parts)
    bbox = unit.source_bbox
    width = frame.content_right - frame.content_left
    if (bbox[1] < frame.caption["bbox"][3] - 1 or bbox[3] > frame.notes_top + 1
            or bbox[0] < frame.content_left - 1 or bbox[2] > frame.content_right + 4
            or bbox[2] - bbox[0] < 0.55 * width
            or "\ufffd" in source
            or any(_note_start(_plain(l)) is not None for l in lines)):
        return False, ()
    sizes = [s["size"] for l in lines for s in l["spans"]]
    dominant = max(sizes)
    if dominant <= frame.note_size + 0.1:
        return False, ()
    if not all(round(s["size"], 3) == round(dominant, 3) or s["size"] < dominant
               for l in lines for s in l["spans"]):
        return False, ()
    return True, ("CENTERED_EDITORIAL_CAPTION", "MAIN_CONTENT_BAND",
                  "EXPLICIT_NOTES_BOUNDARY", "HOMOGENEOUS_BODY_TYPOGRAPHY")


def _body_proofs(unit, page, native, frame):
    lines = _part_lines(unit, page)
    source = "\n".join(p.source_text for p in unit.parts)
    zone, evidence = _body_zone(unit, page, frame)
    ownership = _ownership(unit, page)
    boundary = (unit.status == "MAPPED" and ownership
                and not any(_intersects(unit.source_bbox, (b.x0, b.y0, b.x1, b.y1))
                            for b in page.boxes if b.boxclass != "text"))
    ids = [min(p.source_line_ids) for p in unit.parts]
    order = (ids == sorted(ids) and len(set(ids)) == len(ids)
             and all(a.bbox[3] <= b.bbox[1] + 1 for a, b in zip(unit.parts, unit.parts[1:])))
    actual, visible = native_evidence(native, lines) if native is not None else ("", False)
    direct = bool(lines and direction(lines) == "LTR")
    order_evidence = (("CANONICAL_SOURCE_ID_GEOMETRY_ORDER",)
                      + (("VISIBLE_NATIVE_HORIZONTAL_ORDER",) if visible
                         else ("NATIVE_TRACE_NOT_VISIBLE",)))
    proofs = (
        Proof("BODY_ZONE_PROOF", bool(zone), evidence),
        Proof("OWNERSHIP_PROOF", ownership, ("UNIQUE_DISJOINT_SOURCE_IDENTITIES",)),
        Proof("ORDER_PROOF", bool(order and direct),
              order_evidence if order and direct else ()),
        Proof("BOUNDARY_PROOF", boundary,
              ("FORWARD_MARKDOWN_RANGES", "NO_CONFLICTING_BOX") if boundary else ()),
    )
    certified = all(p.passed for p in proofs) and "\ufffd" not in source
    quality = "ACCEPTED" if certified and _quality_v4(unit, page, native) else "UNRESOLVED"
    return proofs, certified, quality


def _body_certificate(base, unit, page, native, frame):
    base = _ensure_v4(base)
    proofs, certified, quality = _body_proofs(unit, page, native, frame)
    reasons = tuple(p.name + "_MISSING" for p in proofs if not p.passed)
    if certified:
        codes = ("CENTERED_EDITORIAL_CAPTION", "MAIN_CONTENT_BAND",
                 "EXPLICIT_NOTES_BOUNDARY", "ALL_BODY_PROOFS_PRESENT")
        if quality != "ACCEPTED":
            codes += ("QUALITY_EVIDENCE_INSUFFICIENT",)
        return replace(base, certificate_version=VERSION, zone_type="MAIN_BODY",
                       provenance_status="CERTIFIED", quality_status=quality,
                       reason_codes=codes, body_proof=proofs)
    return replace(base, certificate_version=VERSION, body_proof=proofs,
                   provenance_status="UNRESOLVED", quality_status="UNRESOLVED",
                   reason_codes=tuple(dict.fromkeys(tuple(base.reason_codes) + reasons)))


def _note_direction(unit, page, native):
    lines = _part_lines(unit, page)
    source = "\n".join(p.source_text for p in unit.parts)
    actual, visible = native_evidence(native, lines) if native is not None else ("", False)
    return (bool(lines) and direction(lines) == "LTR" and visible
            and _canonical_tokens(actual) == _canonical_tokens(source))


def _note_certificate(document_sha, page_number, unit, page, native, *, all_numbers,
                      linked=None, linked_proof=(), leading_local=False):
    source = "\n".join(p.source_text for p in unit.parts)
    lines = _part_lines(unit, page)
    zone = bool(_separator(page) and unit.status == "MAPPED" and lines)
    direction_ok = _note_direction(unit, page, native)
    ownership = _ownership(unit, page)
    first_start = _note_start(unit.parts[0].source_text)
    continuation = linked is not None
    local = (unit.status == "MAPPED" and bool(unit.parts)
             and ((first_start == unit.note_number)
                  or (continuation and first_start is None and unit.continuation_of is not None)
                  or (leading_local and first_start is None))
             and unit.end_reason in {"NEXT_NOTE_IN_COLUMN_FLOW", "PAGE_BOUNDARY"})
    columns = {p.column for p in unit.parts}
    order = (unit.note_number is not None and bool(all_numbers)
             and all(b == a + 1 for a, b in zip(all_numbers, all_numbers[1:]))
             and None not in columns and len(columns) <= 2)
    complete = bool(local and unit.end_reason == "NEXT_NOTE_IN_COLUMN_FLOW")
    proofs = (
        Proof("zone", zone, ("UNIQUE_PRECEDING_NOTES_SEPARATOR", "EXPLICIT_NOTE_ANCHORS",
                             "MAPPED_NOTE_FLOW") if zone else ()),
        Proof("direction", direction_ok,
              ("LTR_STRONG_SCRIPT", "VISIBLE_HORIZONTAL_NATIVE_CANONICAL_TOKEN_ORDER")
              if direction_ok else ()),
        Proof("ownership", ownership,
              ("UNIQUE_SOURCE_IDENTITIES", "DISJOINT_SOURCE_LINE_GEOMETRY",
               "FORWARD_MARKDOWN_RANGES") if ownership else ()),
        Proof("local_boundary", local, (("PAGE_LOCAL_BODY_MARKER", "SEQUENTIAL_NEXT_MARKER")
                                       if leading_local and local else
                                       ((unit.end_reason,) if local else ()))),
        Proof("order", order,
              ("CONSECUTIVE_MARKERS", "DISJOINT_ONE_OR_TWO_COLUMN_FLOW") if order else ()),
        Proof("continuation", complete,
              ("NEXT_EXPLICIT_NOTE_MARKER",) if complete else ()),
    )
    certified = all(p.passed for p in proofs) and "\ufffd" not in source
    if linked is not None:
        certified = (all(p.passed for p in proofs if p.name != "continuation")
                     and linked_proof.passed and "\ufffd" not in source)
        proofs += (linked_proof,)
        complete = False
    quality = "ACCEPTED" if certified and _quality_v4(unit, page, native) else "UNRESOLVED"
    reasons = [reason for p in proofs if not p.passed for reason in (_MISSING.get(p.name),) if reason]
    if "\ufffd" in source:
        reasons.append("CORRUPT_TEXT_SIGNAL")
    if certified:
        reasons = ["CANONICAL_NATIVE_ORDER_PROVEN"]
        if leading_local:
            reasons.append("PAGE_LOCAL_LEADING_NOTE_PROVEN")
        if linked is not None:
            reasons.append("CROSS_PAGE_IDENTITY_PROVEN")
        if quality != "ACCEPTED":
            reasons.append("QUALITY_EVIDENCE_INSUFFICIENT")
    else:
        reasons.append("PROVENANCE_UNRESOLVED_QUALITY_UNRESOLVED")
    eid = _editorial_id(document_sha, page_number, unit.region_id) if certified else None
    state = "CONTINUATION_UNRESOLVED"
    status = "UNRESOLVED_CONTINUATION"
    if linked is not None:
        state = "CONTINUED_FROM_PREVIOUS"
        status = "CROSS_PAGE_COMPLETE"
        eid = linked[1]
    elif certified and complete:
        state = "COMPLETE_LOCAL"
        status = "COMPLETE"
    blocks = tuple(sorted({key[0] for p in unit.parts for key in p.source_line_ids}))
    line_ids = tuple(dict.fromkeys(key for p in unit.parts for key in p.source_line_ids))
    cert = RegionCertificateV4(
        document_sha, page_number, unit.region_id, unit.source_bbox, "note",
        "LTR" if direction_ok else "UNRESOLVED", blocks, line_ids,
        ((unit.markdown_start, unit.markdown_end),), unit.mapping_method,
        "CERTIFIED" if certified else "UNRESOLVED", quality, tuple(dict.fromkeys(reasons)),
        note_number=unit.note_number, end_reason=unit.end_reason,
        continuation_of=unit.continuation_of,
        proofs=proofs, local_boundary="KNOWN" if local else "UNRESOLVED",
        continuation_status=status, certificate_version=VERSION,
        body_proof=(), editorial_unit_id=eid, continuation_state=state,
        continuation_proof=(linked_proof,) if linked is not None else (),
        linked_region_ids=(linked[0],) if linked is not None else ())
    return cert


def _without_line(boxes, line):
    from pymupdf4llm.helpers.document_layout import LayoutBox

    key = _identity(line)
    rebuilt = []
    removed = False
    for box in boxes:
        kept = [l for l in (box.textlines or []) if _identity(l) != key]
        if len(kept) != len(box.textlines or []):
            removed = True
        if not kept:
            continue
        rebuilt.append(LayoutBox(min(l["bbox"][0] for l in kept), min(l["bbox"][1] for l in kept),
                                 max(l["bbox"][2] for l in kept), max(l["bbox"][3] for l in kept),
                                 box.boxclass, textlines=deepcopy(kept)))
    return rebuilt if removed and rebuilt else []


def _retained_page(page, zone_lines):
    from pymupdf4llm.helpers.document_layout import LayoutBox

    keys = {_identity(l) for l in zone_lines}
    boxes = []
    for box in page.boxes:
        kept = [l for l in (box.textlines or []) if _identity(l) not in keys]
        if not kept:
            continue
        boxes.append(LayoutBox(min(l["bbox"][0] for l in kept), min(l["bbox"][1] for l in kept),
                               max(l["bbox"][2] for l in kept), max(l["bbox"][3] for l in kept),
                               box.boxclass, textlines=deepcopy(kept)))
    return replace(page, boxes=boxes)


def _merge_page(document_sha, page_number, retained, retained_certs, zone, zone_certs):
    md = canonical = ""
    units = []
    certs = []
    for unit in retained.units:
        units.append(replace(unit, markdown_start=len(md),
                             markdown_end=len(md) + (unit.markdown_end - unit.markdown_start),
                             canonical_start=len(canonical),
                             canonical_end=len(canonical) + (unit.canonical_end - unit.canonical_start)))
        md += retained.markdown[unit.markdown_start:unit.markdown_end]
        canonical += retained.canonical_text[unit.canonical_start:unit.canonical_end]
    for unit in zone.units:
        units.append(replace(unit, markdown_start=len(md),
                             markdown_end=len(md) + (unit.markdown_end - unit.markdown_start),
                             canonical_start=len(canonical),
                             canonical_end=len(canonical) + (unit.canonical_end - unit.canonical_start)))
        md += zone.markdown[unit.markdown_start:unit.markdown_end]
        canonical += zone.canonical_text[unit.canonical_start:unit.canonical_end]
    merged = ProvenancePage(document_sha, page_number, md, canonical, tuple(units))
    by_id = {c.region_id: c for c in retained_certs + zone_certs}
    for unit in merged.units:
        base = by_id[unit.region_id]
        certs.append(replace(base, markdown_ranges=((unit.markdown_start, unit.markdown_end),)))
    return CertifiedPage(merged, tuple(certs))


def _terminal_link(previous, previous_page, first, page, native, terminal, next_number):
    if (terminal is None or terminal.end_reason != "PAGE_BOUNDARY"
            or not all(p.passed for p in terminal.proofs if p.name != "continuation")
            or first.note_number != terminal.note_number):
        return None
    prior_unit = next((u for u in previous.provenance.units
                       if u.region_id == terminal.region_id), None)
    if prior_unit is None:
        return None
    if (first.continuation_of != terminal.region_id
            or first.end_reason != "NEXT_NOTE_IN_COLUMN_FLOW"
            or next_number != terminal.note_number + 1
            or _note_start(first.parts[0].source_text) is not None
            or not _ownership(first, page)
            or not _note_direction(first, page, native)):
        return None
    prior_styles = _styles(_part_lines(prior_unit, previous_page))
    first_lines = _part_lines(first, page)
    if not _styles(first_lines) <= prior_styles:
        return None
    first_ids = [min(p.source_line_ids) for p in first.parts]
    if first_ids != sorted(first_ids) or len(set(first_ids)) != len(first_ids):
        return None
    eid = _editorial_id(previous.provenance.source_sha256, previous.provenance.pdf_page,
                        terminal.region_id)
    proof = Proof("CONTINUATION_PROOF", True, (
        "ADJACENT_SAME_DOCUMENT", "EXPLICIT_NOTES_SEPARATOR", "IDENTICAL_FONT_SIZE_FAMILY",
        "UNMARKED_LEADING_SEGMENT", "NEXT_CONSECUTIVE_MARKER", "DISJOINT_COLUMN_FLOW",
        "NATIVE_LTR_ORDER", "CANONICAL_SOURCE_ORDER"))
    return proof, eid


def _find_terminal(result, note_number=None):
    if result is None:
        return None
    terminals = [c for c in result.certificates
                 if c.note_number is not None and c.end_reason == "PAGE_BOUNDARY"]
    if note_number is not None:
        terminals = [c for c in terminals if c.note_number == note_number]
    return terminals[0] if len(terminals) == 1 else None


def _ensure_v4(cert):
    if isinstance(cert, RegionCertificateV4):
        return cert
    values = {}
    for field in fields(RegionCertificateV3):
        if field.name == "certificate_version":
            continue
        if hasattr(cert, field.name):
            values[field.name] = getattr(cert, field.name)
        elif field.default is not MISSING:
            values[field.name] = field.default
        else:
            raise TypeError(f"Missing certificate field {field.name}")
    return RegionCertificateV4(**values, certificate_version=VERSION)


def _upgrade_v2_notes(candidate, page, native):
    units = {u.region_id: u for u in candidate.provenance.units}
    certs = []
    for cert in candidate.certificates:
        cert = _ensure_v4(cert)
        if cert.note_number is None:
            certs.append(cert)
            continue
        unit = units[cert.region_id]
        direction_ok = _note_direction(unit, page, native)
        proofs = tuple(Proof(p.name, direction_ok, (
            "LTR_STRONG_SCRIPT", "VISIBLE_HORIZONTAL_NATIVE_CANONICAL_TOKEN_ORDER")
            if p.name == "direction" and direction_ok else
            (() if p.name == "direction" else p.evidence))
            if p.name == "direction" else p for p in cert.proofs)
        certified = all(p.passed for p in proofs)
        quality = "ACCEPTED" if certified and _quality_v4(unit, page, native) else "UNRESOLVED"
        complete = (cert.end_reason == "NEXT_NOTE_IN_COLUMN_FLOW" and certified)
        reasons = [r for r in cert.reason_codes if r != "DIRECTION_UNPROVEN"]
        if certified:
            reasons = ["CANONICAL_NATIVE_ORDER_PROVEN"]
            if quality != "ACCEPTED":
                reasons.append("QUALITY_EVIDENCE_INSUFFICIENT")
        else:
            reasons += [_MISSING.get(p.name) for p in proofs if not p.passed and _MISSING.get(p.name)]
        eid = _editorial_id(candidate.provenance.source_sha256, page.page_number,
                            unit.region_id) if certified else None
        certs.append(replace(cert, certificate_version=VERSION, proofs=proofs,
                             provenance_status="CERTIFIED" if certified else "UNRESOLVED",
                             quality_status=quality, reason_codes=tuple(dict.fromkeys(reasons)),
                             continuation_status="COMPLETE" if complete else "UNRESOLVED_CONTINUATION",
                             editorial_unit_id=eid,
                             continuation_state="COMPLETE_LOCAL" if complete else "CONTINUATION_UNRESOLVED"))
    return CertifiedPage(candidate.provenance, tuple(certs))


def _certify_page(parsed, page, document_sha, native, previous=None, previous_page=None):
    page = canonicalize_page(page)
    zone = _note_zone(page)
    if zone is None:
        candidate = certify_v2(parsed, page, document_sha, native_page=native)
        candidate = _upgrade_v2_notes(candidate, page, native)
        units = {u.region_id: u for u in candidate.provenance.units}
        frame = _body_frame(page)
        certs = []
        for cert in candidate.certificates:
            unit = units[cert.region_id]
            if unit.role == "text" and unit.note_number is None:
                certs.append(_body_certificate(cert, unit, page, native, frame))
            else:
                certs.append(cert)
        return CertifiedPage(candidate.provenance, tuple(certs)), None
    boxes, _ = zone
    zone_lines = [l for b in boxes for l in b.textlines]
    first_line = min(zone_lines, key=lambda l: (l["bbox"][1], l["bbox"][0], _identity(l)))
    continued = _note_start(_plain(first_line)) is None
    mapped = None
    link = None
    leading_note = None
    prior_open = _find_terminal(previous) if previous is not None else None
    if continued:
        markers = [n for n in (_note_start(_plain(l)) for l in zone_lines) if n is not None]
        if markers:
            candidate = min(markers) - 1
            if (candidate >= 1 and candidate in _body_note_markers(page, zone_lines)
                    and (prior_open is None or prior_open.note_number != candidate)):
                leading_note = candidate
        if leading_note is not None:
            mapped = _map_note_zone(parsed, page, document_sha, boxes, leading_note=leading_note)
            if mapped is not None and mapped.units and mapped.units[0].note_number != leading_note:
                mapped = _map_note_zone(parsed, page, document_sha, boxes)
                leading_note = None
        else:
            adjacent = (previous is not None
                        and previous.provenance.pdf_page == page.page_number - 1)
            terminal = _find_terminal(previous) if adjacent else None
            if terminal is not None and previous is not None:
                mapped = _map_note_zone(parsed, page, document_sha, boxes,
                                        continued_from=previous.provenance)
            else:
                mapped = _map_note_zone(parsed, page, document_sha, boxes)
    else:
        mapped = _map_note_zone(parsed, page, document_sha, boxes)
    if (mapped is None or not mapped.units) and continued:
        orphaned = _without_line(boxes, first_line)
        if orphaned:
            boxes = orphaned
            zone_lines = [l for b in boxes for l in b.textlines]
            mapped = _map_note_zone(parsed, page, document_sha, boxes)
            leading_note = None
    if mapped is not None and mapped.units:
        first = mapped.units[0]
        if first.continuation_of is not None:
            terminal = _find_terminal(previous, first.note_number)
            next_number = mapped.units[1].note_number if len(mapped.units) > 1 else None
            if terminal is None or next_number is None:
                mapped = None
            else:
                link = _terminal_link(previous, previous_page, first, page, native,
                                      terminal, next_number)
                if link is None:
                    mapped = None
    if mapped is None or not mapped.units:
        candidate = certify_v2(parsed, page, document_sha, native_page=native)
        candidate = _upgrade_v2_notes(candidate, page, native)
        units = {u.region_id: u for u in candidate.provenance.units}
        frame = _body_frame(page)
        certs = []
        for cert in candidate.certificates:
            unit = units[cert.region_id]
            if unit.role == "text" and unit.note_number is None:
                certs.append(_body_certificate(cert, unit, page, native, frame))
            else:
                certs.append(cert)
        return CertifiedPage(candidate.provenance, tuple(certs)), None

    retained_page = _retained_page(page, zone_lines)
    retained = discover(parsed, retained_page, document_sha, native_page=native)
    frame = _body_frame(page)
    retained_units = {u.region_id: u for u in retained.provenance.units}
    retained_certs = []
    for cert in retained.certificates:
        unit = retained_units[cert.region_id]
        if unit.role == "text" and unit.note_number is None:
            retained_certs.append(_body_certificate(cert, unit, page, native, frame))
        else:
            retained_certs.append(replace(
                _ensure_v4(cert), provenance_status="UNRESOLVED", quality_status="UNRESOLVED",
                reason_codes=tuple(dict.fromkeys(tuple(cert.reason_codes) + ("LAYOUT_UNSUPPORTED",)))))
    numbers = [u.note_number for u in mapped.units if u.note_number is not None]
    zone_certs = []
    for index, unit in enumerate(mapped.units):
        if index == 0 and link is not None:
            proof, eid = link
            terminal = _find_terminal(previous, unit.note_number)
            if terminal is None:
                raise ValueError("Linked continuation lost its terminal certificate")
            zone_certs.append(_note_certificate(document_sha, page.page_number, unit, page, native,
                                               all_numbers=numbers, linked=(terminal.region_id, eid),
                                               linked_proof=proof))
        else:
            zone_certs.append(_note_certificate(document_sha, page.page_number, unit, page, native,
                                               all_numbers=numbers,
                                               leading_local=bool(index == 0 and leading_note is not None)))
    result = _merge_page(document_sha, page.page_number, retained.provenance, retained_certs,
                         mapped, zone_certs)
    return result, link


def certify_layout_page(parsed, page, document_sha, *, native_page=None):
    parsed = _canonical_parsed(parsed)
    result, _ = _certify_page(parsed, page, document_sha, native_page)
    return result


def _canonical_parsed(parsed):
    pages = [canonicalize_page(p) for p in sorted(parsed.pages, key=lambda p: p.page_number)]
    if len({p.page_number for p in pages}) != len(pages):
        raise ValueError("Duplicate physical pages")
    return replace(parsed, pages=pages)


def certify_document(parsed, document_sha, *, native_pages):
    parsed = _canonical_parsed(parsed)
    layouts = {p.page_number: p for p in parsed.pages}
    results = {}
    for number in sorted(layouts):
        previous = results.get(number - 1)
        result, link = _certify_page(parsed, layouts[number], document_sha,
                                     native_pages.get(number), previous,
                                     layouts.get(number - 1))
        first = next((c for c in result.certificates
                      if c.continuation_state == "CONTINUED_FROM_PREVIOUS"), None)
        if link is not None and previous is not None and first is not None:
            terminal = _find_terminal(previous, first.note_number)
            if terminal is not None and first.linked_region_ids:
                proof, eid = link
                prior_unit = next((u for u in previous.provenance.units
                                   if u.region_id == terminal.region_id), None)
                prior_quality = ("ACCEPTED" if prior_unit is not None
                                 and _quality_v4(prior_unit, layouts[number - 1],
                                                 native_pages.get(number - 1))
                                 else "UNRESOLVED")
                codes = ("CROSS_PAGE_IDENTITY_PROVEN",)
                if prior_quality != "ACCEPTED":
                    codes += ("QUALITY_EVIDENCE_INSUFFICIENT",)
                updated = replace(terminal, provenance_status="CERTIFIED", quality_status=prior_quality,
                                  editorial_unit_id=eid, continuation_state="CONTINUES_NEXT_PAGE",
                                  continuation_status="CROSS_PAGE_COMPLETE",
                                  continuation_proof=(proof,),
                                  linked_region_ids=(first.region_id,), reason_codes=codes)
                results[number - 1] = replace(previous, certificates=tuple(
                    updated if c.region_id == terminal.region_id else c for c in previous.certificates))
        results[number] = result
    return tuple(results[n] for n in sorted(results))


def extract_pdf_region_certificates(path, *, pages=None):
    import pymupdf
    from pymupdf4llm.helpers.document_layout import parse_document

    sha = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    with pymupdf.open(path) as document:
        selected = sorted(pages) if pages is not None else list(range(1, len(document) + 1))
        if len(set(selected)) != len(selected) or any(n < 1 or n > len(document) for n in selected):
            raise ValueError("Unique physical page numbers in document range required")
        parsed = parse_document(document, pages=[n - 1 for n in selected], use_ocr=False)
        return certify_document(parsed, sha, native_pages={n: document[n - 1] for n in selected})
