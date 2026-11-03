"""Additional regressions without changing the frozen visibility candidate."""
import pymupdf
import pytest
from modules.library.pdf_text_visibility import classify_text_run

RUN = {'bbox': (10, 10, 80, 20), 'seqno': 1}
LOG = [('fill-path', (0, 0, 1, 1)), ('fill-text', (9, 9, 81, 21))]


def overlay(seqno=2, rect=(0, 0, 100, 30)):
    return dict(type='f', fill=(1., 1., 1.), fill_opacity=1., level=0,
                seqno=seqno, items=[('re', pymupdf.Rect(rect), 1)])


def test_table_background_before_text_kept():
    assert classify_text_run(RUN, [overlay(seqno=0)], LOG)['status'] == 'unproven'


@pytest.mark.parametrize('seqno', [None, 'unknown', -1])
def test_uncertain_text_paint_order_kept(seqno):
    assert classify_text_run(dict(RUN, seqno=seqno), [overlay()], LOG)['status'] == 'unproven'


def test_unknown_overlay_order_kept():
    assert classify_text_run(RUN, [overlay(seqno=None)], LOG)['status'] == 'unproven'


def test_multiple_partial_overlays_not_unioned_to_force_suppression():
    result = classify_text_run(RUN, [overlay(rect=(0,0,50,30)), overlay(3, (50,0,100,30))], LOG)
    assert result['status'] == 'partial'


def test_multiple_overlays_one_independently_proven_full():
    result = classify_text_run(RUN, [overlay(rect=(0,0,50,30)), overlay(3)], LOG)
    assert result['status'] == 'occluded'
