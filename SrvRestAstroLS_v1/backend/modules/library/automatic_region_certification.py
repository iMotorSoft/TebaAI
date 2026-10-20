"""Opt-in, service-free certification from the canonical extractor's live IR.

No caller-supplied positive certificates. This intentionally small supported
subset never interprets missing script evidence as RTL, or a page cut as the end
of a note. The worker does not import this module.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, replace
import hashlib
import json
import re
import unicodedata

from modules.library.region_markdown_provenance import (
    ProvenancePage, UnresolvedLayout, _bbox, _identity, _plain, map_layout_page,
)
from modules.library.region_quality import RegionState, aggregate

VERSION = "automatic-region-certification-v1"
_ZONES = {"text": "text", "footnote": "note", "page-header": "header",
          "page-footer": "footer", "section-header": "editorial_heading"}


def direction(lines):
    """All strong codepoints count; neutral/damaged-only text proves nothing."""
    strong = {unicodedata.bidirectional(c) for line in lines for c in _plain(line)
              if unicodedata.bidirectional(c) in {"L", "R", "AL"}}
    if "L" in strong and strong & {"R", "AL"}:
        return "MIXED"
    if strong & {"R", "AL"}:
        return "RTL"
    if strong == {"L"}:
        return "LTR"
    return "UNRESOLVED"


def _tokens(text):
    return re.findall(r"\w+|[^\w\s]", text, re.UNICODE)


def _decoration_only(source, markdown):
    # Deliberately refuse literal Markdown metacharacters rather than erase
    # potentially meaningful source punctuation in an equivalence comparison.
    if any(c in source for c in "*_`~>#\\"):
        return False
    plain = re.sub(r"(?m)^\s*(?:>\s*|#{1,6}\s+)", "", markdown)
    for decoration in ("**", "__", "~~", "*", "_"):
        plain = plain.replace(decoration, "")
    return _tokens(source) == _tokens(plain)


def _intersects(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


@dataclass(frozen=True)
class RegionCertificate:
    document_sha: str
    pdf_page: int
    region_id: str
    bbox: tuple
    zone_type: str
    direction: str
    source_block_ids: tuple
    source_line_ids: tuple
    markdown_ranges: tuple
    mapping_method: str
    provenance_status: str
    quality_status: str
    reason_codes: tuple
    note_number: int | None = None
    end_reason: str = "BOX_BOUNDARY"
    continuation_of: str | None = None
    certificate_version: str = VERSION

    def to_dict(self):
        # Round-trip also makes tuple keys / non-finite floats impossible to leak.
        return json.loads(json.dumps(asdict(self), allow_nan=False))


@dataclass(frozen=True)
class CertifiedPage:
    provenance: ProvenancePage
    certificates: tuple[RegionCertificate, ...]

    def to_dict(self):
        return {"document_sha": self.provenance.source_sha256,
                "pdf_page": self.provenance.pdf_page,
                "markdown": self.provenance.markdown,
                "page_aggregate": aggregate(tuple(RegionState(c.quality_status)
                                                   for c in self.certificates)).value,
                "certificates": [c.to_dict() for c in self.certificates]}


def native_evidence(native_page, lines):
    """Exact baseline/geometry lookup in independent PDF text trace, never search.

    Trace characters must occur once, be opaque painted ink, and have no later
    overlapping paint operation. Ambiguous/hidden native text cannot verify
    quality. Only horizontal LTR is supported by this proof in V1.
    """
    trace = native_page.get_texttrace()
    log = native_page.get_bboxlog()
    actual, visible = [], True
    for line in lines:
        chars = []
        baselines = {round(s["origin"][1], 3) for s in line["spans"] if "origin" in s}
        if not baselines:
            return "", False
        for run in trace:
            selected = [ch for ch in run["chars"]
                        if round(ch[2][1], 3) in baselines
                        and line["bbox"][0] - 0.01 <= ch[2][0] < line["bbox"][2]]
            if not selected:
                continue
            visible &= (run.get("opacity") == 1 and run.get("type") in {0, 1}
                        and tuple(run.get("dir", ())) == (1.0, 0.0))
            for ch in selected:
                # Any later drawing, image, or text crossing the glyph is
                # unresolved. No assumptions about white rectangles / overlays.
                visible &= not any(_intersects(ch[3], bbox) for _, bbox in log[run["seqno"] + 1:])
                chars.append((ch[2][0], ch[2][1], ch[0]))
        if not chars or len({(x, y) for x, y, _ in chars}) != len(chars):
            return "", False
        actual.append("".join(chr(cp) for _, _, cp in sorted(chars)))
    return "\n".join(actual), bool(visible)


def certify_layout_page(parsed, page, document_sha, *, native_page=None):
    """Discover and serialize together; no geometry/direction override API.

    Notes require the extractor's explicit footnote labels, pure strong LTR
    script throughout the bottom zone, and the existing adapter's disjoint
    column/ownership checks. Unlabelled continuations are NOT inferred.
    Individual non-note boxes remain independent even if the note flow fails.
    """
    boxes = deepcopy(page.boxes)
    # Ignore mutable input container ordering; source identity breaks exact ties.
    for b in boxes:
        b.textlines.sort(key=lambda l: (l["bbox"][1], l["bbox"][0], _identity(l)))
    boxes.sort(key=lambda b: (b.y0, b.x0, b.y1, b.x1, b.boxclass))
    anchors = [b for b in boxes if b.boxclass == "footnote" and b.textlines]
    top = min(_bbox(b.textlines)[1] for b in anchors) if anchors else None
    notes = [b for b in boxes if b.textlines and top is not None and _bbox(b.textlines)[1] >= top - 1]
    note_ids = {id(b) for b in notes}
    note_direction = direction([l for b in notes for l in b.textlines])
    pieces, unresolved_boxes = [], []
    if notes:
        try:
            if note_direction != "LTR":
                raise UnresolvedLayout("Note direction not supported")
            if any(b.textlines and _bbox(b.textlines)[1] < top - 1 < _bbox(b.textlines)[3]
                   for b in boxes if id(b) not in note_ids):
                raise UnresolvedLayout("Box crosses note zone")
            pieces.append(map_layout_page(parsed, replace(page, boxes=notes), document_sha,
                                          note_direction="ltr"))
        except UnresolvedLayout:
            unresolved_boxes.extend(notes)
    for b in boxes:
        if id(b) in note_ids:
            continue
        try:
            pieces.append(map_layout_page(parsed, replace(page, boxes=[b]), document_sha,
                                          note_direction="ltr"))
        except UnresolvedLayout:
            unresolved_boxes.append(b)
    # Do not drop unsupported boxes. Serialize the original IR separately, with
    # unresolved ownership; retain stable geometry identity and source IDs.
    from modules.library.region_markdown_provenance import Ownership, SourcePart
    for b in unresolved_boxes:
        lines = b.textlines
        if not lines:
            lines = []
        identity = [VERSION, document_sha, page.page_number, b.boxclass,
                    [b.x0, b.y0, b.x1, b.y1], [_identity(l) for l in lines]]
        rid = "region-" + hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:24]
        # Unsupported layout may not have textual lines (e.g. picture).
        md = replace(parsed, pages=[replace(page, boxes=[deepcopy(b)])]).to_markdown()
        source = "\n".join(_plain(l) for l in lines)
        parts = tuple(SourcePart(tuple(l["bbox"]), _identity(l)[0], i, _plain(l), None)
                      for i, l in enumerate(lines))
        u = Ownership(rid, page.page_number, (b.x0, b.y0, b.x1, b.y1), parts,
                      b.boxclass, None, "UNRESOLVED", 0, len(md), 0, len(source),
                      status="UNRESOLVED", transformation_status="UNRESOLVED")
        pieces.append(ProvenancePage(document_sha, page.page_number, md, source, (u,)))
    pieces.sort(key=lambda p: (min((u.source_bbox[1] for u in p.units), default=0),
                               min((u.source_bbox[0] for u in p.units), default=0)))
    md, canonical, units = "", "", []
    for piece in pieces:
        units.extend(replace(u, markdown_start=u.markdown_start + len(md),
                             markdown_end=u.markdown_end + len(md),
                             canonical_start=u.canonical_start + len(canonical),
                             canonical_end=u.canonical_end + len(canonical)) for u in piece.units)
        md += piece.markdown
        canonical += piece.canonical_text
    mapped = ProvenancePage(document_sha, page.page_number, md, canonical, tuple(units))
    all_lines = [l for b in boxes for l in b.textlines]
    identities = [_identity(l) for l in all_lines]
    certificates = []
    for u in mapped.units:
        identities_owned = {(p.source_line_ids, p.bbox) for p in u.parts}
        lines = [l for l in all_lines if _identity(l) in identities_owned]
        d = direction(lines)
        zone = _ZONES.get(u.role, "unknown")
        # Reuse only the exact historical heading vocabulary, not its fuzzy
        # mojibake/uppercase heuristics. A damaged suffix is retained in output;
        # this is zone recognition, never a text correction.
        from modules.library.editorial_evidence_v2 import classify_editorial_block
        label = "\n".join(p.source_text for p in u.parts).rstrip("\ufffd").strip()
        if label in {"Notas y Fuentes", "Notas y Fuentes:", "Notes and Sources"}:
            if classify_editorial_block({"content": label}).block_role_method == "notes_heading_text":
                zone = "notes_heading"
        reasons = []
        if zone == "unknown" or u.status != "MAPPED":
            reasons.append("LAYOUT_UNSUPPORTED")
        # The generic extractor label 'text' is NOT an editorial body-zone
        # certificate: unlabelled note continuations also carry this label.
        if zone == "text":
            reasons.append("ZONE_UNRESOLVED")
        numbers = [other.note_number for other in mapped.units if other.note_number is not None]
        if u.note_number is not None and numbers != sorted(set(numbers)):
            reasons.append("UNSAFE_COLUMN_ORDER")
        if d not in {"LTR", "RTL"}:
            reasons.append("DIRECTION_UNRESOLVED")
        if any(identities.count(_identity(l)) != 1 for l in lines) or len(lines) != len(u.parts):
            reasons.append("PROVENANCE_AMBIGUOUS")
        # Non-note boxes that overlap another box cannot assert column/body
        # ownership. Notes have already passed dedicated column checks.
        if u.note_number is None and any(
            _intersects(u.source_bbox, _bbox(b.textlines)) and
            any(_identity(l) not in identities_owned for l in b.textlines)
            for b in boxes if b.textlines):
            reasons.append("PROVENANCE_AMBIGUOUS")
        certified = not reasons
        provenance_status = "CERTIFIED" if certified else "UNRESOLVED"
        quality = RegionState.UNRESOLVED
        source = "\n".join(p.source_text for p in u.parts)
        fragment = md[u.markdown_start:u.markdown_end]
        native, visible = native_evidence(native_page, lines) if native_page is not None else ("", False)
        if "\ufffd" in source:
            reasons.append("INVALID_UNICODE_REPLACEMENT")
            # A differential proves extractor substitution, not a visible PDF
            # source defect. Otherwise attribution stays unresolved.
            if certified and native and "\ufffd" not in native and visible:
                quality = RegionState.PLATFORM_EXTRACTION_ERROR
                reasons.append("NATIVE_TO_LAYOUT_REPLACEMENT")
        elif (certified and d == "LTR" and zone == "note"
              and u.transformation_status == "ALLOWLIST_ONLY"
              and visible and _tokens(native) == _tokens(source)
              and _decoration_only(source, fragment)
              and not any(unicodedata.category(c) == "Cc" and c not in "\n\r\t" for c in source)):
            quality = RegionState.ACCEPTED
            reasons.append("NATIVE_VISIBLE_TEXT_ORDER_EQUIVALENT")
        else:
            reasons.append("QUALITY_EVIDENCE_INSUFFICIENT")
        blocks = tuple(sorted({key[0] for p in u.parts for key in p.source_line_ids}))
        line_ids = tuple(dict.fromkeys(key for p in u.parts for key in p.source_line_ids))
        certificates.append(RegionCertificate(document_sha, page.page_number, u.region_id,
            u.source_bbox, zone, d, blocks, line_ids, ((u.markdown_start, u.markdown_end),),
            u.mapping_method, provenance_status, quality.value, tuple(dict.fromkeys(reasons)),
            u.note_number, u.end_reason))
    return CertifiedPage(mapped, tuple(certificates))


def extract_pdf_region_certificates(path, *, pages=None):
    """Live PDF → canonical layout → lineage + JSON-ready certificates.

    pages uses physical one-based numbers. No caller-provided positive evidence,
    OCR, font repair, DB, embeddings, worker or publication operations.
    """
    from pathlib import Path
    import pymupdf
    from pymupdf4llm.helpers.document_layout import parse_document

    sha = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    with pymupdf.open(path) as document:
        selected = list(pages) if pages is not None else list(range(1, len(document) + 1))
        if len(set(selected)) != len(selected) or any(n < 1 or n > len(document) for n in selected):
            raise ValueError("Unique physical page numbers in document range required")
        parsed = parse_document(document, pages=[n - 1 for n in sorted(selected)], use_ocr=False)
        return tuple(certify_layout_page(parsed, page, sha, native_page=document[page.page_number - 1])
                     for page in parsed.pages)
