"""Isolated raster OCR benchmark. Run with backend/.venv/bin/python.
Only writes artifacts here; no worker, repository, database or gateway imports.
"""
from pathlib import Path
import collections
import difflib
import hashlib
import json
import os
import re
import subprocess
import sys
import unicodedata as ud

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0, str(ROOT / 'SrvRestAstroLS_v1/backend'))
import pymupdf as fitz
from pymupdf4llm.helpers.document_layout import FLAGS
from modules.library.hebrew_lexical_normalizer import normalize_hebrew_search

SOURCE = Path('/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf')
SHA = '440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a'
PREFIX = Path('/home/issajar/.local/opt/tebaai-ocr-v1/usr')
ENGINE = PREFIX / 'bin/tesseract'
DATA = PREFIX / 'share/tesseract-ocr/5/tessdata'
ENV = dict(os.environ, LD_LIBRARY_PATH=str(PREFIX / 'lib/x86_64-linux-gnu'), OMP_THREAD_LIMIT='1')


def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def distance(a, b):
    row = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        new = [i]
        for j, y in enumerate(b, 1):
            new.append(min(new[-1] + 1, row[j] + 1, row[j-1] + (x != y)))
        row = new
    return row[-1]


def rate(a, b):
    return round(max(0, 1 - distance(a, b) / len(a)), 6) if a else None


def marks(s):
    return ''.join(c for c in ud.normalize('NFD', s) if '\u0591' <= c <= '\u05c7' and ud.category(c).startswith('M'))


def letters(s):
    return ''.join(c for c in s if '\u05d0' <= c <= '\u05ea')


def metrics(gold, actual, pointed=False):
    # Edit accuracy counts substitutions/deletions/insertions, not a vague similarity.
    g, a = normalize_hebrew_search(gold), normalize_hebrew_search(actual)
    gt, at = g.split(), a.split()
    # LCS exact tokens in logical sequence. Wrong letters also penalize this conservative proxy.
    lcs = sum(b.size for b in difflib.SequenceMatcher(None, gt, at, autojunk=False).get_matching_blocks())
    # Align base characters and project spaces to gold offsets. Inserted/deleted spaces count.
    gs, ats = ''.join(gt), ''.join(at)
    def boundaries(tokens):
        n = 0; result = set()
        for t in tokens[:-1]:
            n += len(t); result.add(n)
        return result
    gb, ab = boundaries(gt), boundaries(at)
    mapping = {}
    for block in difflib.SequenceMatcher(None, gs, ats, autojunk=False).get_matching_blocks():
        for offset in range(block.size + 1):
            mapping[block.b + offset] = block.a + offset
    projected = {mapping.get(b, ('unaligned', b)) for b in ab}
    tp = len(gb & projected)
    boundary = 2 * tp / (len(gb) + len(ab)) if gb or ab else 1.0
    nums = lambda s: re.findall(r'\d+', s)
    punct = lambda s: ''.join(c for c in s if ud.category(c).startswith('P'))
    allowed = lambda c: c.isspace() or c.isdigit() or '\u0590' <= c <= '\u05ff' or ud.category(c) == 'Cf' or ud.category(c).startswith('P') or (any(x.isascii() and x.isalpha() for x in gold) and c.isalpha())
    return {'base_letter_accuracy': rate(letters(gold), letters(actual)),
            'base_letter_reference_count': len(letters(gold)),
            'base_letter_edit_distance': distance(letters(gold), letters(actual)),
            'word_order_accuracy': round(lcs / len(gt), 6) if gt else None,
            'word_boundary_accuracy': round(boundary, 6),
            'number_accuracy': rate(nums(gold), nums(actual)),
            'punctuation_accuracy': rate(punct(gold), punct(actual)),
            'niqqud_accuracy': rate(marks(gold), marks(actual)) if pointed else None,
            'niqqud_reference_count': len(marks(gold)) if pointed else None,
            'unexpected_character_count': sum(not allowed(c) for c in actual),
            'replacement_character_count': actual.count('\ufffd')}


def run():
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == SHA
    version = subprocess.run([str(ENGINE), '--version'], env=ENV, capture_output=True, text=True, check=True).stdout
    langs = subprocess.run([str(ENGINE), '--tessdata-dir', str(DATA), '--list-langs'], env=ENV, capture_output=True, text=True, check=True).stdout
    assert 'heb' in langs.splitlines()
    packages = []
    for p in sorted(Path('/tmp/tebaai-ocr-install').glob('*.deb')):
        fields = subprocess.run(['dpkg-deb', '-f', str(p), 'Package', 'Version', 'Architecture'], capture_output=True, text=True, check=True).stdout
        packages.append({'file': p.name, 'fields': fields, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'source': 'Ubuntu noble/universe http://archive.ubuntu.com/ubuntu (apt configured repository)'})
    save('ocr-environment.json', {'engine': 'Tesseract', 'version': version, 'languages': langs, 'packages': packages,
         'binary': str(ENGINE), 'traineddata': {l: {'path': str(DATA / (l+'.traineddata')), 'sha256': hashlib.sha256((DATA / (l+'.traineddata')).read_bytes()).hexdigest(), 'package_version': '1:4.1.0-2'} for l in ('heb','spa')},
         'installation_scope': 'user-local DEV only; no system package installation', 'OMP_THREAD_LIMIT': 1, 'api_ocr': 'NOT TESTED', 'second_engine': 'NOT TESTED', 'source_sha256': SHA})
    goldens = json.loads((OUT / 'ocr-goldens.json').read_text())
    previous = json.loads((OUT.parent / 'regional-ocr-hebrew-search-v1/native-historical-reconstruction.json').read_text())
    runs = []; comparisons = []
    with fitz.open(SOURCE) as doc:
        for r in goldens['regions']:
            page, bbox = doc[r['page']-1], fitz.Rect(r['bbox'])
            old = next(p for p in previous['pages'] if p['pdf_page'] == r['page'])
            baseline = {'native': page.get_text('text', clip=bbox, flags=FLAGS)}
            for method in ('historical', 'reconstruction'):
                baseline[method] = '\n'.join(b['text'] for b in old[method] if bbox.intersects(fitz.Rect(b['bbox'])))
            comparisons.append({'page': r['page'], 'region': r['id'], 'bbox': r['bbox'], 'baseline': baseline,
                'baseline_metrics': {m: metrics(r['text'], t, r.get('pointed', False)) if m == 'native' and r.get('scored', True) else None for m,t in baseline.items()},
                'ordered_fragment_present': {m: normalize_hebrew_search(r['text']) in normalize_hebrew_search(t) if r.get('scored', True) else None for m,t in baseline.items()},
                'baseline_scope': 'native clipped to bbox; historical/reconstruction overlapping blocks (context overhang); only ordered-fragment presence assessed for those two, not misleading whole-block accuracy'})
            for dpi in (300,400):
                image = OUT / 'crops' / f"{r['id']}-{dpi}.png"
                image.parent.mkdir(exist_ok=True)
                page.get_pixmap(dpi=dpi, clip=bbox).save(image)
                # Two fixed PSMs for Hebrew, single block for Spanish. No endless tuning.
                for psm in ((6,7) if r.get('line') else (6,)):
                    cmd = [str(ENGINE), str(image), 'stdout', '--tessdata-dir', str(DATA), '-l', r.get('language','heb'), '--oem', '1', '--psm', str(psm), '--dpi', str(dpi)]
                    result = subprocess.run(cmd, env=ENV, capture_output=True, text=True, check=True, timeout=90)
                    raw = result.stdout
                    text = ''.join(c for c in raw if ud.category(c) != 'Cf').strip()
                    run = {'page': r['page'], 'region': r['id'], 'bbox': r['bbox'], 'coordinate_system': 'unrotated PDF points; top-left origin',
                           'engine': 'Tesseract', 'version': '5.3.4', 'language': r.get('language','heb'), 'dpi': dpi, 'rotation': 0,
                           'preprocessing': 'raw RGB render', 'config': {'oem': 1, 'psm': psm}, 'source_method': 'visual_ocr', 'command': cmd,
                           'raw_output': raw, 'logical_output': text, 'postprocessing': 'remove Unicode Cf bidi controls only; no reverse/reordering',
                           'stderr': result.stderr, 'metrics': metrics(r['text'], text, r.get('pointed',False)) if r.get('scored',True) else None}
                    runs.append(run)
    for n in (167,55,143):
        save(f'ocr-page{n}-results.json', {'source_sha256': SHA, 'runs': [r for r in runs if r['page']==n]})
    save('ocr-comparison.json', {'source_sha256': SHA, 'comparisons': comparisons,
          'metric_definitions': {'base_letter_accuracy': 'max(0,1-Levenshtein(base letters)/gold letters); insertion penalized',
           'word_order_accuracy': 'SequenceMatcher ordered exact-token matched count / gold token count; conservative proxy jointly affected by letter errors; inspect output for true order',
           'word_boundary_accuracy': 'F1 of spaces projected to gold via base-character alignment; unmatched boundary false positive',
           'niqqud_accuracy': 'mark-sequence edit accuracy on fully pointed fragment ONLY, not marks attachment accuracy; attachment needs separate editorial review',
           'numbers_punctuation': 'sequence edit accuracy; null if golden contains none', 'unscored': 'context/layout controls without a complete transcription; no fabricated metrics'},
          'full_page_ocr': 'NOT RUN / NOT RECOMMENDED', 'baseline_source': '../regional-ocr-hebrew-search-v1/native-historical-reconstruction.json'})

if __name__ == '__main__':
    run()
