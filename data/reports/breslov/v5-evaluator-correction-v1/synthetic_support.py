"""Synthetic-only harness. Never import the gate runner or a certifier."""
import ast
import copy
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNNER = HERE.parent / 'v5-hybrid-independent-confirmation-v1/run_gate.py'
HELPERS = {'page_source', 'flat_line_ids', 'separator_y', 'source_audit'}


def legacy_namespace():
    tree = ast.parse((HERE / 'legacy_evaluator.py').read_text())
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in HELPERS]
    assert {n.name for n in nodes} == HELPERS
    ns = {}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(RUNNER), 'exec'), ns)
    return ns


def load_corrected():
    path = RUNNER.with_name('evaluator.py')
    spec = importlib.util.spec_from_file_location('corrected_evaluator', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def cases():
    def row(page, rid, state, links=()):
        return dict(pdf_page=page, region_id=rid, zone_type='note', note_number=7,
                    source_line_ids=[[page, 0]], provenance_status='CERTIFIED',
                    quality_status='ACCEPTED', linked_region_ids=list(links),
                    editorial_unit_id='unit', identity_state='IDENTITY_PROVEN' if links else 'UNRESOLVED',
                    continuation_state=state, continuation_status='CROSS_PAGE_COMPLETE' if links else 'OPEN',
                    identity_proof=[dict(name='synthetic_identity', passed=True, evidence=['synthetic'])])
    a = row(10, 'a', 'CONTINUES_NEXT_PAGE', ['b'])
    b = row(11, 'b', 'CONTINUED_FROM_PREVIOUS', ['a'])
    canonical = {10: [dict(note_number=7, end_reason='PAGE_BOUNDARY', parts=[dict(ids=[[10, 0]], text='7 open')])],
                 11: [dict(note_number=7, end_reason='NEXT_NOTE_IN_COLUMN_FLOW', continuation_of_page=10,
                           parts=[dict(ids=[[11, 0]], text='continued text')])]}
    inventory = [dict(page=p, boxes=[dict(lines=[dict(ids=[[p, 0]], text='synthetic', bbox=[0, 0, 1, 1])])]) for p in (10, 11)]
    result = []
    counters = ['false_cross_page_links', 'false_editorial_completions', 'missed_true_links',
                'missing_reciprocal_links', 'unsafe_false_identity_proven', 'valid_cross_page_relations']
    def add(name, rows, truth=None, **expected):
        result.append(dict(name=name, rows=copy.deepcopy(rows), canonical=copy.deepcopy(canonical if truth is None else truth),
                           inventory=copy.deepcopy(inventory), expected={k:expected.get(k, 0) for k in counters}))
    local = row(10, 'a', 'COMPLETE_LOCAL')
    add('same_page_complete', [local], {10: canonical[10]})
    open_row = row(10, 'a', 'CONTINUES_NEXT_PAGE')
    add('page_boundary_open', [open_row], {10: canonical[10]})
    forward = copy.deepcopy(b); forward['linked_region_ids']=[]; forward['identity_state']='UNRESOLVED'
    add('forward_continuation', [a, forward], missing_reciprocal_links=1, valid_cross_page_relations=1)
    add('reciprocal_relation', [a,b], valid_cross_page_relations=1)
    wrong = copy.deepcopy(a); wrong['linked_region_ids']=['absent']
    add('wrong_target', [wrong,b], false_cross_page_links=2, missed_true_links=1, unsafe_false_identity_proven=2)
    add('explicit_no_link', [a,b], {}, false_cross_page_links=1, unsafe_false_identity_proven=2)
    missing = copy.deepcopy(b); missing['linked_region_ids']=[]; missing['identity_state']='UNRESOLVED'
    add('missing_expected', [open_row,missing], missed_true_links=1)
    add('cross_page_complete', [a,b], valid_cross_page_relations=1)
    false_local = copy.deepcopy(a); false_local['continuation_state']='COMPLETE_LOCAL'
    add('false_local_complete', [false_local,b], false_editorial_completions=1, valid_cross_page_relations=1)
    add('unresolved_unlinked', [open_row], {})
    add('unresolved_proven_link', [a,b], {}, false_cross_page_links=1, unsafe_false_identity_proven=2)
    conflict=copy.deepcopy(b); conflict['editorial_unit_id']='other'
    add('conflicting_editorial_ids', [a,conflict], false_cross_page_links=1, missed_true_links=1, unsafe_false_identity_proven=2)
    duplicate=copy.deepcopy(a); duplicate['linked_region_ids']=['b','b']
    add('duplicate_representation', [duplicate,b], valid_cross_page_relations=1)
    add('dangling', [wrong,missing], false_cross_page_links=1, missed_true_links=1, unsafe_false_identity_proven=1)
    unrelated=copy.deepcopy(b); unrelated['region_id']='c'; unrelated['source_line_ids']=[]
    wrong_c=copy.deepcopy(a); wrong_c['linked_region_ids']=['c']
    unrelated['linked_region_ids']=['a']
    add('wrong_existing_region', [wrong_c,missing,unrelated], false_cross_page_links=1, missed_true_links=1, unsafe_false_identity_proven=2)
    return result


def evaluate(fn, case):
    canonical = {int(k):v for k,v in case['canonical'].items()}
    metrics, violations, links = fn([], case['rows'], case['inventory'], canonical, part='SYNTHETIC')
    mismatch={k:dict(expected=v, actual=metrics.get(k,0)) for k,v in case['expected'].items() if metrics.get(k,0)!=v}
    return dict(name=case['name'], metrics=metrics, mismatches=mismatch, passed=not mismatch,
                violations=violations, links=links)


if __name__ == '__main__':
    raise SystemExit('Use validate_evaluator.py; pre-fix artifacts are frozen.')
