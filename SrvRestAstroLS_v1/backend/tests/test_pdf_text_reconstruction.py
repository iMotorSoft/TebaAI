from collections import Counter
import json
from pathlib import Path
import unicodedata

import pytest

from modules.library.pdf_text_reconstruction import reconstruct_line, reconstruct_runs


def char(c, x, y=20, width=5):
    return (ord(c), 0, (x, y), (x, y-8, x+width, y+2))


def test_hebrew_bases_follow_geometry_not_input_reversal():
    chars = [char('ם', 0), char('ש', 20), char('ו', 10), char('ל', 15)]
    assert reconstruct_line(chars, size=10)['text'] == 'שלום'


def test_marks_before_base_attach_by_geometry_with_multiple_marks():
    chars = [char('ָ', 22, width=.01), char('ש', 20), char('ׁ', 20, width=0), char('ם', 0)]
    result = reconstruct_line(chars, size=10)
    assert result['text'] == 'שָׁם'
    assert result['mark_owners'] == {0: 1, 2: 1}
    assert not result['diagnostics']


@pytest.mark.parametrize('text', ['ש1', '1ש', 'Español שלום', 'ש(ל)', 'ש\ufffd'])
def test_unsupported_mixed_or_mirrored_input_preserved_with_diagnostics(text):
    chars = [char(c, i*6) for i, c in enumerate(text)]
    result = reconstruct_line(chars, size=10)
    assert result['text'] == text
    assert result['diagnostics']


def test_uncertain_mark_is_not_attached_to_previous_codepoint():
    chars = [char('ש', 20), char('ָ', 100, width=0), char('ם', 0)]
    result = reconstruct_line(chars, size=10)
    assert result['text'] == 'שָם'
    assert result['diagnostics'] == ['ambiguous_mark:1']


def test_number_and_latin_order_and_punctuation():
    text = 'Salmos 16:1; 37, ABC.'
    chars = [char(c, i*6) for i, c in enumerate(text)]
    assert reconstruct_line(chars, size=10)['text'] == text


def test_real_space_is_preserved_without_synthetic_insertion():
    chars = [char('ם', 0), char('ו', 6), char('ל', 12), char('ש', 18), char(' ', 24), char('א', 30)]
    result = reconstruct_line(chars, size=10)
    assert result['text'] == 'א שלום'
    assert Counter(result['text']) == Counter(chr(c[0]) for c in chars)


def test_operations_and_baselines_not_merged_into_columns_or_paragraphs():
    runs = [{'seqno': 1, 'size': 10, 'chars': [char('a', 0), char('b', 0, y=40)]},
            {'seqno': 2, 'size': 10, 'chars': [char('c', 100)]}]
    lines = reconstruct_runs(runs)
    assert [l['text'] for l in lines] == ['a', 'b', 'c']
    assert [l['seqno'] for l in lines] == [1, 1, 2]


FIXTURES = json.loads((Path(__file__).parent / 'fixtures/likutey_halajot_reconstruction_v1.json').read_text())['fixtures']


@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda f: f"pdf-{f['pdf_page']}")
def test_real_page_codepoint_conservation_and_short_golden(fixture):
    lines = reconstruct_runs(fixture['runs'])
    result = '\n\n'.join(l['text'] for l in lines)
    assert Counter(''.join(l['text'] for l in lines)) == Counter(chr(c[0]) for r in fixture['runs'] for c in r['chars'])
    # Page 55 full-line golden stays blocked: a neighbouring reference contains
    # mirrored parentheses. Never mistake a local fragment for page-wide PASS.
    for golden in fixture['goldens']:
        if fixture['pdf_page'] == 55 and golden.startswith('וְזֶה'):
            assert golden not in result
            assert any('mirrored_punctuation_requires_inverse_bidi' in l['diagnostics'] for l in lines)
        else:
            assert golden in result


def test_real_niqqud_fragment_geometry_and_normalization_measurement():
    fragment = next(f for f in FIXTURES if f['pdf_page'] == 55)['niqqud_fragment']
    result = reconstruct_line(fragment['chars'], size=fragment['size'])
    assert not result['diagnostics']
    assert unicodedata.normalize('NFD', result['text']).strip() == unicodedata.normalize('NFD', fragment['expected'])
    # Output preserves original mark sequence, not an untested global NFC/NFD.
    assert result['text'] == 'וְזֶה פֵּרוּשׁ הַפָּסוּק '


@pytest.mark.parametrize('order', [(0,1,2,3), (3,2,1,0), (1,3,0,2)])
def test_geometric_result_stable_under_char_permutation(order):
    chars = [char('ם', 0), char('ש', 20), char('ָ', 22, width=.01), char('ׁ', 20, width=0)]
    result = reconstruct_line([chars[i] for i in order], size=10)
    assert unicodedata.normalize('NFD', result['text']) == unicodedata.normalize('NFD', 'שָׁם')
    assert Counter(result['text']) == Counter(chr(c[0]) for c in chars)
