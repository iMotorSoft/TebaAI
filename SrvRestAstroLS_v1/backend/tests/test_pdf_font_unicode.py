from __future__ import annotations

import hashlib

import pytest

from modules.library import pdf_font_unicode as recovery


class Page:
    def __init__(self, fonts):
        self.fonts = fonts

    def get_fonts(self):
        return self.fonts


class Document:
    def __init__(self, *, program=b'audited font', encoding='Identity-H', kind='Type0', existing=False):
        self.program = program
        self.pages = [Page([(17, 'cff', kind, 'ArbitraryFontName', 'F1', encoding)])] * 2
        self.keys = {(17, 'ToUnicode'): ('xref', '9 0 R')} if existing else {}
        self.streams = {}
        self.last = 30

    def __iter__(self):
        return iter(self.pages)

    def xref_get_key(self, xref, key):
        return self.keys.get((xref, key), ('null', 'null'))

    def extract_font(self, xref):
        return ('ArbitraryFontName', 'cff', 'Type0', self.program)

    def get_new_xref(self):
        self.last += 1
        return self.last

    def update_object(self, xref, obj):
        assert obj == '<<>>'

    def update_stream(self, xref, stream):
        self.streams[xref] = stream

    def xref_set_key(self, xref, key, value):
        self.keys[xref, key] = ('xref', value)


@pytest.fixture
def known(monkeypatch):
    fingerprint = hashlib.sha256(b'audited font').hexdigest()
    monkeypatch.setattr(recovery, 'profiles', lambda: {
        fingerprint: {'name': 'NotUsedForMatching', 'mappings': {'268': 'א', '314': 'שׁ'}}
    })
    return fingerprint


def test_exact_hash_only_in_memory_once_even_if_font_is_shared(known):
    doc = Document()
    result = recovery.repair_missing_font_unicode_maps(doc)
    assert result == [{'font_program_sha256': known, 'mapped_cids': 2,
                       'font_xref': 17, 'source_pdf_modified': False}]
    assert len(doc.streams) == 1
    assert b'<013A> <05E905C1>' in next(iter(doc.streams.values()))
    assert recovery.repair_missing_font_unicode_maps(doc) == []
    assert doc.program == b'audited font'


@pytest.mark.parametrize('kwargs', [
    {'program': b'unknown font'}, {'existing': True},
    {'encoding': 'WinAnsiEncoding'}, {'kind': 'TrueType'},
])
def test_unknown_or_noneligible_fonts_remain_untouched(known, kwargs):
    doc = Document(**kwargs)
    assert recovery.repair_missing_font_unicode_maps(doc) == []
    assert not doc.streams


def test_cmap_batches_and_multicodepoint_unicode():
    cmap = recovery.unicode_cmap({str(i): 'שּׁ' for i in range(201)})
    assert cmap.count(b'100 beginbfchar') == 2
    assert b'1 beginbfchar' in cmap
    assert b'<0000> <05E905BC05C1>' in cmap


@pytest.mark.parametrize('mapping', [{'65536': 'א'}, {'-1': 'א'}, {'1': ''}])
def test_invalid_map_rejected(mapping):
    with pytest.raises(ValueError):
        recovery.unicode_cmap(mapping)


def test_reviewed_shin_sin_dagesh_and_holam_are_distinct():
    bank = recovery.profiles()
    campus = bank['249ef7e56fb1a9f324237814abdc71b652e2f2e7057dfea313128cac9d1071ac']['mappings']
    ktifa = bank['6a89bcec987cc39d4730b40f3b0ab991a2dbe5461efc0b08820962933615d47f']['mappings']
    assert campus['264'] == 'ׁ' and campus['265'] == 'ׂ'
    assert campus['314'] == 'שׁ' and campus['315'] == 'שׂ'
    assert ktifa['176'] == 'שׁ' and ktifa['178'] == 'שּׁ'
    assert ktifa['187'] == 'וּ' and ktifa['204'] == 'וֹ'
    assert ktifa['210'] == 'ךְ' and ktifa['211'] == 'ךָ'
