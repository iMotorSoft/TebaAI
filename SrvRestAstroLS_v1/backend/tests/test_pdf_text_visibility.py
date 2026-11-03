from __future__ import annotations

import pymupdf
import pytest

from modules.library.pdf_text_visibility import classify_text_run, standard_compositing, visible_text_runs


def rectangle(*, seqno=2, bbox=(0, 0, 100, 30), **kwargs):
    return dict(type='f', fill=(1.0, 1.0, 1.0), fill_opacity=1.0,
                level=0, layer='', seqno=seqno,
                items=[('re', pymupdf.Rect(bbox), 1)], **kwargs)


RUN = {'bbox': (10, 10, 80, 20), 'seqno': 1}
LOG = [('fill-path', (0, 0, 1, 1)), ('fill-text', (9, 9, 81, 21))]


def test_fully_covered_by_later_opaque_white_rectangle():
    assert classify_text_run(RUN, [rectangle()], LOG)['status'] == 'occluded'


@pytest.mark.parametrize('changes', [
    {'seqno': 0}, {'seqno': 1}, {'fill_opacity': 0.5},
    {'fill_opacity': 0.0}, {'fill': (0.9, 0.9, 0.9)},
    {'type': 's'}, {'level': 1}, {'level': None}, {'layer': 'optional'},
    {'items': [('l', (0, 0), (100, 30))]},
])
def test_no_suppression_without_sufficient_evidence(changes):
    drawing = rectangle()
    drawing.update(changes)
    assert classify_text_run(RUN, [drawing], LOG)['status'] == 'unproven'


def test_no_overlap():
    assert classify_text_run(RUN, [rectangle(bbox=(90, 0, 100, 30))], LOG)['status'] == 'unproven'


def test_partial_overlap_never_removes_entire_run():
    result = classify_text_run(RUN, [rectangle(bbox=(50, 0, 100, 30))], LOG)
    assert result['status'] == 'partial'
    assert result['overlays'][0]['area_ratio'] == pytest.approx(30 / 70)


@pytest.mark.parametrize('log', [[], [('fill-path', (0, 0, 1, 1)), ('fill-text', (9, 9, 200, 21))]])
def test_trace_coverage_alone_is_not_ink_coverage(log):
    assert classify_text_run(RUN, [rectangle()], log)['status'] == 'candidate'


def test_empty_run_is_not_suppressed():
    assert classify_text_run(dict(RUN, bbox=(10, 10, 10, 20)), [rectangle()], LOG)['status'] == 'unproven'


@pytest.mark.parametrize('overlay_first, opacity, partial, expected_hidden', [
    (False, 1, False, 1), (True, 1, False, 0),
    (False, 0.5, False, 0), (False, 1, True, 0),
])
def test_real_pdf_paint_order_and_visible_replacement(overlay_first, opacity, partial, expected_hidden):
    with pymupdf.open() as doc:
        page = doc.new_page()
        cover = pymupdf.Rect(10 if not partial else 60, 30, 120, 65)
        def overlay():
            page.draw_rect(cover, color=None, fill=(1, 1, 1), fill_opacity=opacity)
        if overlay_first:
            overlay()
        page.insert_text((20, 50), 'old 16:1')
        if not overlay_first:
            overlay()
        page.insert_text((20, 50), 'visible 37')
        # Round-trip prevents differences caused by unfinished page caches.
        with pymupdf.open(stream=doc.tobytes(), filetype='pdf') as reopened:
            page = reopened[0]
            original = page.get_texttrace()
            retained, evidence = visible_text_runs(page, compositing_verified=standard_compositing(reopened))
            assert sum(v['status'] == 'occluded' for v in evidence) == expected_hidden
            assert retained == [r for r, v in zip(original, evidence) if v['status'] != 'occluded']
            assert ''.join(chr(c[0]) for c in retained[-1]['chars']) == 'visible 37'


def test_retained_hebrew_combining_marks_numbers_and_punctuation_are_untouched():
    class Page:
        def get_drawings(self, **kwargs):
            assert kwargs == {'extended': True}
            return []
        def get_bboxlog(self):
            return LOG
        def get_texttrace(self):
            return [run]
    text = 'שָׁלוֹם (16:1), ABC 37'
    run = dict(RUN, chars=tuple((ord(c), i, (i, 10), (i, 10, i + 1, 20)) for i, c in enumerate(text)))
    retained, _ = visible_text_runs(Page())
    assert retained[0] is run
    assert ''.join(chr(c[0]) for c in retained[0]['chars']) == text


@pytest.mark.parametrize('key, value, expected', [
    ('BM', '/Normal', True), ('SMask', '/None', True),
    ('BM', '/Multiply', False), ('SMask', '7 0 R', False),
])
def test_compositing_guard(key, value, expected):
    with pymupdf.open() as doc:
        doc.new_page()
        xref = doc.get_new_xref()
        doc.update_object(xref, f'<< /Type /ExtGState /{key} {value} >>')
        assert standard_compositing(doc) is expected


def test_unverified_compositing_preserves_text_even_with_full_geometry():
    class Page:
        def get_drawings(self, **kwargs):
            return [rectangle()]
        def get_bboxlog(self):
            return LOG
        def get_texttrace(self):
            return [RUN]
    retained, evidence = visible_text_runs(Page())
    assert retained == [RUN]
    assert evidence[0]['status'] == 'candidate'
    assert evidence[0]['reason'] == 'compositing_not_verified'
