"""OPTION_B execution; frozen evaluator/runner helpers, no independent positive claim."""
import importlib.util
import json
from pathlib import Path
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
OLD = OUT.parent / 'v5-hybrid-independent-confirmation-v1'
sys.path[:0] = [str(ROOT / 'SrvRestAstroLS_v1/backend'), str(OLD)]
spec = importlib.util.spec_from_file_location('frozen_runner', OLD / 'run_gate.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def write(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    from modules.library.automatic_region_certification_v5 import extract_pdf_region_certificates
    from modules.library.annotation_preseal_validation import canonical_document
    import hashlib
    assert hashlib.sha256(Path(runner.SOURCE).read_bytes()).hexdigest() == runner.SOURCE_SHA
    inventory = json.loads((OLD / 'all-pages-source-inventory.json').read_text())
    canonical, errors = canonical_document(inventory)
    safety = json.loads((OUT.parent / 'v5-hybrid-confirmation-resume-v2/safety-set.json').read_text())
    assert len(safety['pages']) == 85
    pages = extract_pdf_region_certificates(runner.SOURCE, pages=safety['pages'])
    rows = runner.certificate_rows(pages)
    metrics, violations, links = runner.source_audit(pages, rows, inventory, canonical, part='A')
    mandatory = []
    for pair in safety['mandatory_cross_page_pairs']:
        linked = any(r['linked_region_ids'] for r in rows
                     if r['pdf_page'] == pair['from'] and r['note_number'] == pair['note'])
        mandatory.append(dict(**pair, linked=linked, ok=not linked))
    ignored = {'valid_cross_page_relations', 'missed_true_links'}
    passed = not violations and all(p['ok'] for p in mandatory) and all(
        v == 0 for k, v in metrics.items() if k not in ignored)
    result = dict(status='PASS' if passed else 'FAIL', pages=85, regions=len(rows),
                  classification='PREOBSERVED_V5_UNEXPOSED_SAFETY_SET', metrics=metrics,
                  violations=violations, linked_pairs=links, mandatory_pairs=mandatory,
                  canonical_source_errors=errors, certificates=rows)
    write('phase-a-safety-results.json', result)
    print(json.dumps({k: result[k] for k in ('status', 'pages', 'regions', 'metrics')}, indent=2), flush=True)
    # Absolute stop on independent safety failure: no worker integration, no candidate edits.
    if not passed:
        return
    development = json.loads((OLD / 'development-regression-contract.json').read_text())
    numbers = sorted({p for case in development['positive'] + development['negative'] for p in (case['from'], case['to'])})
    rows = runner.certificate_rows(extract_pdf_region_certificates(runner.SOURCE, pages=numbers))
    cases = []
    for kind in ('positive', 'negative'):
        for pair in development[kind]:
            sources = [r for r in rows if r['pdf_page'] == pair['from'] and r['note_number'] == pair['note']]
            linked = [r for r in sources if r['linked_region_ids']]
            ok = False
            if kind == 'positive' and len(linked) == 1:
                s = linked[0]
                targets = [r for r in rows if r['pdf_page'] == pair['to'] and r['region_id'] in s['linked_region_ids']]
                ok = len(targets) == 1 and all([
                    s['identity_state'] == 'IDENTITY_PROVEN',
                    s['continuation_state'] == 'CONTINUES_NEXT_PAGE',
                    targets[0]['note_number'] == pair['note'],
                    targets[0]['identity_state'] == 'IDENTITY_PROVEN',
                    targets[0]['editorial_unit_id'] == s['editorial_unit_id'],
                    s['region_id'] in targets[0]['linked_region_ids'],
                ])
            elif kind == 'negative':
                ok = not linked and not any(r['identity_state'] == 'IDENTITY_PROVEN' for r in sources)
            cases.append(dict(**pair, kind=kind, ok=ok, observed_sources=sources))
    write('development-regression-results.json', dict(status='PASS' if all(c['ok'] for c in cases) else 'FAIL', evidence_class='KNOWN_REGRESSION_ONLY', cases=cases))
    print('Development regressions:', sum(c['ok'] for c in cases), '/7', flush=True)


if __name__ == '__main__':
    main()
