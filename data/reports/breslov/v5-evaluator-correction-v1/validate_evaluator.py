"""Repeatable synthetic + archived-synthetic regression only. No gate runner import."""
import copy
import importlib.abc
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent


class NoV5(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if 'automatic_region_certification_v5' in fullname:
            raise RuntimeError('V5 import forbidden in evaluator gate')


sys.meta_path.insert(0, NoV5())
forbidden = {'all-pages-source-inventory.json', 'eligible-positive-set.json',
             'resume-eligible-positive-set.json', 'virgin-safety-set.json',
             'positive-confirmation-contract.json', 'development-regression-contract.json',
             'virgin-safety-contract.json'}


def no_corpus(event, args):
    if event == 'open' and isinstance(args[0], (str, bytes)):
        path = Path(args[0])
        if path.name in forbidden or path.suffix.lower() == '.pdf':
            raise RuntimeError('Corpus access forbidden: ' + str(path))


sys.addaudithook(no_corpus)
import synthetic_support as support


def write(name, data):
    (HERE / name).write_text(json.dumps(data, indent=2) + '\n')


def main():
    corrected = support.load_corrected()
    old = support.legacy_namespace()['source_audit']
    cases = json.loads((HERE / 'synthetic-evaluator-cases.json').read_text())
    results = [support.evaluate(corrected.source_audit,c) for c in cases]
    write('synthetic-results-after.json', results)
    assert all(r['passed'] for r in results)
    checks = {
        'wrong_target': 'false_cross_page_links',
        'forward_continuation': 'missing_reciprocal_links',
        'conflicting_editorial_ids': 'false_cross_page_links',
        'explicit_no_link': 'false_cross_page_links',
        'false_local_complete': 'false_editorial_completions',
        'unresolved_proven_link': 'unsafe_false_identity_proven',
    }
    mutations = [dict(name=r['name'], metric=checks[r['name']],
                      actual=r['metrics'][checks[r['name']]], detected=r['metrics'][checks[r['name']]]>0)
                 for r in results if r['name'] in checks]
    write('mutation-results.json', dict(total=len(mutations), all_detected=all(m['detected'] for m in mutations), results=mutations))
    assert all(m['detected'] for m in mutations)
    archive = json.loads((support.RUNNER.parent / 'resume-evaluator-audit.json').read_text())
    c = dict(name='stored_resume_synthetic_audit', rows=archive['synthetic_rows'],
             canonical=archive['synthetic_canonical'],
             inventory=[dict(page=p, boxes=[]) for p in (10,11)], expected={})
    before = support.evaluate(old,c)['metrics']
    assert before == archive['metrics']
    after = support.evaluate(corrected.source_audit,c)['metrics']
    delta = {k:after[k]-v for k,v in before.items()}
    assert {k:v for k,v in delta.items() if v} == dict(false_cross_page_links=-1,false_editorial_completions=-1)
    regression=[dict(name=c['name'], before=before, after=after, existing_metric_deltas=delta, passed=True)]
    # Safety controls use synthetic copies only; no stored holdout output is needed.
    for field,value,metric in [
        ('source_line_ids',[[99,99]],'unsafe_false_provenance_certifications'),
        ('source_line_ids',[[99,99]],'unsafe_false_certifications'),
        ('linked_region_ids',[],'false_identity_proven'),
        ('identity_state','UNRESOLVED','inconsistent_identity_state'),
    ]:
        c=copy.deepcopy(cases[3]);c['rows'][0][field]=value
        bm=support.evaluate(old,c)['metrics'];am=support.evaluate(corrected.source_audit,c)['metrics']
        assert am[metric] == bm[metric] > 0
        regression.append(dict(name=metric,before=bm[metric],after=am[metric],delta=0,passed=True))
    write('legacy-regression-results.json', dict(source='previous stored synthetic evaluator audit; never corpus results', results=regression, passed=True))
    assert not any('automatic_region_certification_v5' in n for n in sys.modules)
    write('synthetic-summary.json',dict(cases=len(results),passed=sum(r['passed'] for r in results),failed=sum(not r['passed'] for r in results),
          false_negatives=sum(v['actual']<v['expected'] for r in results for v in r['mismatches'].values()),
          false_positives=sum(v['actual']>v['expected'] for r in results for v in r['mismatches'].values()),
          import_guard='V5 imports forbidden',corpus_guard='holdout contracts/sets/inventory and PDFs forbidden',V5_imported=False,V5_executed=False))
    print(f'{len(results)}/{len(results)} synthetic cases PASS; {len(mutations)}/{len(mutations)} mutations detected; legacy regression PASS')


if __name__ == '__main__':
    main()
