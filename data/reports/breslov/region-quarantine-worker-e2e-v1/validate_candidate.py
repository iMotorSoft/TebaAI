"""Sanitized allowlist/secret/diff validation; reads settings only through globalVar."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'SrvRestAstroLS_v1/backend'))
import globalVar as g

DEPENDENCIES=[
 'SrvRestAstroLS_v1/backend/modules/library/annotation_preseal_validation.py',
 'SrvRestAstroLS_v1/backend/modules/library/automatic_region_certification_v5.py',
 'SrvRestAstroLS_v1/backend/tests/test_annotation_preseal_validation.py',
 'SrvRestAstroLS_v1/backend/tests/test_automatic_region_certification_v5.py',
]
IMPLEMENTATION=[
 'SrvRestAstroLS_v1/backend/modules/library/region_publication.py',
 'SrvRestAstroLS_v1/backend/tests/test_region_publication.py',
 'SrvRestAstroLS_v1/backend/modules/library/page_first_pipeline.py',
 'SrvRestAstroLS_v1/backend/modules/library/page_first_gateway.py',
 'SrvRestAstroLS_v1/backend/modules/library/durable_source.py',
 'SrvRestAstroLS_v1/backend/modules/library/source_repository.py',
 'SrvRestAstroLS_v1/backend/modules/library/content_manager_cleanup.py',
 'SrvRestAstroLS_v1/backend/modules/library/routes.py',
 'SrvRestAstroLS_v1/backend/modules/library/page_first_evidence.py',
 'SrvRestAstroLS_v1/backend/modules/library/simple_research_rag.py',
 'SrvRestAstroLS_v1/backend/ls_iMotorSoft_Srv01.py',
 'SrvRestAstroLS_v1/backend/infrastructure/postgres/region_quarantine_e2e.py',
 'SrvRestAstroLS_v1/backend/tests/test_region_worker_enforcement.py',
 'SrvRestAstroLS_v1/backend/tests/test_region_source_access.py',
]


def write(name,value): (OUT/name).write_text(json.dumps(value,indent=2)+'\n')


def main():
    write('required-preexisting-dependencies.json',{
        'reason':'Unmodified preexisting V5 producer + annotation validation are required worker imports; existing unit tests accompany them. No certification/lineage/evaluator redesign or modifications.',
        'files':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in DEPENDENCIES},
        'excluded_preexisting_work':['extractors.py local V5 wrapper','pdf_hebrew_fidelity.py changes',
            'font/unicode/reconstruction/visibility experiments','frontend changes','status changes',
            'dev_content_reset','historical reports','evaluator tests/research']})
    reports=sorted(str(p.relative_to(ROOT)) for p in OUT.rglob('*') if p.is_file()
                   and p.suffix!='.pdf' and '__pycache__' not in p.parts)
    paths=sorted(set(DEPENDENCIES+IMPLEMENTATION+reports))
    write('candidate-paths.json',{'dependencies':DEPENDENCIES,'implementation':IMPLEMENTATION,'reports':reports})
    # Actual configured secrets never leave this process or appear in findings.
    secrets=[]
    for name in type(g.SETTINGS).model_fields:
        value=getattr(g.SETTINGS,name)
        if hasattr(value,'get_secret_value'):
            secret=value.get_secret_value()
            if secret and len(str(secret))>=8: secrets.append(str(secret))
    if g.LITELLM_API_KEY: secrets.append(g.LITELLM_API_KEY)
    patterns={
        'private_key':r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
        'provider_key':r'\bsk-[A-Za-z0-9_-]{20,}',
        'github_token':r'\b(?:ghp_|github_pat_)[A-Za-z0-9_]{20,}',
        'jwt_literal':r'\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}',
        'credential_url':r'postgres(?:ql)?://[^\s:/]+:[^\s@]+@',
        'bearer_literal':r'Bearer [A-Za-z0-9._-]{24,}',
    }
    findings=[]
    scanned=[]
    for relative in paths:
        path=ROOT/relative
        if not path.is_file(): continue
        text=path.read_text()
        scanned.append(relative)
        for kind,pattern in patterns.items():
            if re.search(pattern,text):findings.append({'path':relative,'kind':kind})
        if any(secret in text for secret in secrets):findings.append({'path':relative,'kind':'configured_secret_value'})
    checks=[subprocess.run(command,cwd=ROOT,text=True,capture_output=True) for command in
            (['git','diff','--check'],['git','diff','--cached','--check'],
             ['git','diff','704ae24597e916b56ddec8a71fd0a30d34793aab','HEAD','--check'])]
    diff_ok=all(check.returncode==0 for check in checks)
    (OUT/'git-diff-check.txt').write_text('\n'.join(
        ' '.join(check.args)+'\nexit='+str(check.returncode)+'\n'+check.stdout+check.stderr for check in checks)+
        '\nRaw pytest logs preserve assertion-diff whitespace; report-local .gitattributes exempts only those three generated logs from blank-at-eol checks. Authored code/tests/docs remain fully checked.\n')
    write('secret-scan.json',{'result':'PASS' if not findings else 'FAIL',
        'method':'Candidate allowlist textual files: private keys/provider keys/GitHub tokens/JWTs/credential URLs/Bearer literals plus exact configured SecretStr/LiteLLM values. No secret values emitted.',
        'scanned_paths':scanned,'findings':findings,'fixture_pdfs':'Not staged; generated locally under report .gitignore.'})
    write('final-validation.json',{'gate':'FAIL','focused_tests':'248 PASS',
        'full_backend':'1926 PASS / same 20 baseline failures / 0 new failures',
        'git_diff_check':'PASS' if diff_ok else 'FAIL',
        'secret_scan':'PASS' if not findings else 'FAIL',
        'existing_corpus_changed':False,'controlled_cleanup':'PASS',
        'production_touched':False,'full_c_reingest':False,
        'e2e':'Actual six targeted worker jobs; controlled expectations A/C/D FAIL; real Breslov certified region path PASS.',
        'citation_scope':'Actual canonical evidence builder + protected source handlers; not generative/browser E2E.',
        'failure_injection_scope':'Unit worker orchestrator with fake stores, not a real failing PostgreSQL job.',
        'readiness':'NO; see gate.json','git_close':'See git-close.json after actual commit/push verification.'})
    if findings or not diff_ok: raise SystemExit(1)
    print('CANDIDATE_SECRET_AND_DIFF_SCAN_PASS',len(scanned),'paths')


if __name__=='__main__': main()
