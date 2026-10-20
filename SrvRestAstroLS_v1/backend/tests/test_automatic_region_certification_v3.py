"""V3 structural proof removal, negative zones, identity and order regressions."""
from copy import deepcopy
from dataclasses import replace
import random
from types import SimpleNamespace

import pymupdf
import pytest

from modules.library.automatic_region_certification_v3 import certify_layout_page, certify_document
from test_automatic_region_certification import PaintedSource
from test_region_markdown_provenance import SHA, box, synthetic, synthetic_line


class RuledSource(PaintedSource):
    def __init__(self, lines):
        super().__init__(lines)
        self.rect = SimpleNamespace(width=300)
        self.rules = [100,300]

    def get_drawings(self):
        return [{"type":"s", "stroke_opacity":1,
                 "items":[("l",pymupdf.Point(10,y),pymupdf.Point(290,y))]} for y in self.rules]


def supported(*, continuation=False):
    caption = synthetic_line(0,0,110,97,"Panel caption")
    caption['spans'][0]['size'] = 5
    body = synthetic_line(1,0,10,160,"Ordinary main text")
    body['bbox'][2] = 290
    body['spans'][0]['size'] = 10
    separator = synthetic_line(2,0,110,297,"Notas y Fuentes")
    first = synthetic_line(3,0,10,340,"continued text" if continuation else "7 First note")
    second = synthetic_line(3,1,10,360,"8 Next note")
    parsed, page = synthetic(box('text',caption),box('text',body),box('section-header',separator),
                             box('footnote',first),box('footnote',second))
    return parsed,page,RuledSource([caption,body,separator,first,second])


def test_body_requires_composed_structure_not_central_text():
    parsed,page,native=supported()
    c=certify_layout_page(parsed,page,SHA,native_page=native).certificates[1]
    assert c.zone_type=='MAIN_BODY'
    assert c.provenance_status=='CERTIFIED'
    assert c.quality_status=='ACCEPTED'
    assert all(p.passed for p in c.body_proof)
    assert c.continuation_state=='CONTINUATION_UNRESOLVED'


@pytest.mark.parametrize('remove',['rules','caption','separator','anchor','native','direction','overlap','column','order','mixed','small','mixed_sizes','header','footer','heading','note'])
def test_body_negatives_fail_closed(remove):
    parsed,page,native=supported()
    body=page.boxes[1].textlines[0]
    if remove=='rules': native.rules.pop()
    elif remove=='caption': page.boxes[0].textlines[0]['bbox'][0] += 5
    elif remove=='separator': page.boxes[2].textlines[0]['spans'][0]['text']='Unknown separator'
    elif remove=='anchor':
        for b in page.boxes[3:]: b.boxclass='text'
    elif remove=='native': native=None
    elif remove=='direction': native.trace[1]['dir']=(-1.,0.)
    elif remove=='overlap': page.boxes.append(deepcopy(page.boxes[1]))
    elif remove=='column': body['bbox'][2]=130
    elif remove=='order':
        other=deepcopy(body);other['bbox'][1]+=20;other['bbox'][3]+=20
        other['spans'][0]['line']=-1
        page.boxes[1].textlines.append(other)
    elif remove=='mixed': body['spans'][0]['text']+=' שלום'
    elif remove=='small': body['spans'][0]['size']=7
    elif remove=='mixed_sizes':
        side=deepcopy(body['spans'][0]);side['size']=8;side['text']='Sidebar'
        body['spans'].append(side)
    elif remove in {'header','footer','heading','note'}:
        page.boxes[1].boxclass={'header':'page-header','footer':'page-footer','heading':'section-header','note':'footnote'}[remove]
    result=certify_layout_page(parsed,page,SHA,native_page=native)
    assert not any(c.zone_type=='MAIN_BODY' and c.provenance_status=='CERTIFIED' for c in result.certificates)
    assert all(c.quality_status=='UNRESOLVED' for c in result.certificates if c.provenance_status!='CERTIFIED')


def document():
    parsed,page,native=supported()
    # The open terminal is 8; next page begins unmarked and ends before 9.
    _,following,next_native=supported(continuation=True)
    following.page_number=2
    following.boxes[-1].textlines[0]['spans'][0]['text']='9 Following note'
    next_native=RuledSource([l for b in following.boxes for l in b.textlines])
    parsed.pages=[page,following]
    return parsed,{1:native,2:next_native}


def test_cross_page_identity_without_merging_page_text():
    parsed,natives=document()
    result=certify_document(parsed,SHA,native_pages=natives)
    first=next(c for c in result[0].certificates if c.note_number==8)
    second=next(c for c in result[1].certificates if c.continuation_of)
    assert first.editorial_unit_id==second.editorial_unit_id
    assert first.continuation_state=='CONTINUES_NEXT_PAGE'
    assert second.continuation_state=='CONTINUED_FROM_PREVIOUS'
    assert first.linked_region_ids==(second.region_id,)
    assert second.linked_region_ids==(first.region_id,)
    assert first.provenance_status==second.provenance_status=='CERTIFIED'
    assert result[0].provenance.pdf_page==1 and result[1].provenance.pdf_page==2
    for p in result:
        for c in p.certificates:
            assert p.provenance.spans_for_region(c.region_id)==c.markdown_ranges


@pytest.mark.parametrize('remove',['gap','font','new_marker','wrong_marker','separator','direction','duplicate','no_end'])
def test_continuation_negatives_never_link_or_complete(remove):
    parsed,natives=document()
    following=parsed.pages[1]
    if remove=='gap': following.page_number=3
    elif remove=='font': following.boxes[-2].textlines[0]['spans'][0]['font']='Other'
    elif remove=='new_marker': following.boxes[-2].textlines[0]['spans'][0]['text']='9 Unrelated unit'
    elif remove=='wrong_marker': following.boxes[-1].textlines[0]['spans'][0]['text']='10 Wrong successor'
    elif remove=='separator': following.boxes[2].textlines[0]['spans'][0]['text']='Unknown'
    elif remove=='direction': natives[2].trace[-2]['dir']=(-1.,0.)
    elif remove=='duplicate': following.boxes.append(deepcopy(following.boxes[-2]))
    elif remove=='no_end': following.boxes.pop()
    result=certify_document(parsed,SHA,native_pages=natives)
    assert not any(c.linked_region_ids for p in result for c in p.certificates)
    terminal=next(c for c in result[0].certificates if c.note_number==8)
    assert terminal.continuation_state=='CONTINUATION_UNRESOLVED'


def test_three_runs_and_page_box_line_permutation():
    parsed,natives=document()
    runs=[certify_document(parsed,SHA,native_pages=natives) for _ in range(3)]
    assert runs[0]==runs[1]==runs[2]
    rng=random.Random(932)
    rng.shuffle(parsed.pages)
    for page in parsed.pages:
        rng.shuffle(page.boxes)
        for b in page.boxes: rng.shuffle(b.textlines)
    assert certify_document(parsed,SHA,native_pages=natives)==runs[0]


def test_duplicate_pages_are_rejected():
    parsed,natives=document()
    parsed.pages.append(parsed.pages[0])
    with pytest.raises(ValueError,match='Duplicate'):
        certify_document(parsed,SHA,native_pages=natives)
