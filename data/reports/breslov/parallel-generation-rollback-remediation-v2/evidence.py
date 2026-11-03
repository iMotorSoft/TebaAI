"""Evidence preparation/freezing and deterministic post-run integrity checks."""
import hashlib,json,re,subprocess,sys
import xml.etree.ElementTree as ET
from datetime import datetime,timezone
from pathlib import Path
R=Path(__file__).resolve().parent
ROOT=R.parents[3]
BACKEND=ROOT/'SrvRestAstroLS_v1/backend'

def save(n,v): (R/n).write_text(json.dumps(v,indent=2,ensure_ascii=True)+'\n')
def load(n): return json.loads((R/n).read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def git(*a): return subprocess.check_output(['git',*a],cwd=ROOT,text=True).strip()
def relative(p): return str(p.relative_to(ROOT))
def parse(name):
    result={'PASS':0,'FAIL':0,'ERROR':0,'SKIP':0,'failing_node_ids':[],'error_node_ids':[]}
    for t in ET.parse(R/name).iter('testcase'):
        status='FAIL' if t.find('failure') is not None else 'ERROR' if t.find('error') is not None else 'SKIP' if t.find('skipped') is not None else 'PASS'
        result[status]+=1
        if status in ('FAIL','ERROR'):
            classname=t.attrib['classname']
            parts=classname.split('.')
            # Existing suite uses tests.test_module[.TestClass] JUnit naming.
            module=next(i for i,p in enumerate(parts) if p.startswith('test_'))
            node='/'.join(parts[:module+1])+'.py::'+'::'.join(parts[module+1:]+[t.attrib['name']])
            result['failing_node_ids' if status=='FAIL' else 'error_node_ids'].append(node)
    for key in ('failing_node_ids','error_node_ids'): result[key]=sorted(set(result[key]))
    return result

def prepare():
    save('pre-freeze-backend-baseline.json',parse('pre-freeze-backend.xml'))
    assert load('preflight-postgres-binding.json')['UUID_TEXT_BINDING_PREFLIGHT']=='PASS'
    assert load('preflight-schema.json')['EXPECTED_TYPES']=='YES'
    assert load('preflight-positive-flow.json')['rollback']=='operational'
    assert load('preflight-negative-fixtures.json')['negative_controls_operational']
    assert not any(load('preflight-cleanup.json')['remaining'].values())
    save('preflight-summary.json',{'complete':True,'certifying':False,'completed_at':datetime.now(timezone.utc).isoformat(),
        'product_changes':0,'harness_changes_before_freeze':[
            'probe: explicit ::text to resolve PostgreSQL untyped text parameter before ::uuid',
            'ACTIVE cleanup: expect distinct ACTIVE rejection message, not retained-INACTIVE message',
            'add unique ACTIVE index assertion and real rollback Python-call profiling'],
        'discarded_fixture_evidence':'all preflight results excluded from certification; audit retained by design',
        'final_preflight_output':'preflight-harness-output-final.txt'})
    # Freeze all versionable backend inputs, including pre-existing Foundation dependencies.
    tracked=git('ls-files').splitlines()
    untracked=git('ls-files','--others','--exclude-standard').splitlines()
    backend=[p for p in tracked+untracked if p.startswith('SrvRestAstroLS_v1/backend/') and (ROOT/p).is_file()]
    extras=[relative(R/n) for n in ['lifecycle_harness.py','evidence.py','capture_initial.py','certification-contract.json','rollback-eligibility-contract.md']]
    freeze_paths=sorted(set(backend+extras))
    initial=load('worktree-before.json')
    changed=[]
    for line in initial['status'].splitlines():
        if line.startswith('?? '): continue
        changed.append(line[3:])
    inventory=[]
    for path in sorted(set(freeze_paths+changed+initial['untracked'])):
        if path.endswith('/'): continue
        p=ROOT/path
        if not p.is_file(): continue
        if path=='SrvRestAstroLS_v1/backend/modules/library/generation.py': category='PRODUCT_FIX'
        elif path=='SrvRestAstroLS_v1/backend/tests/test_generation_rollback_remediation.py': category='CERTIFICATION_TEST'
        elif path==relative(R/'lifecycle_harness.py'): category='FIXTURE_HELPER'
        elif path.startswith(relative(R)+'/'): category='REPORT_ONLY'
        else: category='PREEXISTING_UNRELATED'
        inventory.append({'path':path,'classification':category,'sha256':sha(p),
            'frozen':path in freeze_paths,'note':'Existing candidate dependency frozen, not modified by V2' if category=='PREEXISTING_UNRELATED' and path in freeze_paths else ''})
    save('certification-candidate-paths.json',{'paths':inventory,'scope':'PRODUCT_FIX and CERTIFICATION_TEST preexist V2; no production/test changes by V2; REPORT_ONLY evidence.py controls frozen evidence metrics; all backend dependencies frozen defensively'})
    freeze_paths.append(relative(R/'certification-candidate-paths.json'))
    hashes={p:sha(ROOT/p) for p in freeze_paths}
    save('frozen-manifest.json',{'algorithm':'SHA-256','paths':hashes,'configuration_policy':'same inherited environment and cwd; no env/config changes; DB config from globalVar only',
        'fresh_fixture_policy':'uuid4 per Phase B invocation, no preflight IDs reused; rules in frozen lifecycle_harness.py'})
    (R/'frozen-hashes.txt').write_text(''.join(h+'  '+p+'\n' for p,h in hashes.items()))
    save('frozen-at.json',{'timestamp':datetime.now(timezone.utc).isoformat(),'phase':'B','preflight_completed':True,'production_modifications_by_v2':0})
    print('FROZEN',len(hashes),'files',load('frozen-at.json')['timestamp'])

def finish():
    hashes=load('frozen-manifest.json')['paths']
    changed=[p for p,h in hashes.items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]
    historical=load('historical-hashes-before.json')
    historical_changed=[p for p,h in historical.items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]
    preserved=[r for r in load('certification-candidate-paths.json')['paths'] if r['classification']=='PREEXISTING_UNRELATED']
    unrelated_changed=[r['path'] for r in preserved if not (ROOT/r['path']).is_file() or sha(ROOT/r['path'])!=r['sha256']]
    save('final-frozen-hash-check.json',{'unchanged':not changed,'changed_paths':changed,'files_verified':len(hashes),'historical_changed_paths':historical_changed,'preexisting_unrelated_changed_paths':unrelated_changed,'post_freeze_mutations':len(changed)})
    baseline=load('pre-freeze-backend-baseline.json')
    final=parse('final-backend.xml'); save('final-backend-results.json',final)
    focused=parse('focused.xml'); foundation=parse('foundation-regression.xml')
    newfail=sorted(set(final['failing_node_ids'])-set(baseline['failing_node_ids']))
    newerror=sorted(set(final['error_node_ids'])-set(baseline['error_node_ids']))
    foundation_newfail=sorted(set(foundation['failing_node_ids'])-set(baseline['failing_node_ids']))
    foundation_newerror=sorted(set(foundation['error_node_ids'])-set(baseline['error_node_ids']))
    save('backend-baseline-comparison.json',{'baseline':baseline,'final':final,'new_fail_node_ids':newfail,'new_error_node_ids':newerror,
        'foundation_regression':foundation,'foundation_new_fail_node_ids':foundation_newfail,'foundation_new_error_node_ids':foundation_newerror,
        'note':'Pre-existing baseline failures/errors reproduced explicitly; this does NOT certify complete Foundation V2'})
    p=load('preflight-certification-fixture-identifiers.json'); c=load('certification-fixture-identifiers.json')
    pfids={p['logical_document_id'],p['cross_logical_document_id'],p['collection_id'],*p['generations'].values(),*p['documents'].values()}
    certids={c['logical_document_id'],c['cross_logical_document_id'],c['collection_id'],*c['generations'].values(),*c['documents'].values()}
    fresh=not(pfids&certids)
    diff=subprocess.run(['git','diff','--check'],cwd=ROOT,capture_output=True,text=True)
    (R/'git-diff-check.txt').write_text('exit='+str(diff.returncode)+'\n'+diff.stdout+diff.stderr)
    # Scan evidence without ever writing matched secret values.
    patterns=[r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----',r'\bgh[pousr]_[A-Za-z0-9]{30,}',
        r'\bsk-[A-Za-z0-9_-]{24,}',r'(?:postgres(?:ql)?|https?)://[^\s/:]+:[^\s/@]+@',
        r'(?i)["\']?(?:password|api_key|secret|token)["\']?\s*[:=]\s*["\'][^"\'\s]{12,}["\']']
    hits=[]; scanned=[]
    for path in sorted(R.iterdir()):
        if not path.is_file() or path.suffix not in ('.py','.md','.txt','.json','.xml'): continue
        scanned.append(path.name)
        for i,pat in enumerate(patterns):
            if re.search(pat,path.read_text(errors='replace')): hits.append({'path':path.name,'rule':i})
    save('secret-scan.json',{'result':'PASS' if not hits else 'FAIL','files':scanned,'hits':hits,'matched_values_suppressed':True})
    valid=[]
    for path in sorted(R.glob('*.json')):
        json.loads(path.read_text()); valid.append(path.name)
    checks={'frozen_hashes_unchanged':not changed,'historicals_preserved':not historical_changed,'unrelated_work_preserved':not unrelated_changed,
        'fresh_certification_fixture':fresh,'focused_all_pass':focused['FAIL']==focused['ERROR']==0,
        'no_new_full_backend_failures':not newfail,'no_new_full_backend_errors':not newerror,
        'no_new_foundation_failures':not foundation_newfail,'no_new_foundation_errors':not foundation_newerror,
        'git_diff_check_pass':diff.returncode==0,'secret_scan_pass':not hits,'report_json_valid':True,
        'certification_cleanup':not any(load('certification-cleanup.json')['remaining'].values()),
        'current_c_preserved':load('current-c-readonly-check.json')['result']=='PASS'}
    for name in ['positive-cutover-results.json','positive-rollback-results.json','audit-results.json','atomicity-results.json','idempotency-results.json']:
        checks[name]=load(name)['result']=='PASS'
    outcome='INVALID' if changed else 'PASS' if all(checks.values()) else 'BLOCKED'
    gate='TEBAAI_BRESLOV_PARALLEL_GENERATION_ROLLBACK_REMEDIATION_V2_'+outcome
    save('final-validation.json',{'gate':gate,'checks':checks,'focused':focused,'foundation':foundation,'valid_json_files':valid,'branch':git('branch','--show-current')})
    save('gate.json',{'gate':gate,'result':outcome,'ROLLBACK_FIX_CERTIFIED':outcome=='PASS',
        'READY_FOR_FOUNDATION_V2_PUBLICATION_REVALIDATION':outcome=='PASS',
        'READY_FOR_C_PARALLEL_GENERATION_SAFETY_V2':False,'READY_FOR_C_REINGEST_EXECUTION':False,
        'C_REINGEST_EXECUTED':False,'FOUNDATION_V2_PUBLISHED':False,'COMMIT':False,'PUSH':False})
    print(json.dumps({'gate':gate,'checks':checks,'baseline':baseline,'final':final,'focused':focused,'foundation':foundation},indent=2))

if __name__=='__main__':
    {'freeze':prepare,'finish':finish}[sys.argv[1]]()
