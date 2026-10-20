"""V4 generic body frame, text-class note zone, permutation invariance and continuation."""
from copy import deepcopy
import random

import pytest

from modules.library.automatic_region_certification_v4 import (
    certify_document, certify_layout_page,
)
from test_automatic_region_certification import PaintedSource
from test_region_markdown_provenance import SHA, box, synthetic, synthetic_line


def supported(*, continuation=False, note='7 First note', following='8 Next note'):
    caption = synthetic_line(0, 0, 110, 97, "Panel caption")
    caption['spans'][0]['size'] = 5
    body = synthetic_line(1, 0, 10, 160, "Ordinary main text")
    body['bbox'][2] = 290
    body['spans'][0]['size'] = 10
    second = synthetic_line(1, 1, 10, 175, "Second body line")
    second['bbox'][2] = 290
    second['spans'][0]['size'] = 10
    separator = synthetic_line(2, 0, 110, 297, "Notas y Fuentes")
    first = synthetic_line(3, 0, 10, 340, "continued text" if continuation else note)
    next_line = synthetic_line(3, 1, 10, 360, following)
    parsed, page = synthetic(box('text', caption), box('text', body, second),
                             box('section-header', separator),
                             box('footnote', first), box('footnote', next_line))
    native = PaintedSource([caption, body, second, separator, first, next_line])
    return parsed, page, native


def test_generic_body_is_certified_by_caption_band_without_rules():
    parsed, page, native = supported()
    result = certify_layout_page(parsed, page, SHA, native_page=native)
    body = next(c for c in result.certificates if c.zone_type == 'MAIN_BODY')
    assert body.provenance_status == 'CERTIFIED'
    assert body.quality_status == 'ACCEPTED'
    assert all(p.passed for p in body.body_proof)


def test_body_without_visible_native_trace_certifies_but_never_accepts():
    parsed, page, _ = supported()
    result = certify_layout_page(parsed, page, SHA)
    body = next(c for c in result.certificates if c.zone_type == 'MAIN_BODY')
    assert body.provenance_status == 'CERTIFIED'
    assert body.quality_status == 'UNRESOLVED'


def test_three_digit_note_start_is_mapped_and_certified():
    parsed, page, native = supported(note='123 Long note', following='124 Next note')
    result = certify_layout_page(parsed, page, SHA, native_page=native)
    notes = [c for c in result.certificates if c.zone_type == 'note']
    assert [c.note_number for c in notes] == [123, 124]
    assert notes[0].provenance_status == 'CERTIFIED'


def test_text_class_note_zone_is_mapped_by_separator_not_extractor_class():
    parsed, page, native = supported()
    page.boxes[-2].boxclass = 'text'
    page.boxes[-1].boxclass = 'text'
    result = certify_layout_page(parsed, page, SHA, native_page=native)
    notes = [c for c in result.certificates if c.zone_type == 'note']
    assert [c.note_number for c in notes] == [7, 8]
    assert notes[0].provenance_status == 'CERTIFIED'


def document():
    parsed, page, native = supported()
    _, following, next_native = supported(continuation=True)
    following.page_number = 2
    following.boxes[-1].textlines[0]['spans'][0]['text'] = '9 Following note'
    next_native = PaintedSource([l for b in following.boxes for l in b.textlines])
    parsed.pages = [page, following]
    return parsed, {1: native, 2: next_native}


def test_cross_page_continuation_links_without_merging_page_text():
    parsed, natives = document()
    result = certify_document(parsed, SHA, native_pages=natives)
    first = next(c for c in result[0].certificates if c.note_number == 8)
    second = next(c for c in result[1].certificates if c.continuation_of)
    assert first.editorial_unit_id == second.editorial_unit_id
    assert first.continuation_state == 'CONTINUES_NEXT_PAGE'
    assert second.continuation_state == 'CONTINUED_FROM_PREVIOUS'
    assert first.linked_region_ids == (second.region_id,)
    assert second.linked_region_ids == (first.region_id,)
    assert first.provenance_status == second.provenance_status == 'CERTIFIED'
    assert result[0].provenance.pdf_page == 1 and result[1].provenance.pdf_page == 2


def test_permutation_of_pages_boxes_and_lines_is_invariant():
    parsed, natives = document()
    baseline = certify_document(parsed, SHA, native_pages=natives)
    shuffled = deepcopy(parsed)
    rng = random.Random(321)
    rng.shuffle(shuffled.pages)
    for page in shuffled.pages:
        rng.shuffle(page.boxes)
        for b in page.boxes:
            if b.textlines:
                rng.shuffle(b.textlines)
    assert certify_document(shuffled, SHA, native_pages=natives) == baseline


def test_duplicate_pages_are_rejected():
    parsed, natives = document()
    parsed.pages.append(parsed.pages[0])
    with pytest.raises(ValueError, match='Duplicate'):
        certify_document(parsed, SHA, native_pages=natives)


@pytest.mark.parametrize('mutation', ['no_caption', 'caption_not_centered',
                                      'caption_not_smaller', 'single_body_line'])
def test_generic_body_negatives_fail_closed(mutation):
    parsed, page, native = supported()
    body_box = page.boxes[1]
    if mutation == 'no_caption':
        page.boxes[0].textlines[0]['spans'][0]['text'] = 'Notas y Fuentes'
    elif mutation == 'caption_not_centered':
        page.boxes[0].textlines[0]['bbox'][0] += 30
        page.boxes[0].textlines[0]['bbox'][2] += 30
    elif mutation == 'caption_not_smaller':
        page.boxes[0].textlines[0]['spans'][0]['size'] = 12
    elif mutation == 'single_body_line':
        body_box.textlines = body_box.textlines[:1]
    result = certify_layout_page(parsed, page, SHA, native_page=native)
    assert not any(c.zone_type == 'MAIN_BODY' and c.provenance_status == 'CERTIFIED'
                   for c in result.certificates)
