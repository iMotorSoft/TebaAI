"""Evaluator only: no certifier, PDF, holdout, services or production imports."""
import ast
import copy
import importlib.util
import json
from pathlib import Path
import sys

import pytest

EVIDENCE = Path(__file__).resolve().parents[3] / 'data/reports/breslov/v5-evaluator-correction-v1'
spec = importlib.util.spec_from_file_location('synthetic_evaluator_support', EVIDENCE / 'synthetic_support.py')
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)
evaluator = support.load_corrected()
CASES = json.loads((EVIDENCE / 'synthetic-evaluator-cases.json').read_text())


def case(name):
    return copy.deepcopy(next(c for c in CASES if c['name'] == name))


def score(c):
    return support.evaluate(evaluator.source_audit, c)['metrics']


@pytest.mark.parametrize('c', CASES, ids=[c['name'] for c in CASES])
def test_truth_table(c):
    result = support.evaluate(evaluator.source_audit, c)
    assert result['passed'], result['mismatches']


@pytest.mark.parametrize('name,metric', [
    ('reciprocal_relation','false_cross_page_links'),
    ('cross_page_complete','false_editorial_completions'),
])
def test_original_defects_reproduced(name, metric):
    before = support.evaluate(support.legacy_namespace()['source_audit'], case(name))
    assert before['metrics'][metric] == 1
    assert score(case(name))[metric] == 0


def test_archived_synthetic_audit():
    archive = json.loads((support.RUNNER.parent / 'resume-evaluator-audit.json').read_text())
    c = dict(name='archived', rows=archive['synthetic_rows'],
             canonical=archive['synthetic_canonical'],
             inventory=[dict(page=p, boxes=[]) for p in (10,11)], expected={})
    before = support.evaluate(support.legacy_namespace()['source_audit'], c)['metrics']
    after = score(c)
    assert before == archive['metrics']
    assert after['false_cross_page_links'] == after['false_editorial_completions'] == 0
    for k in before:
        if k not in ('false_cross_page_links','false_editorial_completions'):
            assert after[k] == before[k]


def test_every_conflicting_link_is_scored_not_only_first():
    c = case('reciprocal_relation')
    c['rows'][0]['linked_region_ids'] += ['absent', 'absent']
    m = score(c)
    assert m['valid_cross_page_relations'] == 1
    assert m['false_cross_page_links'] == 1


def test_identity_proof_failure_is_unsafe():
    c = case('reciprocal_relation')
    c['rows'][0]['identity_proof'][0]['passed'] = False
    m = score(c)
    assert m['false_cross_page_links'] == 1
    assert m['unsafe_false_identity_proven'] == 2


def test_other_local_note_not_penalized_by_page_continuation():
    c = case('reciprocal_relation')
    local = copy.deepcopy(c['rows'][0])
    local.update(region_id='different',note_number=8,source_line_ids=[],
                 linked_region_ids=[],identity_state='UNRESOLVED',continuation_state='COMPLETE_LOCAL')
    c['rows'].append(local)
    assert score(c)['false_editorial_completions'] == 0


@pytest.mark.parametrize('field,value,metric', [
    ('source_line_ids', [[99,99]], 'unsafe_false_provenance_certifications'),
    ('source_line_ids', [[99,99]], 'unsafe_false_certifications'),
    ('linked_region_ids', [], 'false_identity_proven'),
    ('identity_state', 'UNRESOLVED', 'inconsistent_identity_state'),
])
def test_existing_safety_checks_preserved(field,value,metric):
    c = case('reciprocal_relation')
    c['rows'][0][field] = value
    before = support.evaluate(support.legacy_namespace()['source_audit'], c)['metrics']
    assert score(c)[metric] == before[metric] > 0


def test_body_safety_preserved():
    c = case('same_page_complete')
    c['rows'][0]['zone_type'] = 'MAIN_BODY'
    c['inventory'][0]['boxes'][0]['lines'][0]['bbox'] = [0,20,1,21]
    c['inventory'][0]['boxes'][0]['lines'].append(dict(ids=[[10,1]],text='Notas y Fuentes',bbox=[0,10,1,11]))
    before = support.evaluate(support.legacy_namespace()['source_audit'],c)['metrics']
    assert score(c)['false_body_certifications'] == before['false_body_certifications'] == 1


def test_permutation_and_duplicate_normalization():
    c = case('duplicate_representation')
    first = score(c)
    c['rows'].reverse()
    assert score(c) == first
    assert first['valid_cross_page_relations'] == 1


def test_duplicate_region_ids_rejected():
    c = case('reciprocal_relation')
    c['rows'].append(copy.deepcopy(c['rows'][0]))
    with pytest.raises(ValueError, match='Duplicate'):
        score(c)


def test_runner_import_is_certifier_free_and_uses_corrected_audit(monkeypatch):
    import runpy
    import subprocess
    monkeypatch.syspath_prepend(str(support.RUNNER.parent))
    namespace = runpy.run_path(str(support.RUNNER), run_name='evaluator_import_test')
    c = case('reciprocal_relation')
    assert support.evaluate(namespace['source_audit'],c)['passed']
    subprocess.run(
        [sys.executable, '-c',
         "import runpy, sys; sys.path.insert(0, sys.argv[1]); "
         "runpy.run_path(sys.argv[2], run_name='evaluator_import_test'); "
         "assert not any('automatic_region_certification_v5' in n for n in sys.modules)",
         str(support.RUNNER.parent), str(support.RUNNER)],
        check=True,
    )


def test_safety_gate_does_not_turn_misses_into_coverage_threshold():
    tree = ast.parse(support.RUNNER.read_text())
    diagnostic_filters = [n for n in ast.walk(tree) if isinstance(n, ast.Compare)
                          and any(isinstance(op,ast.NotIn) for op in n.ops)
                          and 'valid_cross_page_relations' in ast.unparse(n)]
    assert len(diagnostic_filters) == 1
    assert 'missed_true_links' in ast.unparse(diagnostic_filters[0])


def test_runner_uses_standalone_evaluator_without_top_level_v5_import():
    tree = ast.parse(support.RUNNER.read_text())
    assert any(isinstance(n,ast.ImportFrom) and n.module == 'evaluator'
               and any(a.name=='source_audit' for a in n.names) for n in tree.body)
    assert not any(isinstance(n,ast.ImportFrom) and 'certification_v5' in (n.module or '') for n in tree.body)
