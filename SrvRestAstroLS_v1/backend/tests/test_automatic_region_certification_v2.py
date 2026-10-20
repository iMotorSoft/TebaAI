"""V2 removal-of-proof regressions; all quality requires full provenance."""
from copy import deepcopy
from dataclasses import asdict
import random
import json
from pathlib import Path

import pytest

from modules.library.automatic_region_certification_v2 import certify_layout_page, VERSION
from test_automatic_region_certification import PaintedSource
from test_region_markdown_provenance import SHA, box, real_layout, synthetic, synthetic_line


def supported():
    heading = synthetic_line(0, 0, 10, 170, 'Notas y Fuentes')
    first = synthetic_line(1, 0, 10, 200, '7 A short note')
    second = synthetic_line(2, 0, 10, 230, '8 Another note')
    parsed, page = synthetic(box('section-header', heading), box('footnote', first), box('footnote', second))
    return parsed, page, PaintedSource([heading, first, second])


def test_complete_simple_note_is_useful_but_terminal_note_is_not_complete():
    parsed, page, native = supported()
    result = certify_layout_page(parsed, page, SHA, native_page=native)
    first, last = [c for c in result.certificates if c.note_number]
    assert first.provenance_status == 'CERTIFIED'
    assert first.quality_status == 'ACCEPTED'
    assert all(p.passed for p in first.proofs)
    assert first.continuation_status == 'COMPLETE'
    assert last.provenance_status == last.quality_status == 'UNRESOLVED'
    assert last.local_boundary == 'KNOWN'
    assert last.continuation_status == 'UNRESOLVED_CONTINUATION'
    assert all(c.certificate_version == VERSION for c in result.certificates)
    assert result.to_dict()['certificates'][1]['proofs']


@pytest.mark.parametrize('remove', ['separator', 'anchor', 'direction', 'boundary', 'overlap', 'column', 'layout', 'native'])
def test_missing_required_proof_fails_closed(remove):
    parsed, page, native = supported()
    if remove == 'separator':
        page.boxes[0].textlines[0]['spans'][0]['text'] = 'An arbitrary heading'
    elif remove == 'anchor':
        for b in page.boxes[1:]:
            b.boxclass = 'text'
    elif remove == 'direction':
        for t in native.trace:
            t['dir'] = (-1., 0.)
    elif remove == 'boundary':
        page.boxes.pop()
    elif remove == 'overlap':
        page.boxes.append(deepcopy(page.boxes[1]))
    elif remove == 'column':
        page.boxes[-1].textlines[0]['spans'][0]['text'] = '6 Reversed marker'
    elif remove == 'layout':
        for b in page.boxes[1:]:
            b.boxclass = 'list-item'
    elif remove == 'native':
        native = None
    result = certify_layout_page(parsed, page, SHA, native_page=native)
    assert all(c.provenance_status == c.quality_status == 'UNRESOLVED' for c in result.certificates)


@pytest.mark.parametrize('label', ['page-footer', 'section-header', 'page-header', 'text'])
def test_extractor_labels_never_prove_editorial_zone(label):
    line = synthetic_line(0, 0, 10, 200, 'A genuine note continuation')
    parsed, page = synthetic(box(label, line))
    c, = certify_layout_page(parsed, page, SHA, native_page=PaintedSource([line])).certificates
    assert c.provenance_status == c.quality_status == 'UNRESOLVED'
    assert 'ZONE_AMBIGUOUS' in c.reason_codes


@pytest.mark.parametrize('page_number', [55,56,57,167,168])
def test_real_development_ir_determinism_and_permutations(page_number):
    parsed, page = real_layout(page_number)
    before = asdict(page)
    runs = [certify_layout_page(parsed, page, SHA) for _ in range(3)]
    assert runs[0] == runs[1] == runs[2]
    rng = random.Random(117)
    rng.shuffle(page.boxes)
    for b in page.boxes:
        rng.shuffle(b.textlines)
    assert certify_layout_page(parsed, page, SHA) == runs[0]
    assert asdict(real_layout(page_number)[1]) == before
    for c in runs[0].certificates:
        if c.provenance_status != 'CERTIFIED':
            assert c.quality_status == 'UNRESOLVED'


@pytest.mark.parametrize('page_number,note', [(56,36),(167,66)])
def test_known_cross_page_notes_never_false_complete(page_number, note):
    parsed, page = real_layout(page_number)
    c = next(c for c in certify_layout_page(parsed, page, SHA).certificates if c.note_number == note)
    assert c.local_boundary == 'KNOWN'
    assert c.end_reason == 'PAGE_BOUNDARY'
    assert c.continuation_status == 'UNRESOLVED_CONTINUATION'
    assert c.provenance_status == c.quality_status == 'UNRESOLVED'


def test_continuation_page_without_marker_is_not_reinvented():
    for number in (57,168):
        parsed, page = real_layout(number)
        result = certify_layout_page(parsed, page, SHA)
        assert all(c.provenance_status == 'UNRESOLVED' for c in result.certificates)
        assert not any(c.continuation_status == 'COMPLETE' for c in result.certificates)


def test_supported_two_column_note_has_complete_boundary():
    parsed, page, _ = supported()
    # Put terminal marker in another disjoint column. Geometry, not input order,
    # defines the same note flow and ownership of the first note.
    line = synthetic_line(2, 0, 150, 200, '8 Another note')
    page.boxes[-1] = box('footnote', line)
    native = PaintedSource([l for b in page.boxes for l in b.textlines])
    result = certify_layout_page(parsed, page, SHA, native_page=native)
    first = next(c for c in result.certificates if c.note_number == 7)
    assert first.provenance_status == 'CERTIFIED'
    assert first.quality_status == 'ACCEPTED'


@pytest.mark.parametrize('number,region_ids', [
    (80, ('region-cbabcc634980c627e2d2280b', 'region-5c800da9132cbc4511454e79')),
    (140, ('region-4208ec6381b2a5e29276d00e',)),
    (200, ('region-9a246f83b66e789817d4e727', 'region-6bcfd2e337fb9ad3f7934fe4')),
])
def test_all_five_real_v1_unsafe_zones_are_development_regressions(number, region_ids):
    from pymupdf4llm.helpers.document_layout import LayoutBox, PageLayout, ParsedDocument
    data = json.loads((Path(__file__).parent / 'fixtures/automatic_region_v2_development.json').read_text())
    p = next(p for p in data['pages'] if p['page_number'] == number)
    p['boxes'] = [LayoutBox(**b) for b in p['boxes']]
    page = PageLayout(**p)
    result = certify_layout_page(ParsedDocument(pages=[page]), page, SHA)
    by_id = {c.region_id: c for c in result.certificates}
    for rid in region_ids:
        assert by_id[rid].provenance_status == by_id[rid].quality_status == 'UNRESOLVED'
        assert 'ZONE_AMBIGUOUS' in by_id[rid].reason_codes


def test_generic_cross_page_segments_without_marker_remain_unresolved():
    from dataclasses import replace
    parsed, page, native = supported()
    first_run = certify_layout_page(parsed, page, SHA, native_page=native)
    line = synthetic_line(3, 0, 10, 200, 'continued words without a new marker')
    following = replace(page, page_number=page.page_number + 1, boxes=[box('text', line)])
    next_run = certify_layout_page(parsed, following, SHA, native_page=PaintedSource([line]))
    assert first_run.certificates[-1].continuation_status == 'UNRESOLVED_CONTINUATION'
    assert all(c.provenance_status == 'UNRESOLVED' for c in next_run.certificates)
    assert not any(c.continuation_of for c in next_run.certificates)


def test_rtl_and_mixed_do_not_gain_direction_from_script_alone():
    for text in ('7 שלום', '7 Hola שלום', '7 ����'):
        parsed, page, native = supported()
        page.boxes[1].textlines[0]['spans'][0]['text'] = text
        result = certify_layout_page(parsed, page, SHA, native_page=native)
        assert all(c.provenance_status == 'UNRESOLVED' for c in result.certificates)
