"""Offline regression of measurements and fail-closed policy, not a PASS claim."""
from pathlib import Path
import hashlib
import json
import sys
import pytest

OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(OUT))
from evaluate import frozen
from ocr_gate import decide

CASES=json.loads((OUT/'holdout-definition.json').read_text())['cases']
OCR=json.loads((OUT/'ocr-quality-results.json').read_text())

@pytest.mark.parametrize('case',CASES,ids=lambda c:c['id'])
def test_frozen_replay_preserves_originals_and_no_manual_oracle(case):
    m=frozen(); inputs={k:case[k] for k in ('query','canonical_source')};before=inputs.copy()
    result=m.match(inputs)
    assert inputs==before
    assert result['original_query']==case['query']
    assert result['canonical_sha256']==hashlib.sha256(case['canonical_source'].encode()).hexdigest()
    assert result['variant'] is False
    if not case['expected_match']:
        assert result['safest_match_type'] is None
    assert m.match({'query':case['query'],'canonical_source':case['query']})['safest_match_type']=='exact'

@pytest.mark.parametrize('row',OCR['rows'],ids=lambda r:r['id'])
def test_recorded_ocr_decision_never_receives_golden(row):
    forbidden={'golden','golden_text','expected_search','expected_display','evaluation_metrics','metrics'}
    assert not forbidden.intersection(row['signals'])
    output=decide(row['signals'])
    for key in ('decision_search','decision_display','reason_codes'):
        assert output[key]==row[key]
    assert output['replacement_authorized'] is False

@pytest.mark.parametrize('good,bad',[('149','9'),('37','7'),('149','19')])
def test_material_numbers_reject_even_with_high_confidence(good,bad):
    result=decide(dict(text=bad,trusted_digits=[good],trusted_reference=good,
        geometry_verified=True,fixed_config_agreement=True,confidence=100))
    assert result['decision_search']=='SEARCH_REJECT'
    assert 'OCR_DIGIT_LOSS' in result['reason_codes']

@pytest.mark.parametrize('confidence',[0,50,99,100])
def test_high_confidence_and_cross_config_agreement_not_sufficient(confidence):
    result=decide(dict(text='אור הפנים',confidence=confidence,geometry_verified=True,fixed_config_agreement=True))
    assert result['decision_search']=='SEARCH_REJECT'
    assert 'OCR_UNCERTAIN' in result['reason_codes']

@pytest.mark.parametrize('text,reason',[('אורהפנים','OCR_WORD_MERGE'),('א ור הפנים','OCR_WORD_SPLIT'),('אור הפנום','OCR_BASE_LETTER_ERROR')])
def test_reference_discrepancies(text,reason):
    result=decide(dict(text=text,trusted_reference='אור הפנים',geometry_verified=True,fixed_config_agreement=True))
    assert result['decision_search']=='SEARCH_REJECT'
    assert reason in result['reason_codes']

def test_search_and_display_have_distinct_requirements():
    signals=dict(text='אור הפנים',trusted_reference='אוֹר הַפָּנִים',geometry_verified=True,fixed_config_agreement=True)
    assert decide(signals)['decision_search']=='SEARCH_ACCEPT'
    assert decide(signals)['decision_display']=='DISPLAY_REJECT'
    # Synthetic unit test only; not counted as an accepted real OCR fixture.
    signals['trusted_display_reference']='אור הפנים'
    assert decide(signals)['decision_display']=='DISPLAY_ACCEPT'

def test_visual_source_error_never_salvaged():
    result=decide(dict(text='149',trusted_reference='149',source_visual='BAD',geometry_verified=True,fixed_config_agreement=True))
    assert result['decision_search']=='SEARCH_REJECT'
    assert 'SOURCE_PDF_ERROR' in result['reason_codes']

def test_known_bad_headers_rejected_and_vacuous_pass_not_emitted():
    for name in ('R167_A','R55_A'):
        row=next(r for r in OCR['rows'] if r['id']==name)
        assert row['decision_search']=='SEARCH_REJECT'
        assert 'OCR_DIGIT_LOSS' in row['reason_codes']
    assert OCR['status']=='BLOCKED'
    assert OCR['counts']['safe_search_incorrectly_rejected']==3

def test_measured_failure_not_optimized_away():
    result=json.loads((OUT/'holdout-results.json').read_text())
    assert result['status']=='FAIL_RECALL'
    assert result['by_expected_type']['ORTHOGRAPHIC_VARIANT']==dict(count=10,correct=0)
    assert result['metrics']['dangerous_false_positives']==0
    assert len(CASES)==42
    assert hashlib.sha256((OUT/'holdout-definition.json').read_bytes()).hexdigest()==(OUT/'holdout-definition-hash.txt').read_text().strip()
