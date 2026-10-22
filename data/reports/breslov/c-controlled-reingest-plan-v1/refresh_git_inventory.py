"""Read-only Git/worktree inventory for the C controlled reingest plan gate.

Usage (from repo root):
    python3 data/reports/breslov/c-controlled-reingest-plan-v1/refresh_git_inventory.py <label>

Writes <label>-worktree.json next to this script. It never mutates the worktree:
no checkout, no reset, no clean, no stash, no add.
"""
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT = Path(__file__).parent


def git(*args: str) -> str:
    return subprocess.run(
        ['git', '-C', str(REPO), *args], capture_output=True, text=True, check=True
    ).stdout


def main(label: str) -> None:
    assert label in {'before', 'after'}
    status = git('status', '--short')
    files = git('ls-files', '-co', '--exclude-standard').splitlines()
    hashes = {}
    for rel in files:
        path = REPO / rel
        if not path.is_file():
            continue
        try:
            hashes[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            continue
    payload = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'label': label,
        'branch': git('branch', '--show-current').strip(),
        'head': git('rev-parse', 'HEAD').strip(),
        'status_short': status,
        'diff_name_status': git('diff', '--name-status'),
        'cached_name_status': git('diff', '--cached', '--name-status'),
        'preexisting_file_sha256': hashes,
        'preexisting_file_count': len(hashes),
        'note': (
            'Read-only Git inventory. No checkout/reset/clean/stash/add performed. '
            'Hashes cover tracked and untracked, non-ignored files at capture time.'
        ),
    }
    (OUT / f'worktree-{label}.json').write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + '\n'
    )
    print('WORKTREE_INVENTORY_OK', label, payload['head'], len(hashes))


if __name__ == '__main__':
    main(sys.argv[1])
