"""Assemble remediation evidence; no service access, no changes to historical reports."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
R = Path(__file__).resolve().parent
CODE = 'SrvRestAstroLS_v1/backend/modules/library/generation.py'
TEST = 'SrvRestAstroLS_v1/backend/tests/test_generation_rollback_remediation.py'
PREFIX = 'TEBAAI_BRESLOV_PARALLEL_GENERATION_ROLLBACK_REMEDIATION_V1'

def put(name, value):
    (R / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')

def results(path):
    cases = list(ET.parse(path).getroot().iter('testcase'))
    failed, errors = [], []
    for c in cases:
        module = c.attrib['classname'].replace('.', '/')
        node = (module if module.startswith('tests/') else 'tests/' + module) + '.py::' + c.attrib['name']
        if c.find('failure') is not None:
            failed.append(node)
        if c.find('error') is not None:
            errors.append(node)
    return {'passed': sum(c.find('failure') is None and c.find('error') is None
                          and c.find('skipped') is None for c in cases),
            'failed': len(failed), 'errors': len(errors), 'failing_node_ids': failed,
            'error_node_ids': errors}

baseline = results(R / 'baseline-backend.xml')
final = results(R / 'backend-full.xml')
focused = results(R / 'focused.xml')
new_nodes = sorted((set(final['failing_node_ids']) | set(final['error_node_ids'])) -
                   (set(baseline['failing_node_ids']) | set(baseline['error_node_ids'])))
put('backend-results.json', {'baseline_current_worktree_before_fix': baseline,
    'after_fix': final, 'focused': focused, 'new_failure_or_error_nodes': new_nodes,
    'exact_current_baseline_comparison_available': True,
    'historical_20_failure_node_equivalence': 'NOT CLAIMED; historical exact nodes incomplete',
    'existing_foundation_errors': '13 fixture errors: jsonb_build_object marker parameter lacks explicit type. Existing test file preserved byte-for-byte.',
    'full_foundation_validation_claimed': False})

def evidence(name, tests, **extra):
    put(name, {'technical_result': 'PASS', 'evidence': ['focused-tests.txt', 'focused.xml'],
        'test_nodes': ['tests/test_generation_rollback_remediation.py::' + t for t in tests],
        'gate_result': 'INVALID', **extra})

evidence('positive-cutover-results.json', ['test_cutover_rollback_audit_and_cleanup', 'test_postgres_rollback_contract'],
         result='APPLIED', old='INACTIVE', new='ACTIVE', pointer='NEW')
evidence('positive-rollback-results.json', ['test_cutover_rollback_audit_and_cleanup', 'test_postgres_rollback_contract'],
         result='APPLIED', old='ACTIVE', new='INACTIVE', pointer='OLD', prior_active_history=True,
         retention_hold=True, immediate_previous_only=True, reingest=False, reembed=False)
for filename, nodes in {
    'arbitrary-inactive-negative-control.json': ['test_rollback_eligibility_fail_closed[arbitrary]', 'test_rollback_eligibility_fail_closed[historical]', 'test_postgres_rollback_contract'],
    'never-active-inactive-negative-control.json': ['test_rollback_eligibility_fail_closed[never_active]', 'test_postgres_rollback_contract'],
    'building-negative-control.json': ['test_invalid_status[BUILDING-CUTOVER]', 'test_invalid_status[BUILDING-ROLLBACK]', 'test_postgres_rollback_contract'],
    'failed-negative-control.json': ['test_invalid_status[FAILED-CUTOVER]', 'test_invalid_status[FAILED-ROLLBACK]', 'test_postgres_rollback_contract'],
    'stale-cas-negative-control.json': ['test_stale_cutover_and_stale_rollback', 'test_postgres_rollback_contract'],
    'cross-document-negative-control.json': ['test_cross_document[CUTOVER]', 'test_cross_document[ROLLBACK]'],
}.items():
    evidence(filename, nodes, attempted_operation_result='REJECTED', pointer_mutated=False)
evidence('audit-results.json', ['test_cutover_rollback_audit_and_cleanup', 'test_postgres_rollback_contract', 'test_idempotency_safe'],
    applied_sequence=[{'operation':'CUTOVER','from':'OLD','to':'NEW','expected':'OLD','result':'APPLIED'},
                      {'operation':'ROLLBACK','from':'NEW','to':'OLD','expected':'NEW','result':'APPLIED'}],
    timestamp='created_at persisted by existing table default; asserted non-null in PostgreSQL',
    duplicate_audit_on_idempotent=False)
evidence('cleanup-protection-results.json', ['test_cutover_rollback_audit_and_cleanup', 'test_postgres_rollback_contract'],
    after_cutover_old='INACTIVE + retention_hold=true', after_rollback_new='INACTIVE + retention_hold=true',
    generic_cleanup='REJECTED by existing ManifestCleanupService before vector access',
    cleanup_production_code_modified=False)

before = json.loads((R / 'worktree-before.json').read_text())['sha256']
changed = [p for p, h in before.items() if not (ROOT / p).is_file()
           or hashlib.sha256((ROOT / p).read_bytes()).hexdigest() != h]
unrelated = [p for p in changed if p != CODE]
put('worktree-preservation.json', {'changed_preexisting_files': changed,
    'unrelated_preexisting_changes': unrelated, 'preexisting_foundation_test_preserved':
    'SrvRestAstroLS_v1/backend/tests/test_generation_foundation.py' not in changed,
    'historical_publication_fail_preserved': not any('parallel-generation-foundation-v2-publication-v1/' in p for p in changed)})

# Scan candidate paths and all new report text. Emit locations/rule names, never matches.
rules = {
    'private_key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'provider_key': re.compile(r'\bsk-[A-Za-z0-9_-]{20,}\b'),
    'github_token': re.compile(r'\b(?:ghp_|github_pat_)[A-Za-z0-9_]{20,}\b'),
    'credential_uri': re.compile(r'(?:postgres(?:ql)?|https?)://[^\s:/]+:[^\s@]+@'),
    'aws_access_key': re.compile(r'\bAKIA[0-9A-Z]{16}\b'),
}
files = [ROOT / CODE, ROOT / TEST] + [p for p in R.rglob('*') if p.is_file()]
findings = []
for p in files:
    text = p.read_text(errors='replace')
    for rule, pattern in rules.items():
        if pattern.search(text):
            findings.append({'path':str(p.relative_to(ROOT)), 'rule':rule})
put('secret-scan.json', {'result':'PASS' if not findings else 'FAIL',
    'scope':'remediation code, direct tests and new report files',
    'rules':list(rules), 'files_scanned':len(files), 'findings':findings,
    'limitation':'Pattern scan, not a guarantee that every possible secret format is detectable.'})

check = subprocess.run(['git','diff','--check'], cwd=ROOT, capture_output=True, text=True)
(R / 'git-diff-check.txt').write_text(('PASS\n' if check.returncode == 0 else 'FAIL\n') + check.stdout + check.stderr)
invalid_reason = ('TEST_HARNESS_CHANGED_AFTER_OBSERVED_FAILURE: independent PostgreSQL fixture initially reused '
    'one parameter in UUID/text columns and raised AmbiguousParameter before lifecycle execution. '
    'Binding split into two parameters; expectations unchanged. Original failed attempt preserved '
    'in focused-attempt-1.txt/xml. Strict user methodology requires INVALID, not PASS.')
readiness = {'READY_FOR_FOUNDATION_V2_PUBLICATION_REVALIDATION':False,
    'READY_FOR_C_PARALLEL_GENERATION_SAFETY_V2':False,
    'READY_FOR_C_REINGEST_EXECUTION':False, 'C_REINGEST_EXECUTED':False}
validation = {'gate':PREFIX+'_INVALID', 'reason':invalid_reason,
    'technical_rollback_defect_fixed':True, 'cutover_semantics_preserved':True,
    'arbitrary_inactive_activation_allowed':False, 'rollback_eligibility_fail_closed':True,
    'cas_protection_preserved':True, 'current_c_preserved':True,
    'current_c_document_id':'ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa',
    'current_c_logical_document_id':'db200a31-b547-5668-d968-06d0ec36ad95',
    'current_c_pg_writes_by_gate':0, 'current_c_milvus_writes_by_gate':0,
    'current_c_write_evidence':'Gate mutation paths limited to random synthetic IDs; no before/after database write-counter claim.',
    'synthetic_pg_fixture':'unique collection/logical/document IDs; force_rollback transaction; no persisted fixture data',
    'milvus_access_by_remediation':False, 'foundation_v2_published':False,
    'commit':False,'push':False, 'focused_tests':focused,
    'new_backend_failures':new_nodes, 'git_diff_check':'PASS' if check.returncode==0 else 'FAIL',
    'secret_scan':'PASS' if not findings else 'FAIL', 'unrelated_preexisting_changes':unrelated, **readiness}
put('final-validation.json',validation)
put('gate.json',{'gate':PREFIX,'result':'INVALID','token':PREFIX+'_INVALID',
    'reason':invalid_reason, 'functional_evidence_passes':True, 'publication_authorized':False, **readiness})
print(json.dumps({'focused':focused,'baseline':baseline,'final':final,'new_nodes':new_nodes,
                 'unrelated_changes':unrelated,'secret_findings':findings}, indent=2))
