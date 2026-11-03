"""Offline report validation, secret-pattern scan and tracked-diff preservation."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def main():
    generated = {'final-validation.json', 'changed-files.txt'}
    paths = [p for p in OUT.rglob('*') if p.is_file() and '__pycache__' not in p.parts
             and p.name not in generated]
    # Include existing tracked local modifications, but never persist their contents.
    paths += [ROOT / p for p in git('diff', '--name-only').decode().splitlines()]
    patterns = {
        'private_key': r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
        'credential_uri': r'(?:postgres(?:ql)?|https?)://[^\s:/]+:[^\s/@]+@',
        'provider_key': r'\b(?:sk-[A-Za-z0-9_-]{24,}|ghp_[A-Za-z0-9]{30,}|AKIA[A-Z0-9]{16})\b',
        'literal_secret_assignment': r'''(?im)^\s*(?:[A-Z_]*(?:PASSWORD|API_KEY|ACCESS_TOKEN|SECRET))\s*=\s*["'][^"'\r\n]{8,}["']\s*$''',
    }
    findings = []
    scanned = sorted(set(paths))
    for path in scanned:
        text = path.read_text(errors='replace')
        relative = str(path.relative_to(ROOT))
        baseline = subprocess.run(['git', 'show', f'HEAD:{relative}'], cwd=ROOT,
                                  capture_output=True).stdout.decode(errors='replace')
        for rule, pattern in patterns.items():
            for match in re.finditer(pattern, text):
                findings.append({'path': relative, 'rule': rule,
                                 'preexisting_in_head': match.group() in baseline})
    current = git('diff')
    original = Path('/tmp/tebaai-foundation-initial.diff').read_bytes()
    check = subprocess.run(['git', 'diff', '--check'], cwd=ROOT, capture_output=True)
    integrity = json.loads((OUT / 'integrity-verification.json').read_text())
    result = {
        'git_diff_check_pass': check.returncode == 0,
        'preexisting_tracked_diff_byte_identical': current == original,
        'initial_and_final_tracked_diff_sha256': hashlib.sha256(current).hexdigest(),
        'current_c_content_unchanged': integrity['current_c_content_unchanged'],
        'secret_scan': {'kind': 'pattern scan, not proof of absence of all possible secrets',
                        'files_scanned': len(scanned), 'findings': findings},
        'local_head': git('rev-parse', 'HEAD').decode().strip(),
        'tracking_head': git('rev-parse', '@{u}').decode().strip(),
        'commit_created': False, 'push_executed': False,
        'foundation_implementation_completed': False,
    }
    (OUT / 'final-validation.json').write_text(json.dumps(result, indent=2) + '\n')
    manifest = sorted(str(p.relative_to(ROOT)) for p in OUT.rglob('*')
                      if p.is_file() and '__pycache__' not in p.parts)
    if str((OUT / 'changed-files.txt').relative_to(ROOT)) not in manifest:
        manifest.append(str((OUT / 'changed-files.txt').relative_to(ROOT)))
    (OUT / 'changed-files.txt').write_text('\n'.join(sorted(manifest)) + '\n')
    assert check.returncode == 0 and current == original
    assert not any(not item['preexisting_in_head'] for item in findings)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
