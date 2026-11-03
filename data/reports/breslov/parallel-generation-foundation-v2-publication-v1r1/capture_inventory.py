"""Read-only repository inventory; writes only this rerun's evidence directory."""
import hashlib
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path.cwd()
R = Path(__file__).resolve().parent
PREFIX = R.relative_to(ROOT).as_posix() + '/'

def git(*args):
    return subprocess.check_output(['git', *args], text=True).rstrip('\n')

def save(name, value):
    (R / name).write_text(json.dumps(value, indent=2) + '\n')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

readers = {'hybrid_search.py', 'text_search.py', 'simple_research_repository.py',
           'relation_qa_repository.py', 'source_repository.py'}
seeds = subprocess.check_output(['rg', '-l',
    'library_(visible_documents|document_generations|logical_document_active_generations|logical_documents|generation_activation_audit)|modules.library.generation|_register_generation|_activate_candidate_generation',
    'SrvRestAstroLS_v1/backend/modules', 'SrvRestAstroLS_v1/backend/tests',
    'SrvRestAstroLS_v1/backend/db/migrations/043_generation_foundation.sql'], text=True).splitlines()
# Cleanup and vector-reader regression tests also depend on the changed contract.
seeds += ['SrvRestAstroLS_v1/backend/tests/test_content_manager_cleanup.py',
          'SrvRestAstroLS_v1/backend/tests/test_library_search_hybrid_milvus_alias.py',
          'SrvRestAstroLS_v1/backend/modules/library/durable_source.py']
seeds = sorted(set(seeds))

def classify(path):
    p = Path(path)
    if path.startswith(PREFIX): return 'PUBLICATION_RERUN_REPORT'
    if path.startswith('data/reports/breslov/parallel-generation-rollback-remediation-'):
        return 'ROLLBACK_REMEDIATION_V2' if '/parallel-generation-rollback-remediation-v2/' in path else 'PREEXISTING_UNRELATED'
    if path.startswith('data/reports/breslov/parallel-generation-foundation-v2/'):
        return 'FOUNDATION_V2_REPORT'
    if path in seeds:
        if p.suffix == '.sql': return 'FOUNDATION_V2_MIGRATION'
        if '/tests/' in path: return 'ROLLBACK_REMEDIATION_V2' if 'rollback_remediation' in path else 'FOUNDATION_V2_TEST'
        if p.name in readers: return 'FOUNDATION_V2_READER'
        return 'FOUNDATION_V2_PRODUCT'
    return 'PREEXISTING_UNRELATED'

status = git('status', '--short', '--untracked-files=all')
untracked = git('ls-files', '--others', '--exclude-standard').splitlines()
modified = git('diff', '--name-only').splitlines()
cached = git('diff', '--cached', '--name-only').splitlines()
paths = sorted(set(untracked + modified + cached))
entries = [{'path': p, 'classification': classify(p), 'sha256': sha(ROOT / p)} for p in paths if (ROOT / p).is_file()]
save('worktree-before.json', {'captured_at': datetime.now(timezone.utc).isoformat(),
    'note': 'Only this capture_inventory.py was created before capture. No preexisting path changed.',
    'status_short': status, 'diff_name_status': git('diff', '--name-status'),
    'cached_name_status': git('diff', '--cached', '--name-status'), 'untracked': untracked,
    'paths': entries, 'counts': dict(Counter(e['classification'] for e in entries)),
    'classification_scope': 'Worktree ownership inventory, not proof of completed dependency closure.'})
base = git('rev-parse', 'HEAD')
remote = git('ls-remote', 'origin', 'refs/heads/feature/console-backend-core').split()[0]
tracking = git('rev-parse', 'origin/feature/console-backend-core')
save('baseline-git-state.json', {'branch': git('branch', '--show-current'),
    'LOCAL_HEAD': base, 'TRACKING_HEAD': tracking, 'LS_REMOTE_HEAD': remote,
    'BASE_REMOTE_HEAD': base, 'equal': base == remote == tracking})
tracked = set(git('ls-files').splitlines())
save('foundation-v2-candidate-paths.json', {'status': 'PROVISIONAL_NOT_FROZEN',
    'method': 'Independent production/schema/reference search plus cleanup, vector regression and source durability roots; not copied from historical allowlist.',
    'paths': seeds, 'count': len(seeds), 'dependency_closure_complete': False})
save('foundation-v2-versioning-gap.json', {'status': 'ROOT_PATHS_ONLY', 'paths': [
    {'path': p, 'state': 'MISSING' if not (ROOT / p).is_file() else 'UNTRACKED' if p not in tracked else 'TRACKED_MODIFIED' if p in modified else 'TRACKED_UNCHANGED'} for p in seeds],
    'missing_root_paths': sum(not (ROOT / p).is_file() for p in seeds),
    'complete_dependency_closure_certified': False})
historical = {}
for directory in ['parallel-generation-foundation-v2-publication-v1',
                  'parallel-generation-rollback-remediation-v1',
                  'parallel-generation-rollback-remediation-v2']:
    for p in sorted((R.parent / directory).rglob('*')):
        if p.is_file(): historical[p.relative_to(ROOT).as_posix()] = sha(p)
save('historical-hashes-before.json', historical)
cert = R.parent / 'parallel-generation-rollback-remediation-v2'
manifest = json.loads((cert / 'frozen-manifest.json').read_text())['paths']
changed = [p for p, h in manifest.items() if not (ROOT / p).is_file() or sha(ROOT / p) != h]
save('rollback-v2-prerequisite.json', {'historical_gate': json.loads((cert / 'gate.json').read_text()),
    'historical_hash_check': json.loads((cert / 'final-frozen-hash-check.json').read_text()),
    'current_certified_hashes_verified': len(manifest), 'current_changed_paths': changed,
    'ROLLBACK_FIX_CERTIFIED': not changed,
    'note': 'Prerequisite integrity only; not a new Foundation certification.'})
print(json.dumps({'root_paths': len(seeds), 'counts': dict(Counter(e['classification'] for e in entries)), 'certified_changed_paths': changed}))
