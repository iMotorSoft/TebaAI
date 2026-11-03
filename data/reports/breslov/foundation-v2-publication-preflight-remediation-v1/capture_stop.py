"""Capture a source-inspection stop; no services, product writes or certification."""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()

def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2) + '\n')

head = git('rev-parse', 'HEAD')
save('baseline-git-state.json', {
    'branch': git('branch', '--show-current'), 'LOCAL_HEAD': head,
    'TRACKING_HEAD': git('rev-parse', 'origin/feature/console-backend-core'),
    'LS_REMOTE_HEAD': git('ls-remote', 'origin', 'refs/heads/feature/console-backend-core').split()[0],
    'BASE_REMOTE_HEAD': head, 'expected_head': '9882b569e55513dc179eccdc1c465bf31b25cb6a',
    'fetch_completed': True,
})
paths = ['SrvRestAstroLS_v1/backend/modules/library/page_first_gateway.py',
         'SrvRestAstroLS_v1/backend/db/migrations/043_generation_foundation.sql',
         'data/reports/breslov/parallel-generation-foundation-v2-publication-v1r1/REPORT.md',
         'data/reports/breslov/parallel-generation-foundation-v2-publication-v1r1/gateway-registration-results.json']
save('v1r1-failure-attribution.json', {
    'method': 'current source and migration inspection; historical reproduction corroboration',
    'classification': 'FAIL_PRODUCT_DEFECT_DISCOVERED',
    'schema_live_reverified': False,
    'defects': [
        {'constraint': 'library_document_generations_run_id_fkey',
         'product_operation': 'persist_document_and_pages calls _register_generation at line 250 before inserting library_ingestion_runs_v2 at line 258',
         'fixture_only': False},
        {'constraint': 'library_document_generations_document_logical_fkey',
         'product_operation': '_register_generation inserts generation at line 342 before linking library_documents.logical_document_id at line 355',
         'fixture_only': False}],
    'source_hashes': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths},
    'historical_results_changed': False,
})
result = {
    'gate': 'TEBAAI_BRESLOV_FOUNDATION_V2_PUBLICATION_PREFLIGHT_REMEDIATION_V1_FAIL',
    'reason': 'FAIL_PRODUCT_DEFECT_DISCOVERED',
    'stop_rule': 'user section 7: stop on demonstrated product defect; do not repair product here',
    'certification': 'NOT_RUN', 'freeze': 'NOT_RUN', 'fixture_tests': 'NOT_RUN',
    'foundation_regression': 'NOT_RUN', 'full_backend': 'NOT_RUN',
    'durable_source_verification': 'NOT_RUN',
    'fixture_errors': None, 'targeted_prior_error_nodes_remaining': None,
    'PUBLICATION_PREFLIGHT_READY': False,
    'READY_FOR_FOUNDATION_V2_PUBLICATION_V1R2': False,
    'FOUNDATION_V2_PUBLISHED': False,
    'READY_FOR_C_PARALLEL_GENERATION_SAFETY_V2': False,
    'READY_FOR_C_REINGEST_EXECUTION': False, 'C_REINGEST_EXECUTED': False,
    'current_c_postgresql_writes_by_this_execution': 0,
    'current_c_milvus_writes_by_this_execution': 0,
    'current_c_state_comparison': 'NOT_RUN',
    'COMMIT': False, 'PUSH': False,
}
save('gate.json', result)
save('final-validation.json', result)
check = subprocess.run(['git', 'diff', '--check'], cwd=ROOT, capture_output=True, text=True)
(OUT / 'git-diff-check.txt').write_text(f'exit_code={check.returncode}\n{check.stdout}{check.stderr}')
invalid = []
for p in OUT.glob('*.json'):
    try:
        json.loads(p.read_text(), parse_constant=lambda s: (_ for _ in ()).throw(ValueError(s)))
    except ValueError:
        invalid.append(p.name)
save('json-validation.json', {'invalid_json_files': invalid, 'INVALID_JSON_FILES': len(invalid)})
print(result['gate'])
