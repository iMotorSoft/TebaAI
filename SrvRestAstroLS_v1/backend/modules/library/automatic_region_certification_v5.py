"""V5: explicit positive cross-page editorial identity proof.

V4 remains the historical frozen certifier. V5 reuses V4 for body, notes,
quality and local safety, then re-validates every cross-page link against a
named positive identity contract. A link is only retained when the same
editorial unit is positively proven; missing evidence fails closed to
UNRESOLVED and an explicit contradiction fails to IDENTITY_REJECTED.

The contract separates:
  CANDIDATE_CONTINUATION  note terminal at a page boundary, not yet proven
  IDENTITY_PROVEN         all positive predicates passed
  IDENTITY_UNRESOLVED     evidence missing; no link
  IDENTITY_REJECTED       at least one structural contradiction; no link
"""
from __future__ import annotations

from dataclasses import MISSING, dataclass, fields, replace
import hashlib
import json
from pathlib import Path
import re
from types import SimpleNamespace
import unicodedata

from modules.library.annotation_preseal_validation import (
    canonical_document as source_canonical_document,
    marker_number as source_marker_number,
)
from modules.library.automatic_region_certification import CertifiedPage, native_evidence
from modules.library.automatic_region_certification_v2 import Proof
from modules.library.automatic_region_certification_v3 import RegionCertificateV3
from modules.library.automatic_region_certification_v4 import (
    RegionCertificateV4,
    _canonical_parsed,
    _canonical_tokens,
    _note_start,
    _note_zone,
    _ownership,
    _part_lines,
    _separator,
    _styles,
    certify_document as certify_v4,
    certify_layout_page as certify_v4_page,
)
from modules.library.region_markdown_provenance import SourcePart, _identity

VERSION = "automatic-region-certification-v5"

CANDIDATE_CONTINUATION = "CANDIDATE_CONTINUATION"
IDENTITY_PROVEN = "IDENTITY_PROVEN"
IDENTITY_UNRESOLVED = "IDENTITY_UNRESOLVED"
IDENTITY_REJECTED = "IDENTITY_REJECTED"
IDENTITY_NOT_CROSS_PAGE = "NOT_CROSS_PAGE"

CONTRADICTION_PROOFS = {
    "SAME_NOTE_NUMBER",
    "NEXT_MARKER_CONSECUTIVE",
    "TERMINAL_IS_LAST_NOTE",
    "LEADING_IS_FIRST_NOTE",
    "COLUMN_LINEAGE",
    "STYLE_COMPATIBLE",
    "OWNERSHIP_BOTH",
    "CANONICAL_ORDER_BOTH",
}
TERMINAL_PUNCTUATION = (".", "!", "?", "。", "！", "？")


@dataclass(frozen=True)
class RegionCertificateV5(RegionCertificateV4):
    certificate_version: str = VERSION
    identity_state: str = IDENTITY_UNRESOLVED
    identity_proof: tuple[Proof, ...] = ()
    identity_evidence: tuple[str, ...] = ()


def _note_units(result):
    return tuple(u for u in result.provenance.units if u.note_number is not None)


def _marked_start(unit):
    return bool(unit.parts) and _note_start(unit.parts[0].source_text) is not None


def _zone_columns(page):
    """Independent x-projection columns and their reading order (LTR)."""
    zone = _note_zone(page)
    if zone is None:
        return None
    boxes, top = zone
    lines = [line for box in boxes for line in box.textlines]
    if not lines:
        return None
    columns = []
    for line in sorted(lines, key=lambda item: tuple(item["bbox"])):
        x0, _, x1, _ = line["bbox"]
        hits = [column for column in columns if x0 < column[1] and column[0] < x1]
        if len(hits) > 1:
            return None
        if hits:
            column = hits[0]
            column[0] = min(column[0], x0)
            column[1] = max(column[1], x1)
            column[2].append(line)
        else:
            columns.append([x0, x1, [line]])
    columns.sort(key=lambda column: column[0])
    index = {
        _identity(line): position
        for position, (_, _, members) in enumerate(columns)
        for line in members
    }
    bottom = max(line["bbox"][3] for line in lines)
    return {"top": top, "bottom": bottom, "columns": columns, "index": index}


def _ordered_lines(unit, layout):
    return sorted(_part_lines(unit, layout),
                  key=lambda line: (line["bbox"][1], line["bbox"][0], _identity(line)))


def _column_of(line, zone):
    return zone["index"].get(_identity(line)) if zone is not None else None


def _base_font(font):
    font = re.sub(r"-(Italic|Bold|BoldItalic)MT$", "", font)
    for suffix in ("PSMT", "MT", "PS"):
        if font.endswith(suffix):
            return font[:-len(suffix)]
    return font


def _base_styles(styles):
    return {(_base_font(font), round(size, 3)) for font, size in styles}


def _style_subset(unit, layout, prior_unit, prior_layout):
    current = _base_styles(_styles(_part_lines(unit, layout)))
    prior = _base_styles(_styles(_part_lines(prior_unit, prior_layout)))
    return bool(current) and current == prior


def _latin_only(text):
    normalized = unicodedata.normalize("NFKC", text)
    return "".join(
        char for char in normalized
        if not ("\u0590" <= char <= "\u05ff")
        and not ("\u0600" <= char <= "\u06ff")
    )


def _direction_compatible(unit, layout, native):
    lines = _part_lines(unit, layout)
    if not lines or not native:
        return False
    actual, visible = native_evidence(native, lines)
    if not visible:
        return False
    source = "\n".join(part.source_text for part in unit.parts)
    return (_canonical_tokens(actual) == _canonical_tokens(source)
            or _canonical_tokens(_latin_only(actual))
            == _canonical_tokens(_latin_only(source)))


def _canonical_order(unit):
    ids = [min(part.source_line_ids) for part in unit.parts]
    return ids == sorted(ids) and len(set(ids)) == len(ids)


def _last_line_text(unit):
    return unit.parts[-1].source_text if unit.parts else ""


def _identity_contract(previous, previous_layout, previous_native, terminal_unit,
                       page, layout, native, first_unit, *, prior_units=None,
                       next_units=None):
    """Positive proof that both segments are the same editorial note unit.

    Every hard predicate is structural and deterministic. No semantic model,
    embedding or filename is consulted. Missing native/geometry evidence fails
    closed; an explicit contradiction is reported as IDENTITY_REJECTED.
    """
    prior_zone = _zone_columns(previous_layout)
    next_zone = _zone_columns(layout)
    prior_notes = tuple(u for u in (prior_units if prior_units is not None
                                    else previous.units)
                        if u.note_number is not None)
    next_note_units = tuple(u for u in (next_units if next_units is not None
                                        else page.units)
                            if u.note_number is not None)
    first_next_note = next_note_units[0] if next_note_units else None
    following = tuple(u for u in next_note_units
                     if u.region_id != first_unit.region_id and _marked_start(u))
    next_number = following[0].note_number if following else None

    terminal_last = _ordered_lines(terminal_unit, previous_layout)[-1:]
    first_lines = _ordered_lines(first_unit, layout)
    first_line = first_lines[0] if first_lines else None
    prior_last_column = (_column_of(terminal_last[0], prior_zone)
                         if terminal_last and prior_zone else None)
    first_column = (_column_of(first_line, next_zone)
                    if first_line is not None and next_zone else None)
    prior_columns = len(prior_zone["columns"]) if prior_zone else 0
    next_columns = len(next_zone["columns"]) if next_zone else 0
    column_lineage = bool(
        prior_zone and next_zone and terminal_last and first_line is not None
        and prior_last_column == prior_columns - 1
        and first_column == 0
    )
    frame = bool(
        prior_zone and next_zone and terminal_last and first_line is not None
        and terminal_unit.source_bbox[3] >= prior_zone["bottom"] - 2.0
        and first_unit.source_bbox[1] <= next_zone["top"] + 30.0
    )
    last_text = _last_line_text(terminal_unit).rstrip()
    supporting_punctuation = bool(last_text and not last_text.endswith(TERMINAL_PUNCTUATION))

    proofs = (
        Proof("ADJACENT_SAME_DOCUMENT", bool(
            previous.source_sha256 == page.source_sha256
            and previous.pdf_page + 1 == page.pdf_page
        ), ("SAME_SOURCE_SHA256", "PHYSICALLY_ADJACENT_PAGES")),
        Proof("TERMINAL_PAGE_BOUNDARY", terminal_unit.end_reason == "PAGE_BOUNDARY",
              ("PAGE_BOUNDARY_END_REASON",)),
        Proof("TERMINAL_IS_LAST_NOTE", bool(
            prior_notes and prior_notes[-1].region_id == terminal_unit.region_id
        ), ("LAST_NOTE_IN_CANONICAL_READING_ORDER",)),
        Proof("LEADING_IS_FIRST_NOTE", bool(
            first_next_note is not None and first_next_note.region_id == first_unit.region_id
        ), ("FIRST_NOTE_IN_CANONICAL_READING_ORDER",)),
        Proof("LEADING_IS_UNMARKED", bool(
            first_unit.parts and _note_start(first_unit.parts[0].source_text) is None
        ), ("UNMARKED_LEADING_SEGMENT",)),
        Proof("SAME_NOTE_NUMBER", first_unit.note_number == terminal_unit.note_number,
              ("CONTINUATION_OWNER_NOTE_NUMBER",)),
        Proof("NEXT_MARKER_CONSECUTIVE", bool(
            next_number is not None
            and terminal_unit.note_number is not None
            and next_number == terminal_unit.note_number + 1
        ), ("NEXT_EXPLICIT_MARKER_IS_N_PLUS_ONE",)),
        Proof("LEADING_ENDS_AT_NEXT_MARKER", first_unit.end_reason == "NEXT_NOTE_IN_COLUMN_FLOW",
              ("NEXT_NOTE_IN_COLUMN_FLOW",)),
        Proof("OWNERSHIP_BOTH", bool(
            _ownership(terminal_unit, previous_layout) and _ownership(first_unit, layout)
        ), ("UNIQUE_DISJOINT_SOURCE_IDENTITIES",)),
        Proof("DIRECTION_BOTH", bool(
            _direction_compatible(terminal_unit, previous_layout, previous_native)
            and _direction_compatible(first_unit, layout, native)
        ), ("LTR_STRONG_SCRIPT", "VISIBLE_HORIZONTAL_NATIVE_CANONICAL_TOKEN_ORDER")),
        Proof("STYLE_COMPATIBLE", _style_subset(
            first_unit, layout, terminal_unit, previous_layout
        ), ("IDENTICAL_FONT_SIZE_FAMILY",)),
        Proof("CANONICAL_ORDER_BOTH", bool(
            _canonical_order(terminal_unit) and _canonical_order(first_unit)
        ), ("CANONICAL_SOURCE_ID_GEOMETRY_ORDER",)),
        Proof("NOTES_SEPARATOR_BOTH", bool(
            _separator(previous_layout) is not None and _separator(layout) is not None
        ), ("UNIQUE_NOTES_SEPARATOR_EACH_PAGE",)),
        Proof("COLUMN_LINEAGE", column_lineage,
              ("TERMINAL_IN_LAST_NOTE_COLUMN", "LEADING_IN_FIRST_NOTE_COLUMN")),
        Proof("NOTE_ZONE_FRAME", frame,
              ("TERMINAL_REACHES_NOTE_ZONE_BOTTOM", "LEADING_STARTS_AT_NOTE_ZONE_TOP")),
    )
    evidence = tuple(code for proof in proofs if proof.passed for code in proof.evidence)
    if supporting_punctuation:
        evidence += ("SECONDARY_NON_TERMINAL_PUNCTUATION",)
    if column_lineage and prior_columns == next_columns == 1:
        evidence += ("SINGLE_COLUMN_LINEAGE",)
    failed = {proof.name for proof in proofs if not proof.passed}
    if not failed:
        state = IDENTITY_PROVEN
    elif failed & CONTRADICTION_PROOFS:
        state = IDENTITY_REJECTED
    else:
        state = IDENTITY_UNRESOLVED
    return state, proofs, evidence


def _ensure_v5(certificate):
    if isinstance(certificate, RegionCertificateV5):
        return certificate
    values = {}
    for field in fields(RegionCertificateV3):
        if field.name == "certificate_version":
            continue
        if hasattr(certificate, field.name):
            values[field.name] = getattr(certificate, field.name)
        elif field.default is not MISSING:
            values[field.name] = field.default
        else:
            raise TypeError(f"Missing certificate field {field.name}")
    for name in ("body_proof", "editorial_unit_id", "continuation_state",
                 "continuation_proof", "linked_region_ids"):
        if hasattr(certificate, name):
            values[name] = getattr(certificate, name)
    values.setdefault("body_proof", ())
    values.setdefault("editorial_unit_id", None)
    values.setdefault("continuation_state", "CONTINUATION_UNRESOLVED")
    values.setdefault("continuation_proof", ())
    values.setdefault("linked_region_ids", ())
    return RegionCertificateV5(certificate_version=VERSION, **values)


def _default_identity(certificate):
    if certificate.zone_type != "note":
        return IDENTITY_NOT_CROSS_PAGE
    if certificate.end_reason == "PAGE_BOUNDARY":
        return CANDIDATE_CONTINUATION
    return IDENTITY_NOT_CROSS_PAGE


def _downgrade(certificate, state, proofs, evidence):
    reasons = tuple(dict.fromkeys(
        tuple(certificate.reason_codes)
        + (("CROSS_PAGE_IDENTITY_UNPROVEN" if state == IDENTITY_UNRESOLVED
            else "CROSS_PAGE_IDENTITY_REJECTED"),)
    ))
    return replace(
        certificate,
        certificate_version=VERSION,
        provenance_status="UNRESOLVED",
        quality_status="UNRESOLVED",
        editorial_unit_id=None,
        continuation_state="CONTINUATION_UNRESOLVED",
        continuation_status="UNRESOLVED_CONTINUATION",
        linked_region_ids=(),
        continuation_proof=(),
        reason_codes=reasons,
        identity_state=state,
        identity_proof=proofs,
        identity_evidence=evidence,
    )


def _upgrade_page(result, updates):
    certificates = []
    for certificate in result.certificates:
        certificate = _ensure_v5(certificate)
        if certificate.region_id in updates:
            certificates.append(updates[certificate.region_id])
            continue
        certificates.append(replace(certificate, identity_state=_default_identity(certificate)))
    return CertifiedPage(result.provenance, tuple(certificates))


def _source_inventory(parsed):
    rows = []
    for page in parsed.pages:
        rows.append({
            "page": page.page_number,
            "width": page.width,
            "height": page.height,
            "boxes": [
                {
                    "index": index,
                    "class": box.boxclass,
                    "bbox": [box.x0, box.y0, box.x1, box.y1],
                    "lines": [
                        {
                            "bbox": list(line["bbox"]),
                            "ids": list(dict.fromkeys(
                                (span["block"], span["line"]) for span in line["spans"]
                            )),
                            "text": "".join(span["text"] for span in line["spans"]),
                            "styles": sorted({
                                (span["font"], span["size"]) for span in line["spans"]
                            }),
                        }
                        for line in box.textlines or []
                    ],
                }
                for index, box in enumerate(page.boxes)
            ],
        })
    return rows


def _synthetic_unit(unit, region_id=None):
    parts = tuple(
        SourcePart(
            bbox=tuple(part["bbox"]),
            source_line_ids=tuple(tuple(pair) for pair in part["ids"]),
            source_sequence=index,
            source_text=part["text"],
            column=None,
        )
        for index, part in enumerate(unit["parts"])
    )
    boxes = [tuple(part["bbox"]) for part in unit["parts"]]
    bbox = (
        min(box[0] for box in boxes), min(box[1] for box in boxes),
        max(box[2] for box in boxes), max(box[3] for box in boxes),
    ) if boxes else (0.0, 0.0, 0.0, 0.0)
    return SimpleNamespace(
        parts=parts, note_number=unit["note_number"],
        end_reason=unit["end_reason"], source_bbox=bbox,
        region_id=region_id, status="MAPPED",
        transformation_status="ALLOWLIST_ONLY", continuation_of=None,
    )


def _unit_line_ids(unit):
    return {tuple(pair) for part in unit["parts"] for pair in part["ids"]}


def _certificate_unit(page, certificate):
    return next((unit for unit in page.provenance.units
                 if unit.region_id == certificate.region_id), None)


def _matching_certificate(page, unit):
    wanted = _unit_line_ids(unit)
    for certificate in page.certificates:
        source = _certificate_unit(page, certificate)
        if source is None:
            continue
        if {tuple(pair) for part in source.parts for pair in part.source_line_ids} == wanted:
            return certificate
    return None


def _containing_certificate(page, unit):
    wanted = _unit_line_ids(unit)
    best = None
    best_overlap = 0
    for certificate in page.certificates:
        source = _certificate_unit(page, certificate)
        if source is None:
            continue
        overlap = len({tuple(pair) for part in source.parts
                       for pair in part.source_line_ids} & wanted)
        if overlap > best_overlap:
            best, best_overlap = certificate, overlap
    return best


def _editorial_id(document_sha, page, region_id):
    payload = json.dumps([VERSION, document_sha, page, region_id],
                         separators=(",", ":"))
    return "editorial-" + hashlib.sha256(payload.encode()).hexdigest()[:24]


def _proven_update(certificate, *, state, proofs, evidence, document_sha, page,
                   linked_id, editorial_id, continuation_state, continuation_of=None,
                   zone_type=None, note_number=None):
    reasons = tuple(dict.fromkeys(
        tuple(certificate.reason_codes) + ("CROSS_PAGE_IDENTITY_PROVEN",)
    ))
    return replace(
        _ensure_v5(certificate),
        certificate_version=VERSION,
        zone_type=zone_type or certificate.zone_type,
        note_number=certificate.note_number if note_number is None else note_number,
        provenance_status="CERTIFIED",
        quality_status="ACCEPTED",
        reason_codes=reasons,
        linked_region_ids=(linked_id,),
        editorial_unit_id=editorial_id,
        continuation_state=continuation_state,
        continuation_status="CROSS_PAGE_COMPLETE",
        continuation_of=continuation_of,
        identity_state=state,
        identity_proof=proofs,
        identity_evidence=evidence,
    )


def _source_candidates(parsed, results, updates, *, document_sha, native_pages):
    inventory = _source_inventory(parsed)
    canonical, _errors = source_canonical_document(inventory)
    by_page = {page.provenance.pdf_page: page for page in results}
    layouts = {page.page_number: page for page in parsed.pages}
    for number in sorted(by_page):
        if number + 1 not in by_page:
            continue
        prior = canonical.get(number, [])
        following = canonical.get(number + 1, [])
        if not prior or not following:
            continue
        terminal = prior[-1]
        leading = following[0]
        if terminal["end_reason"] != "PAGE_BOUNDARY":
            continue
        if leading["continuation_of_page"] != number:
            continue
        if (terminal["note_number"] is None
                or leading["note_number"] != terminal["note_number"]):
            continue
        if source_marker_number(leading["parts"][0]["text"]) is not None:
            continue
        terminal_certificate = _matching_certificate(by_page[number], terminal)
        target_certificate = _containing_certificate(by_page[number + 1], leading)
        if terminal_certificate is None or target_certificate is None:
            continue
        if (updates[number].get(terminal_certificate.region_id) is not None
                or updates[number + 1].get(target_certificate.region_id) is not None):
            continue
        prior_units = [
            _synthetic_unit(unit, terminal_certificate.region_id
                            if unit is terminal else None)
            for unit in prior
        ]
        next_units = [
            _synthetic_unit(unit, target_certificate.region_id
                            if unit is leading else None)
            for unit in following
        ]
        terminal_unit = prior_units[-1]
        leading_unit = next_units[0]
        state, proofs, evidence = _identity_contract(
            by_page[number].provenance, layouts[number], native_pages.get(number),
            terminal_unit, by_page[number + 1].provenance, layouts[number + 1],
            native_pages.get(number + 1), leading_unit,
            prior_units=prior_units, next_units=next_units,
        )
        if state != IDENTITY_PROVEN:
            continue
        editorial = _editorial_id(document_sha, number, terminal_certificate.region_id)
        updates[number][terminal_certificate.region_id] = _proven_update(
            terminal_certificate, state=state, proofs=proofs, evidence=evidence,
            document_sha=document_sha, page=number,
            linked_id=target_certificate.region_id, editorial_id=editorial,
            continuation_state="CONTINUES_NEXT_PAGE",
        )
        updates[number + 1][target_certificate.region_id] = _proven_update(
            target_certificate, state=state, proofs=proofs, evidence=evidence,
            document_sha=document_sha, page=number + 1,
            linked_id=terminal_certificate.region_id, editorial_id=editorial,
            continuation_state="CONTINUED_FROM_PREVIOUS",
            continuation_of=terminal_certificate.region_id,
            zone_type="note", note_number=terminal["note_number"],
        )


def certify_document(parsed, document_sha, *, native_pages):
    """V4 decisions are re-validated by the V5 positive identity contract."""
    parsed = _canonical_parsed(parsed)
    layouts = {page.page_number: page for page in parsed.pages}
    results = tuple(certify_v4(parsed, document_sha, native_pages=native_pages))
    by_page = {page.provenance.pdf_page: page for page in results}
    by_region = {
        (page.provenance.pdf_page, certificate.region_id): certificate
        for page in results for certificate in page.certificates
    }
    updates = {page.provenance.pdf_page: {} for page in results}
    seen = set()
    for page in results:
        number = page.provenance.pdf_page
        for certificate in page.certificates:
            if (not certificate.linked_region_ids or number in seen
                    or certificate.continuation_state == "CONTINUED_FROM_PREVIOUS"):
                continue
            target_id = certificate.linked_region_ids[0]
            target_page = by_page.get(number + 1)
            target = by_region.get((number + 1, target_id)) if target_page else None
            if target is None:
                updates[number][certificate.region_id] = _downgrade(
                    _ensure_v5(certificate), IDENTITY_UNRESOLVED, (),
                    ("MISSING_LINKED_REGION",))
                continue
            seen.add(number)
            assert target_page is not None
            terminal_unit = next(u for u in page.provenance.units
                                 if u.region_id == certificate.region_id)
            first_unit = next(u for u in target_page.provenance.units
                              if u.region_id == target.region_id)
            state, proofs, evidence = _identity_contract(
                page.provenance, layouts[number], native_pages.get(number), terminal_unit,
                target_page.provenance, layouts[number + 1], native_pages.get(number + 1),
                first_unit,
            )
            if state == IDENTITY_PROVEN:
                updates[number][certificate.region_id] = replace(
                    _ensure_v5(certificate), identity_state=state,
                    identity_proof=proofs, identity_evidence=evidence,
                )
                updates[number + 1][target.region_id] = replace(
                    _ensure_v5(target), identity_state=state,
                    identity_proof=proofs, identity_evidence=evidence,
                )
            else:
                updates[number][certificate.region_id] = _downgrade(
                    _ensure_v5(certificate), state, proofs, evidence,
                )
                updates[number + 1][target.region_id] = _downgrade(
                    _ensure_v5(target), state, proofs, evidence,
                )
    _source_candidates(parsed, results, updates, document_sha=document_sha,
                       native_pages=native_pages)
    return tuple(_upgrade_page(page, updates[page.provenance.pdf_page]) for page in results)


def certify_layout_page(parsed, page, document_sha, *, native_page=None):
    result = certify_v4_page(parsed, page, document_sha, native_page=native_page)
    return _upgrade_page(result, {})


def extract_pdf_region_certificates(path, *, pages=None):
    import pymupdf
    from pymupdf4llm.helpers.document_layout import parse_document

    sha = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    with pymupdf.open(path) as document:
        selected = sorted(pages) if pages is not None else list(range(1, len(document) + 1))
        if len(set(selected)) != len(selected) or any(
                number < 1 or number > len(document) for number in selected):
            raise ValueError("Unique physical page numbers in document range required")
        parsed = parse_document(document, pages=[number - 1 for number in selected], use_ocr=False)
        return certify_document(parsed, sha,
                                native_pages={number: document[number - 1]
                                              for number in selected})
