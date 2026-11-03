"""Additive offline cases for existing Hebrew helpers; no parallel normalizer."""
import importlib.util
from pathlib import Path
import unicodedata

import pytest
from modules.library.hebrew_lexical_normalizer import normalize_hebrew_lexical, normalize_hebrew_search

_spec = importlib.util.spec_from_file_location('regional_benchmark', Path(__file__).with_name('benchmark_offline.py'))
benchmark = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(benchmark)


def test_good_native_not_replaced():
    assert benchmark.candidate_action(visual_good=True, native_good=True) == 'PASS_NATIVE'


def test_broken_native_only_requests_benchmark():
    assert benchmark.candidate_action(visual_good=True, native_good=False) == 'OCR_BENCHMARK_REQUIRED'


def test_structural_regression_is_not_ocr_target():
    assert benchmark.candidate_action(visual_good=True, native_good=False, structural_regression=True) == 'FIX_STRUCTURAL_REGRESSION'


@pytest.mark.parametrize('native_good', [True, False])
def test_source_error_stays_source_error(native_good):
    assert benchmark.candidate_action(visual_good=False, native_good=native_good) == 'SOURCE_PDF_ERROR'


def test_unknown_visual_does_not_choose_silently():
    assert benchmark.candidate_action(visual_good=None, native_good=False) == 'UNRESOLVED_SOURCE_OR_PIPELINE'


def test_same_base_letters_same_evidence_and_unchanged_display():
    pointed = 'וְזֶה פֵּרוּשׁ הַפָּסוּק'
    original_bytes = pointed.encode()
    evidence = {'id': 'offline-1', 'display': pointed}
    index = {normalize_hebrew_search(pointed): evidence}
    assert index[normalize_hebrew_search('וזה פרוש הפסוק')] is evidence
    assert index[normalize_hebrew_search(unicodedata.normalize('NFD', pointed))] is evidence
    assert evidence['display'].encode() == original_bytes


def test_requested_example_has_extra_yod_not_only_niqqud():
    assert normalize_hebrew_search('וְזֶה פֵּרוּשׁ הַפָּסוּק') == 'וזה פרוש הפסוק'
    assert normalize_hebrew_search('וזה פירוש הפסוק') != 'וזה פרוש הפסוק'
    # A separately pointed source with the same consonants DOES match.
    assert normalize_hebrew_search('וְזֶה פֵּירוּשׁ הַפָּסוּק') == 'וזה פירוש הפסוק'


@pytest.mark.parametrize('value', ['אבג 149 (LM I, 22:1)', 'שלום-עולם', 'אב ג', 'אבג Latin', 'אחטם לך'])
def test_strict_existing_lexical_options_preserve_boundaries_numbers_punctuation_mixed(value):
    assert normalize_hebrew_lexical(value, do_unicode=False, do_maqaf=False, do_invisible=False) == value


def test_base_letters_order_and_negative_cases():
    assert normalize_hebrew_search('אוֹר הַפָּנִים') == 'אור הפנים'
    for negative in ('הפנים אור', 'אור הפנימ', 'אורהפנים', 'אור הפנים 149'):
        assert normalize_hebrew_search(negative) != 'אור הפנים'


def test_broad_search_helper_cannot_certify_reference_identity():
    assert normalize_hebrew_search('(LM I, 22:1)') == normalize_hebrew_search('(LM I, 22-1)')
    assert normalize_hebrew_lexical('(LM I, 22:1)') != normalize_hebrew_lexical('(LM I, 22-1)')
