"""Close an early failed run without fabricating downstream certification."""
import hashlib
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path.cwd()
R = Path(__file__).resolve().parent

def save(name, obj):
    (R / name).write_text(json.dumps(obj, indent=2) + '\n')

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def git(*args):
    return subprocess.check_output(['git', *args], text=True).strip()

inventory = json.loads((R / 'worktree-before.json').read_text())
history = json.loads((R / 'historical-hashes-before.json').read_text())
changed_history = [p for p,h in history.items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]
changed_preexisting = [e['path'] for e in inventory['paths']
    if e['classification'] != 'PUBLICATION_RERUN_REPORT'
    and (not (ROOT/e['path']).is_file() or sha(ROOT/e['path'])!=e['sha256'])]
tests = ET.parse(R / 'focused.xml')
counts = {'PASS':0,'FAIL':0,'ERROR':0,'SKIP':0}
failures, errors = [], []
for case in tests.iter('testcase'):
    node = case.attrib['classname'].replace('.', '/') + '.py::' + case.attrib['name']
    if case.find('error') is not None:
        counts['ERROR'] += 1
        errors.append(node)
    elif case.find('failure') is not None:
        counts['FAIL'] += 1
        failures.append(node)
    elif case.find('skipped') is not None: counts['SKIP'] += 1
    else: counts['PASS'] += 1
save('backend-results.json', {'focused':counts,'failing_node_ids':failures,'error_node_ids':errors,
    'full_backend_baseline':'NOT_RUN_EARLY_STOP','full_backend_frozen':'NOT_RUN_NO_FREEZE',
    'new_fail_node_ids':None,'new_error_node_ids':None,'known_reproduced_full_baseline_nodes':None})
preflight = json.loads((R/'preflight-results.json').read_text())
preflight.update(status='FAIL_PRODUCT_REGISTRATION',fixture_suites=counts,
    note='Service availability passed; actual product registration failed before freeze. No fixture/product changes made.')
save('preflight-results.json',preflight)
save('foundation-v2-dependency-closure.json', {'status':'NOT_COMPLETED_EARLY_STOP',
    'root_inventory':'foundation-v2-candidate-paths.json','missing_required_dependencies':None,
    'complete_dependency_closure':False,'reason':'Real product integration defect reproduced in preflight; no publication candidate frozen.'})
save('backend-baseline-comparison.json', {'status':'NOT_RUN_EARLY_STOP',
    'new_FAIL_node_ids':None,'new_ERROR_node_ids':None,
    'historical_counts_reused_as_current_baseline':False})
check = subprocess.run(['git','diff','--check'], text=True, capture_output=True)
(R/'git-diff-check.txt').write_text('exit_code='+str(check.returncode)+'\n'+check.stdout+check.stderr)
# Candidate evidence only, not a secret certification of an unconstructed stage allowlist.
patterns = {
    'private_key':r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
    'openai_style_key':r'\bsk-[A-Za-z0-9_-]{24,}',
    'github_token':r'\bgh[pousr]_[A-Za-z0-9]{30,}',
    'credentialed_postgres_url':r'postgres(?:ql)?://[^\s:/]+:[^\s@]+@',
    'authorization_bearer':r'(?i)authorization\s*[:=]\s*[\"\']?Bearer\s+[A-Za-z0-9._-]{20,}',
    'assigned_secret':r'(?i)(?:password|api_key|access_token|refresh_token)\s*[\"\']?\s*[:=]\s*[\"\'][^\"\'\s]{8,}[\"\']',
    'cookie_value':r'(?i)(?:set-cookie|cookie)\s*:\s*[a-z_]+=\S{16,}',
}
findings=[]
files=sorted(p for p in R.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
for p in files:
    for kind,pattern in patterns.items():
        if re.search(pattern,p.read_text(errors='replace')): findings.append({'path':str(p.relative_to(ROOT)),'kind':kind})
save('secret-scan.json',{'status':'PASS' if not findings else 'FAIL','scope':'Current rerun evidence files only; no paths intended for commit on FAIL.',
    'files_scanned':len(files),'checks':list(patterns),'findings':findings,'limitations':'Pattern-based, not an exhaustive secret detector.'})
regression=json.loads((R/'current-c-regression-results.json').read_text())
after=json.loads((R/'current-c-after.json').read_text())
save('final-frozen-hash-check.json',{'status':'NOT_APPLICABLE_NO_FREEZE','validated_frozen_bytes':False,
    'historical_changed_paths':changed_history,'preexisting_changed_paths':changed_preexisting,
    'historical_files_verified':len(history),'post_freeze_mutations':None})
gate={'gate':'TEBAAI_BRESLOV_PARALLEL_GENERATION_FOUNDATION_V2_PUBLICATION_V1R1_FAIL',
    'result':'FAIL','phase':'PREFLIGHT_BEFORE_FREEZE','reason':'GENERATION_REGISTRATION_FOREIGN_KEY_ORDER_DEFECT',
    'full_revalidation_completed':False,'candidate_frozen':False,'COMMIT':False,'PUSH':False,
    'FOUNDATION_V2_VALIDATED':False,'ROLLBACK_FIX_CERTIFIED':True,'FOUNDATION_V2_PUBLISHED':False,
    'FOUNDATION_V2_AUTHORITATIVE':False,'FRESH_AUTHORITATIVE_TREE_SELF_CONTAINED':False,
    'CURRENT_C_PRESERVED':regression['database_and_vector_snapshot_unchanged'],
    'READY_FOR_C_PARALLEL_GENERATION_SAFETY_V2':False,'READY_FOR_C_REINGEST_EXECUTION':False,
    'C_REINGEST_EXECUTED':False,'C_EXTRACTION_EXECUTED':False,'C_EMBEDDINGS_REGENERATED':False,'C_VECTORS_REBUILT':False}
save('gate.json',gate)
save('final-validation.json',{'result':'FAIL_EARLY_PREFLIGHT','product_defect_reproduced':True,
    'focused':counts,'full_backend':'NOT_RUN','all_downstream_publication_gates':'NOT_RUN',
    'freeze':'NOT_RUN','staging':'NOT_RUN','commit':False,'push':False,'fresh_tree':'NOT_RUN',
    'historical_evidence_preserved':not changed_history,'preexisting_worktree_preserved':not changed_preexisting,
    'product_test_fixture_edits':0,'git_diff_check_exit':check.returncode,
    'pattern_secret_scan':'PASS' if not findings else 'FAIL','current_c_chunks':after['chunk_count'],
    'current_c_vectors':after['vector_count'],'current_c_unchanged':gate['CURRENT_C_PRESERVED'],
    'durable_source_approved_sha':after['durable_source_sha256']=='440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a',
    'HEAD_unchanged':git('rev-parse','HEAD')=='9882b569e55513dc179eccdc1c465bf31b25cb6a',
    'index_unchanged':git('diff','--cached','--name-status')==inventory['cached_name_status'],
    'minimum_complete_publication_artifacts':'NOT_APPLICABLE_EARLY_FAILURE; absent downstream artifacts not fabricated'})
invalid=[]
for p in R.rglob('*.json'):
    try: json.loads(p.read_text())
    except (ValueError, OSError): invalid.append(str(p.relative_to(ROOT)))
save('json-validation.json',{'parser':'Python json.loads','invalid_report_json':len(invalid),'invalid_paths':invalid,
    'note':'This file also parsed after write.'})
json.loads((R/'json-validation.json').read_text())
assert not changed_history and not changed_preexisting and not invalid and check.returncode==0 and not findings
print(json.dumps({'focused':counts,'history_changed':len(changed_history),'preexisting_changed':len(changed_preexisting),
    'json_invalid':len(invalid),'secret_scan_findings':findings,'head':git('rev-parse','HEAD')}))
