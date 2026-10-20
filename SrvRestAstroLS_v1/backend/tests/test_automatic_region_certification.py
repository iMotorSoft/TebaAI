"""Automatic evidence issuance; no positive quality/provenance flags accepted."""
from copy import deepcopy
from dataclasses import asdict
import inspect
import json
import random

import pytest

from modules.library.automatic_region_certification import (
    certify_layout_page, direction, extract_pdf_region_certificates, native_evidence,
)
from test_region_markdown_provenance import (
    SHA, assert_notes, box, real_layout, synthetic, synthetic_line,
)


class PaintedSource:
    """Independent synthetic PDF trace/bboxlog, not a certificate input."""
    def __init__(self, lines):
        self.trace = []
        for i, line in enumerate(lines):
            content = ''.join(s['text'] for s in line['spans'])
            x, y = line['spans'][0]['origin']
            self.trace.append({'chars': [(ord(c), 1, (x + k, y), (x + k, y - 1, x + k + .5, y))
                                         for k, c in enumerate(content)],
                               'seqno': i, 'opacity': 1, 'type': 0, 'dir': (1., 0.)})
        self.log = [('fill-text', tuple(l['bbox'])) for l in lines]

    def get_texttrace(self):
        return self.trace

    def get_bboxlog(self):
        return self.log


def note_page(content='7 A short note'):
    line = synthetic_line(0, 0, 10, 200, content)
    parsed, page = synthetic(box('footnote', line))
    return parsed, page, PaintedSource([line])


def test_automatic_note_certificate_has_real_computed_quality_and_serializes():
    parsed, page, native = note_page()
    result = certify_layout_page(parsed, page, SHA, native_page=native)
    cert, = result.certificates
    assert cert.provenance_status == 'CERTIFIED'
    assert cert.quality_status == 'ACCEPTED'
    assert cert.zone_type == 'note' and cert.direction == 'LTR'
    assert cert.end_reason == 'PAGE_BOUNDARY'  # NOT a complete editorial end!
    assert json.loads(json.dumps(result.to_dict())) == result.to_dict()
    assert 'visual_good' not in inspect.signature(certify_layout_page).parameters


def test_missing_native_evidence_never_accepts_clean_text():
    parsed, page, _ = note_page()
    cert, = certify_layout_page(parsed, page, SHA).certificates
    assert cert.provenance_status == 'CERTIFIED'
    assert cert.quality_status == 'UNRESOLVED'


@pytest.mark.parametrize('text,expected', [
    ('שלום', 'RTL'), ('Hola', 'LTR'), ('Hola שלום', 'MIXED'),
    ('123 !!!', 'UNRESOLVED'), ('����', 'UNRESOLVED'), ('ש abcdef', 'MIXED'),
])
def test_direction_counts_all_strong_characters(text, expected):
    assert direction([synthetic_line(0, 0, 10, 10, text)]) == expected


@pytest.mark.parametrize('mutation', ['zone', 'script', 'identity', 'opacity', 'occlusion', 'text', 'order'])
def test_required_evidence_removal_fails_closed(mutation):
    parsed, page, native = note_page()
    if mutation == 'zone':
        page.boxes[0].boxclass = 'text'
    elif mutation == 'script':
        page.boxes[0].textlines[0]['spans'][0]['text'] += ' שלום'
    elif mutation == 'identity':
        page.boxes.append(deepcopy(page.boxes[0]))
    elif mutation == 'opacity':
        native.trace[0]['opacity'] = .5
    elif mutation == 'occlusion':
        native.log.append(('fill-path', (0, 0, 300, 500)))
    elif mutation == 'text':
        cp, glyph, origin, bbox = native.trace[0]['chars'][2]
        native.trace[0]['chars'][2] = (ord('B'), glyph, origin, bbox)
    elif mutation == 'order':
        native.trace[0]['dir'] = (-1., 0.)
    result = certify_layout_page(parsed, page, SHA, native_page=native)
    assert all(c.quality_status == 'UNRESOLVED' for c in result.certificates)
    if mutation in {'zone', 'script', 'identity'}:
        assert all(c.provenance_status == 'UNRESOLVED' for c in result.certificates)


def test_duplicate_text_ownership_is_not_substring_lookup():
    parsed, page = synthetic(box('text', synthetic_line(0, 0, 10, 10, 'Repeated')),
                             box('text', synthetic_line(1, 0, 10, 30, 'Repeated')))
    result = certify_layout_page(parsed, page, SHA)
    a, b = result.certificates
    assert a.region_id != b.region_id
    assert a.markdown_ranges[0][1] == b.markdown_ranges[0][0]
    assert result.provenance.owners(*b.markdown_ranges[0])[0].region_id == b.region_id


@pytest.mark.parametrize('number', [55, 56, 167])
def test_real_ir_three_runs_and_full_input_permutation(number):
    parsed, page = real_layout(number)
    before = asdict(page)
    runs = [certify_layout_page(parsed, page, SHA) for _ in range(3)]
    assert runs[0] == runs[1] == runs[2]
    rng = random.Random(79)
    rng.shuffle(page.boxes)
    for b in page.boxes:
        rng.shuffle(b.textlines)
    assert certify_layout_page(parsed, page, SHA) == runs[0]
    page2 = real_layout(number)[1]
    assert asdict(page2) == before


@pytest.mark.parametrize('number', [56, 167])
def test_automatic_labelled_note_columns_and_page_local_boundaries(number):
    parsed, page = real_layout(number)
    result = certify_layout_page(parsed, page, SHA)
    assert_notes(result.provenance, number)
    notes = [c for c in result.certificates if c.note_number]
    assert all(c.zone_type == 'note' and c.provenance_status == 'CERTIFIED' for c in notes)
    assert notes[-1].end_reason == 'PAGE_BOUNDARY'
    assert notes[-1].continuation_of is None


def test_text_is_not_assumed_body_even_when_it_looks_good():
    parsed, page, native = note_page('7 A short note')
    page.boxes[0].boxclass = 'text'
    c, = certify_layout_page(parsed, page, SHA, native_page=native).certificates
    assert c.zone_type == 'text'
    assert 'ZONE_UNRESOLVED' in c.reason_codes
    assert c.quality_status == 'UNRESOLVED'


def test_unlabelled_continuation_is_not_reinvented_as_body():
    parsed, page = real_layout(57)
    result = certify_layout_page(parsed, page, SHA)
    assert all(c.quality_status == 'UNRESOLVED' for c in result.certificates)
    assert not any(c.note_number == 36 for c in result.certificates)


def test_unsupported_layout_retains_inventory_and_fails_closed():
    parsed, page, native = note_page()
    page.boxes[0].boxclass = 'formula'
    result = certify_layout_page(parsed, page, SHA, native_page=native)
    cert, = result.certificates
    assert cert.provenance_status == 'UNRESOLVED'
    assert cert.quality_status == 'UNRESOLVED'
    assert result.provenance.markdown


def test_reversed_numeric_column_order_is_not_certified():
    parsed, page = synthetic(box('footnote', synthetic_line(0, 0, 10, 200, '8 Left note')),
                             box('footnote', synthetic_line(1, 0, 150, 200, '7 Right note')))
    result = certify_layout_page(parsed, page, SHA)
    assert all('UNSAFE_COLUMN_ORDER' in c.reason_codes for c in result.certificates)
    assert all(c.provenance_status == 'UNRESOLVED' for c in result.certificates)


def test_native_replacement_is_attributed_only_with_visible_differential():
    line = synthetic_line(0, 0, 10, 200, 'Notas y Fuentes\ufffd')
    native_line = deepcopy(line)
    native_line['spans'][0]['text'] = 'Notas y Fuentes\x03'
    parsed, page = synthetic(box('section-header', line))
    native = PaintedSource([native_line])
    cert, = certify_layout_page(parsed, page, SHA, native_page=native).certificates
    assert cert.provenance_status == 'CERTIFIED'
    assert cert.quality_status == 'PLATFORM_EXTRACTION_ERROR'
    native.trace[0]['opacity'] = 0
    cert, = certify_layout_page(parsed, page, SHA, native_page=native).certificates
    assert cert.quality_status == 'UNRESOLVED'


def test_source_errors_are_not_invented():
    parsed, page, native = note_page('7 A note \ufffd')
    cert, = certify_layout_page(parsed, page, SHA, native_page=native).certificates
    assert cert.quality_status == 'UNRESOLVED'


def test_api_runs_live_canonical_extraction_without_ocr(tmp_path):
    import pymupdf
    from modules.library.extractors import extract_pdf_with_region_certificates
    pdf = tmp_path / 'generic.pdf'
    with pymupdf.open() as doc:
        doc.new_page().insert_text((50, 50), 'A simple generic body')
        doc.save(pdf)
    results = extract_pdf_with_region_certificates(str(pdf), pages=[1])
    assert len(results) == 1 and results[0]['certificates']
    assert results[0]['document_sha'] != SHA
    assert all(c['quality_status'] == 'UNRESOLVED' for c in results[0]['certificates'])
    with pytest.raises(ValueError):
        extract_pdf_region_certificates(str(pdf), pages=[0])
