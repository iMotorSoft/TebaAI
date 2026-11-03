"""Conservative PDF paint-order visibility candidate (not ingestion-integrated).

Trace bounds are font-metric bounds, not necessarily glyph ink bounds. A later
opaque rectangle covering a trace is a *candidate*. Suppression additionally
requires containment of the entire text paint operation's ink bbox from
get_bboxlog(). Shared operations can therefore remain unresolved. This is
intentional: no thresholds, partial-run removal, redaction or string rewriting.
"""
from __future__ import annotations

import pymupdf


def classify_text_run(run: dict, drawings: list[dict], bboxlog: list) -> dict:
    bounds = pymupdf.Rect(run['bbox'])
    result = {'status': 'unproven', 'overlays': []}
    if bounds.is_empty or bounds.is_infinite:
        return result
    seqno = run.get('seqno')
    if not isinstance(seqno, int) or seqno < 0:
        return result
    ink = None
    if seqno < len(bboxlog) and bboxlog[seqno][0] in ('fill-text', 'stroke-text'):
        ink = pymupdf.Rect(bboxlog[seqno][1])
        if ink.is_empty or ink.is_infinite:
            ink = None
    for drawing in drawings:
        # extended=True exposes clip/group nesting; missing metadata is not
        # proof of an unclipped, non-transparent paint operation.
        if (drawing.get('type') not in ('f', 'fs')
            or drawing.get('fill') != (1.0, 1.0, 1.0)
            or drawing.get('fill_opacity') != 1.0
            or drawing.get('level') != 0
            or drawing.get('layer', '')
            or not isinstance(drawing.get('seqno'), int)
            or drawing['seqno'] <= seqno):
            continue
        items = drawing.get('items', [])
        if len(items) != 1 or items[0][0] != 're':
            continue
        # Use the actual rectangle path, never a general path's envelope.
        rectangle = pymupdf.Rect(items[0][1])
        if rectangle.is_empty or rectangle.is_infinite:
            continue
        intersection = bounds & rectangle
        ratio = intersection.get_area() / bounds.get_area()
        if ratio == 0:
            continue
        full = rectangle.contains(bounds)
        ink_full = ink is not None and rectangle.contains(ink)
        result['overlays'].append({
            'seqno': drawing['seqno'], 'bbox': list(rectangle),
            'fill': drawing['fill'], 'opacity': drawing['fill_opacity'],
            'overlap': 'full' if full else 'partial', 'area_ratio': ratio,
            'paint_ink_contained': ink_full,
        })
        if full and ink_full:
            result['status'] = 'occluded'
        elif full and result['status'] != 'occluded':
            result['status'] = 'candidate'
        elif result['status'] == 'unproven':
            result['status'] = 'partial'
    return result


def standard_compositing(document) -> bool:
    """Fail closed for masks/non-Normal blending anywhere in this candidate.

    Drawing opacity alone cannot prove coverage: white with Multiply blending
    leaves earlier ink visible. This deliberately broad guard is not a PDF
    graphics-state interpreter and may retain more text than necessary.
    """
    for xref in range(1, document.xref_length()):
        for key, allowed in (('BM', {'null', '/Normal'}), ('SMask', {'null', '/None'})):
            if document.xref_get_key(xref, key)[1] not in allowed:
                return False
    return True


def visible_text_runs(page, *, compositing_verified: bool = False) -> tuple[list[dict], list[dict]]:
    """Filter only proven occlusions; preserve retained run objects verbatim.

    This is an isolated trace fixture API, NOT canonical Markdown. No Unicode,
    whitespace, combining-mark or ordering transformations are performed.
    The caller must verify standard compositing before enabling suppression.
    """
    drawings = page.get_drawings(extended=True)
    bboxlog = page.get_bboxlog()
    retained, evidence = [], []
    for index, run in enumerate(page.get_texttrace()):
        verdict = classify_text_run(run, drawings, bboxlog)
        if verdict['status'] == 'occluded' and not compositing_verified:
            verdict['status'] = 'candidate'
            verdict['reason'] = 'compositing_not_verified'
        evidence.append(dict(verdict, run_index=index, seqno=run['seqno'], bbox=list(run['bbox'])))
        if verdict['status'] != 'occluded':
            retained.append(run)
    return retained, evidence
