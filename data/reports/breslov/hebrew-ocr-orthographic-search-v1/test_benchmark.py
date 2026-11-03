"""No network, OCR, source PDF, or service use in tests; regression of offline contracts."""
import copy
import json
from pathlib import Path
import pytest
from benchmark import distance, metrics
from search_benchmark import expand, match, fold

OUT = Path(__file__).resolve().parent
FIXTURES = json.loads((OUT/'orthographic-fixtures.json').read_text())['cases']


@pytest.mark.parametrize('case', FIXTURES, ids=lambda c:c['id'])
def test_fixture(case):
    before=copy.deepcopy(case)
    result=match(case)
    assert result['safest_match_type']==case['expected_match']
    assert result['original_query']==case['query']
    assert result['canonical_source']==case['canonical_source']
    assert before==case


def test_unconfirmed_ambiguous_source_is_not_accepted():
    c=copy.deepcopy(FIXTURES[0]); c.pop('lexeme_guard')
    assert match(c)['variant_candidate_found']
    assert match(c)['safest_match_type'] is None


def test_candidate_not_identity_and_no_blanket_mater_removal():
    assert fold('פירוש') != fold('פֵּרוּשׁ')
    assert fold('שהוא') != fold('שהיא')
    assert expand('שהיא')['expanded_variants']==[]
    assert expand('לפירוש')['expanded_variants']==[]  # no unchecked affix stripping
    assert expand('פירושים')['expanded_variants']==[]


def test_exact_beats_lower_evidence_types():
    assert match(FIXTURES[8])['safest_match_type']=='exact'
    assert match(FIXTURES[9])['safest_match_type']=='niqqud_insensitive'
    assert match(FIXTURES[0])['safest_match_type']=='orthographic_variant'


def test_metrics_distinguish_letters_marks_boundaries_order_numbers():
    assert distance('אב','אבד')==1
    perfect=metrics('אוֹר הַפָּנִים, 149','אוֹר הַפָּנִים, 149',True)
    for k in ('base_letter_accuracy','word_order_accuracy','word_boundary_accuracy','niqqud_accuracy','number_accuracy','punctuation_accuracy'):
        assert perfect[k]==1
    unpointed=metrics('אוֹר הַפָּנִים,','אור הפנים,',True)
    assert unpointed['base_letter_accuracy']==1 and unpointed['niqqud_accuracy']==0
    fused=metrics('אור הפנים','אורהפנים')
    assert fused['base_letter_accuracy']==1 and fused['word_boundary_accuracy']==0
    reordered=metrics('אור הפנים','הפנים אור')
    assert reordered['word_order_accuracy']<1
    assert metrics('149','9')['number_accuracy']==0
    assert metrics('אור','אור =')['unexpected_character_count']==1
    assert metrics('אור','אור\ufffd')['replacement_character_count']==1


@pytest.mark.parametrize('page',(55,143,167))
def test_ocr_provenance_and_metrics_replay(page):
    gold={r['id']:r for r in json.loads((OUT/'ocr-goldens.json').read_text())['regions']}
    rows=json.loads((OUT/f'ocr-page{page}-results.json').read_text())['runs']
    assert {r['dpi'] for r in rows}=={300,400}
    for r in rows:
        assert r['source_method']=='visual_ocr' and r['version']=='5.3.4'
        assert r['rotation']==0 and r['preprocessing']=='raw RGB render'
        g=gold[r['region']]
        assert r['bbox']==g['bbox']
        if r['metrics']:
            assert r['metrics']==metrics(g['text'],r['logical_output'],g.get('pointed',False))


def test_good_native_stays_native_and_column_fusion_visible():
    rows=json.loads((OUT/'ocr-page167-results.json').read_text())['runs']
    combined=next(r for r in rows if r['region']=='R167_E_combined' and r['dpi']==300)
    assert 'HaTefilá 3. se refrena' in combined['logical_output']
    assert combined['metrics'] is None  # not a falsely certified full golden
    assert all(r['page']!=56 for r in rows)
