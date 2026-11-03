"""Offline evidence only. Run from backend with uv run python <this path>.
No service imports, OCR installs, network calls, source writes or ingestion.
"""
from pathlib import Path
import hashlib
import importlib.metadata
import importlib.util
import json
import shutil
import sys

BACKEND = Path(__file__).resolve().parents[4] / 'SrvRestAstroLS_v1/backend'
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / 'scripts'))
import pymupdf as fitz
from pymupdf4llm.helpers.document_layout import FLAGS
from likutey_layout_parser import parse_page
from modules.library.pdf_font_unicode import repair_missing_font_unicode_maps
from modules.library.pdf_text_visibility import standard_compositing, visible_text_runs
from modules.library.pdf_text_reconstruction import reconstruct_runs
from modules.library.hebrew_lexical_normalizer import normalize_hebrew_search

OUT = Path(__file__).resolve().parent
SOURCE = Path('/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf')
SHA = '440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a'

def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

def candidate_action(*, visual_good: bool | None, native_good: bool, structural_regression: bool = False) -> str:
    """Offline decision contract, NOT a quality detector or worker hook."""
    if visual_good is False:
        return 'SOURCE_PDF_ERROR'
    if visual_good is None:
        return 'UNRESOLVED_SOURCE_OR_PIPELINE'
    if native_good:
        return 'PASS_NATIVE'
    if structural_regression:
        return 'FIX_STRUCTURAL_REGRESSION'
    return 'OCR_BENCHMARK_REQUIRED'


def run():
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == SHA
    versions = {n: importlib.metadata.version(n) for n in ('pymupdf', 'pymupdf4llm')}
    pages = []
    with fitz.open(SOURCE) as doc:
        for number in (41, 55, 56, 143, 167):
            page = doc[number - 1]
            page.get_pixmap(dpi=130).save(OUT / f'page-{number}.png')
            historical, _ = parse_page(doc, number - 1)
            raw = page.get_text('dict', flags=FLAGS)
            blocks = []
            for b in raw['blocks']:
                if 'lines' not in b:
                    continue
                text = '\n'.join(''.join(s['text'] for s in line['spans']) for line in b['lines'])
                blocks.append({'block_id': b['number'], 'bbox': b['bbox'], 'native': text,
                               'replacement_count': text.count('\ufffd')})
            pages.append({'pdf_page': number, 'page_bbox': list(page.rect), 'blocks': blocks,
                          'native_text': page.get_text('text', flags=FLAGS),
                          'historical': [{'bbox': b.bbox, 'text': b.content,
                                          'role': b.block_type, 'decoder_applied': b.hebrew_decoder_applied}
                                         for b in historical]})
        # In-memory candidate only; never save amended document.
        font_changes = repair_missing_font_unicode_maps(doc)
        compositing = standard_compositing(doc)
        for row in pages:
            page = doc[row['pdf_page'] - 1]
            runs, visibility = visible_text_runs(page, compositing_verified=compositing)
            row['reconstruction'] = [{k: g[k] for k in ('text', 'source', 'bbox', 'seqno', 'diagnostics')}
                                     for g in reconstruct_runs(runs)]
            row['visibility'] = visibility
    regions = [('A_header', [50, 43, 447, 58]), ('B_hebrew_main', [50, 65, 447, 230]),
               ('C_transition', [50, 244, 447, 258]), ('D_spanish_body', [50, 265, 447, 546]),
               ('E_notes_heading', [50, 553, 447, 567]),
               ('E_notes_left', [50, 573, 249, 651]), ('E_notes_right', [252, 573, 447, 651])]
    row = pages[-1]
    manifest = []
    with fitz.open(SOURCE) as original:
        for region, bbox in regions:
            rect = fitz.Rect(bbox)
            ids = [b['block_id'] for b in row['blocks'] if rect.intersects(fitz.Rect(b['bbox']))]
            original[166].get_pixmap(dpi=220, clip=rect).save(OUT / f'page167-{region}.png')
            manifest.append({'region': region, 'pdf_page': 167, 'printed_page': 149, 'bbox': bbox,
                             'coordinate_system': 'PDF points; top-left origin; unrotated page',
                             'block_ids': ids, 'dpi': 220,
                             'reason': 'broken embedded Unicode' if region in ('A_header', 'B_hebrew_main')
                                       else 'native good / structural control; OCR not selected',
                             'ocr_selected_for_benchmark': region in ('A_header', 'B_hebrew_main'),
                             'source_method_if_ocr_runs': 'visual_ocr_fallback',
                             'engine': None, 'confidence': None,
                             'native_blocks': [b for b in row['blocks'] if b['block_id'] in ids],
                             'historical_blocks': [b for b in row['historical'] if rect.intersects(fitz.Rect(b['bbox']))],
                             'reconstruction_lines': [b for b in row['reconstruction'] if rect.intersects(fitz.Rect(b['bbox']))]})
    save('page167-regions.json', {'golden_id': 'LIKUTEY_HALAJOT_COMPLEX_PAGE_GOLDEN_V1',
                                'source_sha256': SHA, 'page_bbox': row['page_bbox'], 'regions': manifest})
    golden = json.loads((OUT / 'manual-golden.json').read_text())
    checks = []
    for fragment in golden['fragments']:
        region = next(r for r in manifest if r['region'] == fragment['region'])
        texts = {'native': '\n'.join(b['native'] for b in region['native_blocks']),
                 'historical': '\n'.join(b['text'] for b in region['historical_blocks']),
                 'reconstruction': '\n'.join(b['text'] for b in region['reconstruction_lines'])}
        checks.append({'fragment_id': fragment['id'], 'region': fragment['region'],
                       'measurement': 'normalized ordered fragment present; not whole-region accuracy',
                       'matches': {method: normalize_hebrew_search(fragment['text']) in normalize_hebrew_search(text)
                                   for method, text in texts.items()}, 'ocr': None})
    save('page167-comparison.json', {
        'gate': 'TEBAAI_BRESLOV_PAGE167_HYBRID_EXTRACTION_BENCHMARK_V1', 'status': 'BLOCKED',
        'reason': 'no runnable Hebrew OCR engine; no OCR comparison or accuracy evidence',
        'pdf_visual_good': True, 'native_hebrew': 'FAIL', 'historical_decoder': 'FAIL',
        'experimental_reconstruction': 'PARTIAL', 'recommended_extraction_source': 'UNRESOLVED',
        'ocr_base_letters': None, 'ocr_word_order': None, 'ocr_numbers': None,
        'ocr_punctuation': None, 'ocr_niqqud': None, 'ocr_search_suitable': None, 'ocr_display_suitable': None,
        'fragment_checks': checks,
        'notes': 'Original geometry has distinct left block29 and right block30. Reconstruction groups same seqno/baseline across columns and merges lines; NOT certified.',
        'visual_scope': 'assistant-reviewed raster; legible sampled regions; not editorial proof of all wording'})
    metrics = ('HEBREW_BASE_LETTER_ACCURACY', 'WORD_ORDER_ACCURACY', 'WORD_BOUNDARY_ACCURACY',
               'NUMBER_ACCURACY', 'PUNCTUATION_ACCURACY', 'NIQQUD_FIDELITY',
               'UNEXPECTED_CHARACTER_RATE', 'U+FFFD_COUNT')
    save('ocr-results.json', {'gate': 'TEBAAI_BRESLOV_REGIONAL_OCR_FALLBACK_EVALUATION_V1',
         'status': 'BLOCKED', 'verdict': 'MORE_EVIDENCE_REQUIRED', 'engine_runs': [], 'full_page_runs': [],
         'metrics': {metric: None for metric in metrics}, 'selected_regions': [
             {'pdf_page': 167, 'region': r['region'], 'bbox': r['bbox'], 'block_ids': r['block_ids'],
              'reason': r['reason'], 'source_method': 'visual_ocr_fallback', 'engine': None, 'confidence': None,
              'status': 'NOT_EVALUATED_ENGINE_UNAVAILABLE'}
             for r in manifest if r['ocr_selected_for_benchmark']],
         'additional_page_plan': [
             {'pdf_page': n, 'ocr_run': False, 'reason': 'broken Hebrew/CID regions only; engine unavailable'}
             for n in (41, 55, 56, 143)],
         'page56_rule': 'never OCR to cover the known Markdown notes regression'})
    save('source-pdf-errors.json', {'reviewed_pages': [41, 55, 56, 143, 167], 'errors': [],
         'scope': 'no obvious visible source defect observed in these renders; not exhaustive editorial QA',
         'if_error_found': {'classification': 'SOURCE_PDF_ERROR', 'record': ['page', 'bbox', 'description', 'visual_evidence'],
                            'action': 'record and continue; never repair source silently'}})
    save('native-historical-reconstruction.json', {'source_sha256': SHA, 'versions': versions,
                                                 'font_changes_in_memory': font_changes, 'pages': pages})
    source = 'וְזֶה פֵּרוּשׁ הַפָּסוּק'
    evidence = {'evidence_id': 'offline-search-contract-1', 'canonical_text': source}
    queries = (source, 'וזה פרוש הפסוק', 'וזה פירוש הפסוק', 'וזה פרוש הפסוק 149', 'וזה פרוש הפסוק אחר')
    key = normalize_hebrew_search(source)
    results = [{'query': q, 'search_key': normalize_hebrew_search(q),
                'evidence_id': evidence['evidence_id'] if normalize_hebrew_search(q) == key else None}
               for q in queries]
    assert results[0]['evidence_id'] == results[1]['evidence_id']
    assert all(r['evidence_id'] is None for r in results[2:])
    assert evidence['canonical_text'] == source
    save('hebrew-search-normalization.json', {'scope': 'offline exact-key matching; NOT live retrieval',
         'existing_helper': 'modules/library/hebrew_lexical_normalizer.py:normalize_hebrew_search',
         'canonical_evidence': evidence, 'derived_search_text_he': key, 'results': results,
         'existing_helper_punctuation_collision': {'a': 'שלום, עולם', 'b': 'שלום עולם',
             'same_key': normalize_hebrew_search('שלום, עולם') == normalize_hebrew_search('שלום עולם')},
         'runtime_gate': 'BLOCKED: no live retrieval; broad punctuation normalization is not identity proof'})
    inventory = []
    for name in ('tesseract', 'easyocr', 'paddleocr', 'rapidocr', 'surya', 'docling', 'pytesseract'):
        available = bool(shutil.which(name)) or importlib.util.find_spec(name) is not None
        inventory.append({'name': name, 'availability': 'ALREADY_AVAILABLE' if available else 'NOT_AVAILABLE',
                          'version_model': None, 'hebrew_support': 'not verified in DEV',
                          'local_or_api': 'local', 'cost': 'not measured; no run', 'latency_ms': None,
                          'dependencies': 'executable/package and Hebrew model assets not validated',
                          'privacy': 'local execution would avoid PDF egress'})
    inventory.extend([
        {'name': 'PyMuPDF OCR bridge', 'availability': 'NOT_AVAILABLE', 'version_model': versions['pymupdf'],
         'hebrew_support': 'requires external Tesseract + Hebrew traineddata', 'local_or_api': 'local',
         'cost': 'not measured', 'latency_ms': None, 'dependencies': 'Tesseract absent from PATH',
         'privacy': 'local'},
        {'name': 'vision/API OCR', 'availability': 'NOT_AVAILABLE', 'version_model': None,
         'hebrew_support': 'not verified', 'local_or_api': 'API', 'cost': 'unknown', 'latency_ms': None,
         'dependencies': 'no verified OCR endpoint/model/access; no network probe performed',
         'privacy': 'PDF region egress requires provider/privacy review; not sent'},
        {'name': 'PyMuPDF rasterizer', 'availability': 'ALREADY_AVAILABLE', 'version_model': versions['pymupdf'],
         'hebrew_support': 'renders glyphs; NOT an OCR engine', 'local_or_api': 'local',
         'cost': 'local CPU', 'latency_ms': None, 'dependencies': 'existing pymupdf', 'privacy': 'local'}])
    save('engine-inventory.json', {'scope': 'PATH + backend venv; scoped filesystem search; not entire host',
                                  'engines': inventory, 'installations': False, 'api_calls': False})

if __name__ == '__main__':
    run()
