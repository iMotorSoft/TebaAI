"""Heuristic secret scan for the C controlled reingest plan report directory.

Local regex scan only; gitleaks/detect-secrets are not installed. Not a guarantee
of absence, but it fails loudly on credential-shaped strings in the evidence.
"""
import json
import re
from pathlib import Path

OUT = Path(__file__).parent
PATTERNS = {
    'aws_access_key_id': re.compile(r'AKIA[0-9A-Z]{16}'),
    'private_key_block': re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----'),
    'jwt_like': re.compile(r'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}'),
    'bearer_token': re.compile(r'(?i)bearer\s+[A-Za-z0-9._\-]{24,}'),
    'assigned_password': re.compile(
        r'(?i)\b(pass(word)?|secret|api[_-]?key|token)\b\s*[:=]\s*["\']?[A-Za-z0-9/+_.\-]{12,}'
    ),
    'dsn_with_password': re.compile(r'postgres(?:ql)?://[^\s:@]+:[^\s:@]+@'),
}
TEXT_SUFFIXES = {'.md', '.json', '.py', '.txt', '.jsonl', '.sh', '.yaml', '.yml'}


def main() -> None:
    findings = []
    scanned = 0
    for path in sorted(OUT.rglob('*')):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if path.name == 'secret-scan.json':
            continue
        scanned += 1
        text = path.read_text(errors='ignore')
        for name, pattern in PATTERNS.items():
            for match in pattern.finditer(text):
                line = text[: match.start()].count('\n') + 1
                snippet = match.group(0)
                redacted = snippet[:4] + '***'
                findings.append({
                    'file': str(path.relative_to(OUT)),
                    'line': line,
                    'pattern': name,
                    'snippet_redacted': redacted,
                })
    payload = {
        'status': 'FAIL' if findings else 'PASS',
        'files_scanned': scanned,
        'scope': 'this report directory only; preexisting user worktree files not scanned or modified',
        'method': 'local heuristic regex scan; gitleaks/detect-secrets not installed; not a guarantee of absence',
        'findings': findings,
    }
    (OUT / 'secret-scan.json').write_text(json.dumps(payload, indent=2) + '\n')
    print('SECRET_SCAN', payload['status'], scanned, 'files', len(findings), 'findings')


if __name__ == '__main__':
    main()
