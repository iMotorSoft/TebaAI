"""Run before defining holdout. Byte snapshots; no service access."""
from pathlib import Path
import hashlib
import json

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
PREV = OUT.parent / 'hebrew-ocr-orthographic-search-v1'

def sha(b):
    return hashlib.sha256(b).hexdigest()

def run():
    paths = [PREV / 'search_benchmark.py', ROOT / 'SrvRestAstroLS_v1/backend/modules/library/hebrew_lexical_normalizer.py']
    files = {str(p.relative_to(ROOT)): {'sha256': sha(p.read_bytes()), 'source': p.read_text()} for p in paths}
    artifact = {
        'version': 1, 'files': files,
        'rule_set': {'פירוש':'פרוש','עיקר':'עקר','תחילה':'תחלה','תפילין':'תפלין','בבוקר':'בבקר','תפילה':'תפלה','חידושין':'חדושין','עיבור':'עבור'},
        'normalization': 'Exact NFC equality; otherwise frozen normalize_hebrew_search. Full implementation embedded.',
        'generation': 'Directed whole-token replacement; one token per variant; maximum four; no reverse/stemming.',
        'acceptance': 'Candidate accepted ONLY with lexeme_guard=confirmed_context. This is a manual oracle in the development prototype, NOT an implemented automatic disambiguator.',
        'ranking': ['EXACT','NIQQUD_INSENSITIVE','ORTHOGRAPHIC_VARIANT','SEMANTIC'],
        'ranking_scope': 'Pairwise classifier; no production reranker exists in this prototype.',
        'holdout_policy': 'No new candidate entries, manual lexeme guards, exception pairs or thresholds after freeze. Ground truth never passed as lexeme_guard.',
        'hash_spec': 'SHA256 exact UTF-8 artifact bytes including final newline; hash outside artifact avoids self-reference.'}
    target = OUT / 'orthographic-rules-frozen.json'
    if target.exists():
        raise SystemExit('Refusing to overwrite frozen artifact')
    target.write_text(json.dumps(artifact, ensure_ascii=False, sort_keys=True, indent=2)+'\n')
    (OUT/'orthographic-rules-hash.txt').write_text(sha(target.read_bytes())+'  orthographic-rules-frozen.json\n')

if __name__ == '__main__':
    run()
