"""Diagnostic replay, not ingestion or a new golden/test. Run from backend:
PYTHONDONTWRITEBYTECODE=1 uv run python ../../data/reports/breslov/historical-extraction-solution-audit-v1/closure/trace_offline.py
No gateway instances, DB connections, embedding calls, or source PDF mutations.
"""
from pathlib import Path
import ast
import hashlib
import importlib.metadata
import json
import re
import sys
import unicodedata

BACKEND = Path.cwd()
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / 'scripts'))
import pymupdf as fitz
import pymupdf4llm
from pymupdf4llm.helpers.document_layout import FLAGS
from modules.library import simple_research_rag as rag
from modules.library.page_first_evidence import _resolve_printed_page
from modules.library.page_first_pipeline import analyze_page
from modules.library.pdf_hebrew_fidelity import document_header_info, page_markdown
from modules.library.chunking import paragraph_chunks
from modules.library.editorial_evidence_v2 import detect_footnote_marker
from scripts.ingest_likutey_halajot_page_first_v2 import SOURCE, EXPECTED_SHA256, get_page_text
from likutey_layout_parser import parse_page

OUT = Path(__file__).resolve().parent
ROOT = BACKEND.parents[1]
fixtures = json.loads((BACKEND / 'tests/fixtures/likutey_halajot_page_first_v2_acceptance.json').read_text())
ligatures = json.loads((BACKEND / 'tests/fixtures/pdf_ligature_literal_normalization_v1.json').read_text())
query35 = next(f['query'] for f in fixtures if f.get('expected_footnote_number') == 35)
query36 = ligatures['note_36']['query']
source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
assert source_hash == EXPECTED_SHA256
result = {'source_sha256': source_hash, 'scope': 'offline replay; installed dependencies; no live corpus/retrieval',
          'versions': {'pymupdf': fitz.VersionBind, 'pymupdf4llm': importlib.metadata.version('pymupdf4llm'),
                       'layout': getattr(pymupdf4llm, '_use_layout', False)},
          'flags': {'historical_text': fitz.TEXTFLAGS_TEXT, 'current_layout': FLAGS,
                    'CID_for_unknown': fitz.TEXT_CID_FOR_UNKNOWN_UNICODE}, 'pages': []}

def probe(text):
    chunk = {'content': text}
    return {'page_resolver': _resolve_printed_page(chunk), 'rag_page_resolver': rag._canonical_printed_page(chunk),
            'note35': rag._embedded_footnote_number(text, query35),
            'note36': rag._embedded_footnote_number(text, query36),
            'note_starts': [(m.group('number'), m.start()) for m in rag._EMBEDDED_FOOTNOTE_START.finditer(text)],
            'marker35_36': [m for m in detect_footnote_marker(text) if m[0] in (35, 36)],
            'opening_repr': repr(text[:100]),
            'opening_categories': [unicodedata.category(c) for c in text.splitlines()[0]] if text else []}

with fitz.open(SOURCE) as doc:
    hdr = document_header_info(doc)
    for number in (51, 53, 55, 56):
        page = doc[number - 1]
        old = get_page_text(page)
        raw_current = page.get_textpage(flags=FLAGS, clip=fitz.INFINITE_RECT()).extractText()
        raw_cid_diagnostic = page.get_textpage(
            flags=FLAGS | fitz.TEXT_CID_FOR_UNKNOWN_UNICODE, clip=fitz.INFINITE_RECT()).extractText()
        before = pymupdf4llm.to_markdown(doc, pages=[number - 1], **({'hdr_info': hdr} if hdr else {}))
        current, repairs = page_markdown(doc, number - 1, hdr_info=hdr)
        canonical = analyze_page(number, current)
        blocks, node = parse_page(doc, number - 1)
        texts = {'historical_v2_raw': old, 'current_layout_raw': raw_current,
                 'current_layout_raw_cid_diagnostic': raw_cid_diagnostic,
                 'current_markdown_before_repair': before, 'current_canonical': canonical.original_markdown}
        for name, text in texts.items():
            (OUT / f'pdf-{number}-{name}.txt').write_text(text, encoding='utf-8')
        chunks = [x['content'] for x in paragraph_chunks(canonical.original_markdown, 1400, 150, 1)]
        headings = []
        for fixture in [f for f in fixtures if f['expected_pdf_page'] == number and f['expected_source_layer'] == 'section_heading']:
            q = rag.normalize_structural_heading_for_search(fixture['query'])
            def classify(t):
                candidates = rag.classify_structural_heading_candidates(q, [{'chunk_id': 'offline', 'content': t,
                    'block_type': 'page_first_v1', 'evidence_role': 'page_text'}])
                return [{'type': c.get('literal_match_type'), 'heading': c.get('heading_original'),
                         'from_content': c.get('heading_from_content')} for c in candidates]
            headings.append({'query': fixture['query'], 'historical': classify(old), 'current_page': classify(current),
                             'current_chunks': [classify(t) for t in chunks]})
        # Minimal input perturbations, NOT proposed production rewriting.
        no_quote_prefix = re.sub(r'(?m)^> ', '', current)
        no_number_bold = re.sub(r'\*\*(\d+)\*\*', r'\1', current)
        no_initial_italic = re.sub(r'(?m)^(\d+ )_([^_]+)_', r'\1\2', no_quote_prefix)
        row = {'pdf_page': number, 'probes': {name: probe(text) for name, text in texts.items()},
               'layout_node': node, 'repairs': repairs, 'repair_unchanged': before == current,
               'signals': {'headings': canonical.headings, 'footnotes': canonical.footnote_numbers,
                           'references': canonical.printed_references},
               'chunks': [{'index': i, 'len': len(t), **probe(t)} for i, t in enumerate(chunks)],
               'headings': headings,
               'ablations': {'remove_quote_prefix_only': probe(no_quote_prefix),
                            'remove_number_bold_only': probe(no_number_bold),
                            'remove_quote_and_initial_italic': probe(no_initial_italic)},
               'historical_decoded_layout': [{'role': b.block_type, 'content': b.content,
                    'decoder_applied': b.hebrew_decoder_applied, 'bbox': b.bbox} for b in blocks]}
        if number == 55:
            row['reference_layers'] = {'old_surface': rag._content_has_exact_reference_surface(old, 'Salmos 16:1'),
                'current_surface': rag._content_has_exact_reference_surface(current, 'Salmos 16:1')}
        result['pages'].append(row)
# Recover the exact historical inline geometry fixture; do not invent a new golden.
from modules.library.hebrew_pdf_layout import readable_line
from modules.library.pdf_text_reconstruction import reconstruct_line
test_tree = ast.parse((BACKEND / 'tests/test_likutey_moharan_ii_layout.py').read_text())
test_function = next(n for n in test_tree.body if isinstance(n, ast.FunctionDef)
                     and n.name == 'test_rebuilds_hebrew_from_geometry_without_manual_reversal')
line = ast.literal_eval(next(n.value for n in test_function.body if isinstance(n, ast.Assign)))
chars = [(ord(c['c']), 0, (c['bbox'][0], 0), c['bbox']) for s in line['spans'] for c in s['chars']]
result['historical_geometry_fixture_replay'] = {'source_test': test_function.name,
    'historical_projection': readable_line(line), 'candidate': reconstruct_line(chars, size=10),
    'adaptation': 'rawdict chars -> texttrace tuple, synthetic origin at historical bbox x0; not real C ownership proof'}
(OUT / 'trace.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str) + '\n')
print(json.dumps({ 'sha256': source_hash, 'pages': [{ 'page': p['pdf_page'],
    'old': p['probes']['historical_v2_raw'], 'current': p['probes']['current_canonical'],
    'ablations': p['ablations'], 'headings': p['headings']} for p in result['pages']]}, ensure_ascii=False, indent=2))
