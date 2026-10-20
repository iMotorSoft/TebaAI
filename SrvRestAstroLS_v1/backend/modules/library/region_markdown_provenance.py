"""Offline forward-lineage adapter for PyMuPDF4LLM's layout IR (not worker).

No PDF repair, OCR, reverse text matching, or quality inference. The supported
editorial layout is a bottom note zone with disjoint columns and a declared
reading direction. Unsupported layouts fail explicitly rather than drop text.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
import hashlib
import json
import math

from modules.library.editorial_evidence_v2 import detect_footnote_number

VERSION = "region-markdown-provenance-v1"


class UnresolvedLayout(ValueError):
    """No defensible ownership/order can be emitted for this layout."""


def _bbox(lines):
    boxes = [tuple(line["bbox"]) for line in lines]
    return (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))


def _key(line):
    # Existing extractor block/line identity, not mutable container position.
    return tuple(dict.fromkeys((s["block"], s["line"]) for s in line["spans"]))


def _identity(line):
    # Layout can split one native line into multiple geometric fragments.
    return (_key(line), tuple(line["bbox"]))


def _plain(line):
    return "".join(s["text"] for s in line["spans"]).strip()


@dataclass(frozen=True)
class SourcePart:
    bbox: tuple[float, float, float, float]
    source_line_ids: tuple[tuple[int, int], ...]
    source_sequence: int
    source_text: str
    column: int | None


@dataclass(frozen=True)
class Ownership:
    region_id: str
    pdf_page: int
    source_bbox: tuple[float, float, float, float]
    parts: tuple[SourcePart, ...]
    role: str
    note_number: int | None
    end_reason: str
    markdown_start: int
    markdown_end: int
    canonical_start: int
    canonical_end: int
    mapping_method: str = "FORWARD_IR_SERIALIZATION"
    status: str = "MAPPED"
    transformations: tuple[str, ...] = ("MARKDOWN_DECORATION",)
    transformation_status: str = "ALLOWLIST_ONLY"
    transformation_warning: str | None = None
    continuation_of: str | None = None


@dataclass(frozen=True)
class ProvenancePage:
    source_sha256: str
    pdf_page: int
    markdown: str
    canonical_text: str
    units: tuple[Ownership, ...]

    def spans_for_region(self, region_id: str):
        return tuple((u.markdown_start, u.markdown_end) for u in self.units
                     if u.region_id == region_id)

    def owners(self, start: int, end: int):
        if not 0 <= start < end <= len(self.markdown):
            raise ValueError("Invalid half-open Markdown range")
        return tuple(u for u in self.units
                     if u.markdown_start < end and start < u.markdown_end)

    def exclude(self, region_ids):
        """Exact original slices; offsets remain in immutable pre-exclusion output."""
        unknown = set(region_ids) - {u.region_id for u in self.units}
        if unknown:
            raise ValueError("Untracked quarantine region")
        return tuple((u.region_id, self.markdown[u.markdown_start:u.markdown_end])
                     for u in self.units if u.region_id not in region_ids)


def classify_owned_unit(page: ProvenancePage, region_id: str, *, evidence_refs: tuple[str, ...],
                        visual_good: bool | None, text_verified: bool,
                        order_verified: bool, structure_verified: bool):
    """Thin offline bridge to the EXISTING quality contract, after ownership.

    Positive certificates are external evidence, not inferred from clean text.
    Unknown transformations cannot become accepted even with caller flags.
    """
    from modules.library.region_quality import RegionCandidate, classify_region

    unit = next((u for u in page.units if u.region_id == region_id), None)
    if unit is None:
        raise ValueError("Quality requires a tracked ownership unit")
    safe = unit.status == "MAPPED" and unit.transformation_status == "ALLOWLIST_ONLY"
    return classify_region(RegionCandidate(
        page.source_sha256, page.pdf_page, region_id,
        page.markdown[unit.markdown_start:unit.markdown_end], "pymupdf4llm", evidence_refs,
        bbox=unit.source_bbox, visual_good=visual_good,
        text_verified=text_verified and safe, order_verified=order_verified,
        structure_verified=structure_verified,
        diagnostics=() if safe else (unit.transformation_warning or "unresolved_provenance",),
    ))


def map_layout_page(parsed, page, source_sha256: str, *, note_direction: str,
                    note_zone_bbox: tuple[float, float, float, float] | None = None,
                    continued_from: ProvenancePage | None = None,
                    note_start=detect_footnote_number,
                    leading_note: int | None = None) -> ProvenancePage:
    """Emit Markdown and ownership together, using the installed canonical engine.

    Non-note box order remains extractor-authoritative. Within a bottom note
    zone, geometry is authoritative (columns then vertical lines). Direction is
    an explicit layout contract, never guessed from a filename or note number.
    Terminal bounds are PAGE_BOUNDARY, NOT a claim that a continued note ends.
    The canonical-text representation is source spans joined by line breaks;
    its offsets are deliberately distinct from decorated Markdown offsets.
    """
    from pymupdf4llm.helpers.document_layout import LayoutBox

    if note_direction not in {"ltr", "rtl"}:
        raise UnresolvedLayout("Explicit note column direction required")
    if len(source_sha256) != 64 or any(c not in "0123456789abcdef" for c in source_sha256):
        raise ValueError("Source SHA-256 required")
    boxes = page.boxes
    if any(not b.textlines or b.boxclass in {"table", "picture", "formula", "list-item", "table-fallback"}
           for b in boxes):
        raise UnresolvedLayout("Non-text or list layout needs a dedicated forward adapter")
    lines = [line for b in boxes for line in b.textlines]
    for line in lines:
        x0, y0, x1, y1 = line["bbox"]
        if not all(math.isfinite(v) for v in (x0, y0, x1, y1)) or x0 >= x1 or y0 >= y1:
            raise UnresolvedLayout("Invalid source line geometry")
    keys = [_identity(line) for line in lines]
    if any(not k[0] for k in keys) or len(set(keys)) != len(keys):
        raise UnresolvedLayout("Missing or duplicated source line identity")
    # Stable sequence derives from existing extraction IDs, not input ordering.
    sequence = {k: i for i, k in enumerate(sorted(keys))}
    previous = None
    if continued_from is not None and leading_note is not None:
        raise UnresolvedLayout("Continuation and page-local leading note are exclusive")
    if continued_from is not None:
        prior_notes = [u for u in continued_from.units if u.note_number is not None]
        if (continued_from.source_sha256 != source_sha256
                or continued_from.pdf_page + 1 != page.page_number or not prior_notes
                or prior_notes[-1].end_reason != "PAGE_BOUNDARY"):
            raise UnresolvedLayout("Continuation needs an adjacent, same-source open note")
        previous = prior_notes[-1]
    if leading_note is not None and leading_note < 1:
        raise UnresolvedLayout("Invalid page-local leading note number")
    anchors = [b for b in boxes if b.boxclass == "footnote"]
    note_boxes = []
    if anchors or note_zone_bbox is not None:
        zone_top = (note_zone_bbox[1] if note_zone_bbox is not None
                    else min(_bbox(b.textlines)[1] for b in anchors))
        note_boxes = [b for b in boxes if _bbox(b.textlines)[1] >= zone_top - 1]
        if note_zone_bbox is not None:
            x0, y0, x1, y1 = note_zone_bbox
            if x0 >= x1 or y0 >= y1 or not note_boxes:
                raise UnresolvedLayout("Invalid or empty certified note zone")
            if any(not (x0 <= _bbox(b.textlines)[0] and _bbox(b.textlines)[2] <= x1
                        and _bbox(b.textlines)[3] <= y1) for b in note_boxes):
                raise UnresolvedLayout("Note-zone certificate does not contain its source boxes")
        if any(_bbox(b.textlines)[1] < zone_top - 1 < _bbox(b.textlines)[3]
               for b in boxes if b not in note_boxes):
            raise UnresolvedLayout("A source box crosses the note zone")
    if previous is not None and not note_boxes:
        raise UnresolvedLayout("Continuation requires a geometric note-zone certificate")
    note_ids = {id(b) for b in note_boxes}
    groups = []
    # Keep full converter boxes, including damaged text, with independent IDs.
    for b in boxes:
        if id(b) not in note_ids:
            groups.append((b.boxclass, None, [(line, None) for line in b.textlines], "BOX_BOUNDARY"))
    if note_boxes:
        note_lines = [line for b in note_boxes for line in b.textlines]
        anchor_sizes = {round(s["size"], 3) for b in (anchors or note_boxes[:1])
                        for l in b.textlines for s in l["spans"]}
        nonfooter_blocks = {s["block"] for b in note_boxes if b.boxclass != "page-footer"
                            for l in b.textlines for s in l["spans"]}
        for b in note_boxes:
            if b.boxclass not in {"footnote", "text", "page-footer"}:
                raise UnresolvedLayout("Non-note editorial zone intersects bottom note flow")
            for line in b.textlines:
                if any(round(s["size"], 3) not in anchor_sizes for s in line["spans"]):
                    raise UnresolvedLayout("Note zone contains incompatible text typography")
                if b.boxclass == "page-footer" and any(s["block"] not in nonfooter_blocks for s in line["spans"]):
                    raise UnresolvedLayout("Footer has no native-block lineage into note flow")
        # Connected x-projections define columns; short last lines remain owned.
        columns = []
        for line in sorted(note_lines, key=lambda l: tuple(l["bbox"])):
            x0, _, x1, _ = line["bbox"]
            hits = [c for c in columns if x0 < c[1] and c[0] < x1]
            if len(hits) > 1:
                raise UnresolvedLayout("Line bridges editorial columns")
            if hits:
                c = hits[0]
                c[0], c[1] = min(c[0], x0), max(c[1], x1)
                c[2].append(line)
            else:
                columns.append([x0, x1, [line]])
        columns.sort(key=lambda c: c[0], reverse=note_direction == "rtl")
        current = []
        number = previous.note_number if previous else leading_note
        seen_numbers = {number} if number is not None else set()
        for column, (_, _, col_lines) in enumerate(columns):
            ordered = sorted(col_lines, key=lambda l: (l["bbox"][1], l["bbox"][0], _key(l)))
            for upper_line, lower_line in zip(ordered, ordered[1:]):
                if upper_line["bbox"][3] > lower_line["bbox"][1] + 1:
                    raise UnresolvedLayout("Overlapping note lines have ambiguous order")
            for line in ordered:
                source_text = _plain(line)
                start = note_start(source_text)
                if start is None and source_text.split() and source_text.split()[0].rstrip(".)").isdigit():
                    raise UnresolvedLayout("Numeric note start outside historical recognizer contract")
                if start is not None:
                    if start in seen_numbers:
                        raise UnresolvedLayout("Repeated note identity in editorial zone")
                    seen_numbers.add(start)
                    if current:
                        groups.append(("footnote", number, current, "NEXT_NOTE_IN_COLUMN_FLOW"))
                    current, number = [], start
                if number is None:
                    raise UnresolvedLayout("Leading continuation has no page-local owner")
                current.append((line, column))
        if current:
            groups.append(("footnote", number, current, "PAGE_BOUNDARY"))
    md, canonical, units = "", "", []
    for role, number, members, end_reason in groups:
        unit_lines = [line for line, _ in members]
        bbox = _bbox(unit_lines)
        identity = [VERSION, source_sha256, page.page_number, [_identity(l) for l in unit_lines], bbox]
        region_id = "region-" + hashlib.sha256(json.dumps(identity, separators=(",", ":")).encode()).hexdigest()[:24]
        parts = tuple(SourcePart(tuple(line["bbox"]), _key(line), sequence[_identity(line)],
                                 _plain(line), column) for line, column in members)
        # Reuse PyMuPDF4LLM's own serializer on a copied IR unit: it mutates spans.
        box = LayoutBox(*bbox, boxclass=role, textlines=deepcopy(unit_lines))
        one_page = replace(page, boxes=[box])
        fragment = replace(parsed, pages=[one_page]).to_markdown()
        plain = "\n".join(p.source_text for p in parts) + "\n\n"
        unit = Ownership(region_id, page.page_number, bbox, parts, role, number,
                         end_reason, len(md), len(md) + len(fragment),
                         len(canonical), len(canonical) + len(plain),
                         transformations=("MARKDOWN_DECORATION", "EDITORIAL_GROUPING"))
        # The historical serializer may delete a line-end hyphen. Ownership
        # still travels forward, but that is NOT an approved safe transform.
        # Preserve the candidate for diagnosis; never certify it for acceptance.
        if any(p.source_text.endswith("-") for p in parts[:-1]):
            unit = replace(unit, transformation_status="UNRESOLVED",
                           transformation_warning="serializer_line_end_hyphenation_requires_review")
        if previous is not None and number == previous.note_number:
            unit = replace(unit, continuation_of=previous.region_id)
        units.append(unit)
        md += fragment
        canonical += plain
    return ProvenancePage(source_sha256, page.page_number, md, canonical, tuple(units))
