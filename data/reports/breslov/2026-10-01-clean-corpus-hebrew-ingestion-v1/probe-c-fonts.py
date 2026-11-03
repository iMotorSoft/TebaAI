"""Read-only source-font/visibility probe; never changes PG, Milvus or source PDF."""
import hashlib
import json
from pathlib import Path
import sys

REPORT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPORT.parents[3] / 'SrvRestAstroLS_v1/backend'))
import pymupdf
from modules.library.pdf_font_unicode import repair_missing_font_unicode_maps

source = next(book for book in json.loads((REPORT / 'source-books.json').read_text()) if book['label'] == 'C')
path = Path(source['source_path'])
before = hashlib.sha256(path.read_bytes()).hexdigest()
assert before == source['sha256']
result = {'source_sha256': before, 'unicode_recovery_integrated_into_ingestion': False,
          'corpus_modified': False, 'font_changes_in_memory': [], 'fully_covered_runs': [],
          'unresolved_runs_on_review_pages': []}
with pymupdf.open(path) as doc:
    result['font_changes_in_memory'] = repair_missing_font_unicode_maps(doc)
    for page in doc:
        rectangles = [d for d in page.get_drawings()
                      if d['type'] == 'f' and d['fill'] == (1.0, 1.0, 1.0)
                      and d['fill_opacity'] == 1.0 and len(d['items']) == 1
                      and d['items'][0][0] == 're']
        for span in page.get_texttrace():
            text = ''.join(chr(c[0]) for c in span['chars'])
            bounds = pymupdf.Rect(span['bbox'])
            covering = [d for d in rectangles if d['seqno'] > span['seqno'] and d['rect'].contains(bounds)]
            run = {'pdf_page': page.number + 1, 'text_seqno': span['seqno'], 'font': span['font'],
                   'text': text, 'bbox': list(bounds), 'glyph_ids': [c[1] for c in span['chars']]}
            if covering:
                run['covering_rectangles'] = [{'seqno': d['seqno'], 'bbox': list(d['rect']),
                                              'fill': d['fill'], 'opacity': d['fill_opacity']} for d in covering]
                result['fully_covered_runs'].append(run)
            elif '\ufffd' in text and page.number + 1 in (1, 55, 56, 143):
                result['unresolved_runs_on_review_pages'].append(run)
result['source_sha256_after'] = hashlib.sha256(path.read_bytes()).hexdigest()
assert result['source_sha256_after'] == before
(REPORT / 'c-font-visibility-probe.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
print(json.dumps({'covered_runs': len(result['fully_covered_runs']),
                  'unresolved_review_runs': len(result['unresolved_runs_on_review_pages']),
                  'source_unchanged': True, 'ingestion_fix_integrated': False}))
