"""Offline reproducible experiment. No service access; source opened read-only.
Run from backend with uv run python ../../data/reports/breslov/2026-10-01-clean-corpus-hebrew-ingestion-v1/audit-c-text-reconstruction.py
"""
import hashlib
import html
import json
from collections import Counter
from pathlib import Path
import sys
import unicodedata

REPORT = Path(__file__).resolve().parent
ROOT = REPORT.parents[3]
sys.path.insert(0, str(ROOT / 'SrvRestAstroLS_v1/backend'))
import pymupdf
from modules.library.pdf_font_unicode import repair_missing_font_unicode_maps
from modules.library.pdf_text_visibility import standard_compositing, visible_text_runs
from modules.library.pdf_text_reconstruction import reconstruct_line, reconstruct_runs

out = REPORT / 'c-text-reconstruction-candidate'
out.mkdir(exist_ok=True)
source = next(s for s in json.loads((REPORT / 'source-books.json').read_text()) if s['label'] == 'C')
path = Path(source['source_path'])
sha = hashlib.sha256(path.read_bytes()).hexdigest()
assert sha == source['sha256']
old = json.loads((REPORT / 'c-visibility-candidate/audit.json').read_text())
known = json.loads((REPORT / 'c-font-visibility-probe.json').read_text())['fully_covered_runs']
keys = {(r['pdf_page'], r['text_seqno'], r['font'], tuple(r['glyph_ids'])) for r in known}
families = Counter()
records = []
for r in old['overlapping_runs']:
    if (r['page'], r['seqno'], r['font'], tuple(r['glyph_ids'])) not in keys or r['status'] == 'occluded':
        continue
    assert r['status'] == 'candidate'
    assert any(o['overlap'] == 'full' for o in r['overlays'])
    assert all(not o['paint_ink_contained'] for o in r['overlays'])
    family = 'full_trace_shared_ink_single_overlay' if len(r['overlays']) == 1 else 'full_trace_shared_ink_plus_partial_overlays'
    families[family] += 1
    records.append(dict(r, family=family, decision='KEEP', certification='UNRESOLVED'))
assert sum(families.values()) == 286
(out / 'ambiguous-families.json').write_text(json.dumps({'counts': dict(families), 'records': records}, ensure_ascii=False, indent=2))

# Short manual fragments from the rendered PDF, not extractor-derived goldens.
expected = {2: ['ליקוטי', 'הלכות'], 41: ['Likutey Halajot Explicado'],
            55: ['וְזֶה פֵּרוּשׁ הַפָּסוּק', 'Salmos 16:1'],
            56: ['MELODÍAS Y PLEGARIAS'], 143: ['Likutey Halajot Explicado']}
fixtures = []
summary = []
review = []
with pymupdf.open(path) as doc:
    repair_missing_font_unicode_maps(doc)
    verified = standard_compositing(doc)
    for pg, goldens in expected.items():
        page = doc[pg - 1]
        retained, evidence = visible_text_runs(page, compositing_verified=verified)
        lines = reconstruct_runs(retained)
        raw = page.get_text('rawdict')
        fixture = {'source_sha256': sha, 'pdf_page': pg, 'runs': retained, 'goldens': goldens,
                   'golden_provenance': 'manual short fragments from PDF render; not full-page certification'}
        if pg == 55:
            fragment_chars = [c for r in retained for c in r['chars']
                              if 126.9 < c[2][1] < 127.5 and 365.7 < c[2][0] < 442.1]
            fragment = reconstruct_line(fragment_chars, size=12.3)
            fixture['niqqud_fragment'] = {'chars': fragment_chars, 'size': 12.3,
                                         'expected': goldens[0], 'result': fragment,
                                         'comparison': 'NFD equivalence only; output NOT normalized'}
        fixtures.append(fixture)
        (out / f'page-{pg}-chars.json').write_text(json.dumps({'rawdict': raw, 'lines': lines, 'visibility': evidence}, ensure_ascii=False, indent=2))
        page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5)).save(out / f'page-{pg}.png')
        # Blank line per paint-operation/baseline is diagnostic, NOT inferred
        # paragraph structure. No claim that this is canonical page Markdown.
        md = '\n\n'.join(line['text'].strip() for line in lines if line['text'].strip()) + '\n'
        (out / f'page-{pg}-candidate.md').write_text(md, encoding='utf-8')
        (out / f'page-{pg}-viewer.html').write_text('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Offline text candidate</title><style>body{max-width:55rem;margin:2rem auto;padding:0 1rem}p{white-space:pre-wrap;overflow-wrap:anywhere;font:20px/1.8 serif}</style><h1>Uncertified candidate — PDF '+str(pg)+'</h1>' + ''.join('<p><bdi dir="auto">'+html.escape(l['text'])+'</bdi></p>' for l in lines), encoding='utf-8')
        summary.append({'page': pg, 'line_count': len(lines),
                        'unresolved_lines': sum(bool(l['diagnostics']) for l in lines),
                        'diagnostics': dict(Counter(d.split(':')[0] for l in lines for d in l['diagnostics'])),
                        'goldens': [{'expected': g, 'exact_match': g in md} for g in goldens],
                        'niqqud_fragment_equivalent': (unicodedata.normalize('NFD', fragment['text']).strip() == unicodedata.normalize('NFD', goldens[0])) if pg == 55 else None,
                        'codepoint_conservation': Counter(''.join(chr(c[0]) for r in retained for c in r['chars'])) == Counter(''.join(l['text'] for l in lines))})
    # Broad deterministic review queue: up to 40 distinct pages, then category
    # exemplars. Crops alone are not a certificate of invisible glyphs.
    suppressed = [r for r in old['overlapping_runs'] if r['status'] == 'occluded']
    chosen = {}
    pages = sorted({r['page'] for r in suppressed})
    for i in range(min(40, len(pages))):
        pg = pages[round(i * (len(pages)-1) / max(1, min(40, len(pages))-1))]
        r = next(r for r in suppressed if r['page'] == pg)
        chosen[(r['page'], r['run_index'])] = r
    predicates = {
        'hebrew': lambda r: any('\u05d0' <= c <= '\u05ea' for c in r['text']),
        'marks': lambda r: any(unicodedata.category(c).startswith('M') for c in r['text']),
        'numbers': lambda r: any(c.isdigit() for c in r['text']),
        'reference_candidate': lambda r: ':' in r['text'],
        'header_geometry': lambda r: r['bbox'][1] < 70,
        'body_geometry': lambda r: r['bbox'][1] >= 70,
    }
    coverage = {}
    for tag, predicate in predicates.items():
        matches = [r for r in suppressed if predicate(r)]
        coverage[tag] = len(matches)
        if matches:
            r = matches[0]
            chosen[(r['page'], r['run_index'])] = r
    for (pg, idx), record in chosen.items():
        bounds = pymupdf.Rect(record['bbox']) + (-5, -5, 5, 5)
        clip = bounds & doc[pg-1].rect
        image = f'suppressed-{pg}-{idx}.png'
        doc[pg-1].get_pixmap(matrix=pymupdf.Matrix(3, 3), clip=clip).save(out / image)
        review.append(dict(record, crop=image, visual_review='PENDING'))
with pymupdf.open() as sheet:
    sheet_page = sheet.new_page(width=1200, height=140*((len(review)+2)//3))
    for i, record in enumerate(review):
        x, y = (i % 3)*400, (i // 3)*140
        sheet_page.insert_text((x+5, y+15), f"PDF {record['page']} run {record['run_index']}")
        sheet_page.insert_image(pymupdf.Rect(x+5, y+22, x+395, y+135), filename=str(out / record['crop']))
    sheet_page.get_pixmap().save(out / 'suppression-contact-sheet.png')
fixture_path = ROOT / 'SrvRestAstroLS_v1/backend/tests/fixtures/likutey_halajot_reconstruction_v1.json'
fixture_path.write_text(json.dumps({'fixtures': fixtures}, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
assert hashlib.sha256(path.read_bytes()).hexdigest() == sha
result = {'gate': 'TEBAAI_BRESLOV_LIKUTEY_HALAJOT_TEXT_RECONSTRUCTION_V1_BLOCKED',
          'ready_for_c_reingest': False, 'source_unchanged': True, 'source_sha256': sha,
          'visibility_rule_unchanged': True, 'historical_runs': 671, 'suppressed': 385,
          'retained_ambiguous': 286, 'families': dict(families),
          'certified_visible_false_positives': None, 'samples': summary,
          'suppression_review_queue': review, 'suppressed_category_availability': coverage,
          'normalization_changed': False,
          'paragraph_structure_certified': False, 'desktop_certified': False, 'mobile_certified': False}
(out / 'audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k != 'suppression_review_queue'}, ensure_ascii=False, indent=2))
