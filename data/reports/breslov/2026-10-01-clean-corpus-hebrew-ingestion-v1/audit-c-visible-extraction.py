"""Offline candidate audit. No services, ingestion, redactions or source writes.
Run from backend: uv run python ../../data/reports/breslov/2026-10-01-clean-corpus-hebrew-ingestion-v1/audit-c-visible-extraction.py
"""
import hashlib
import json
from collections import Counter
from pathlib import Path
import sys
import unicodedata

REPORT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPORT.parents[3] / 'SrvRestAstroLS_v1/backend'))
import pymupdf
from modules.library.pdf_text_visibility import standard_compositing, visible_text_runs
from modules.library.pdf_font_unicode import repair_missing_font_unicode_maps
from modules.library.pdf_hebrew_fidelity import page_markdown

source = next(b for b in json.loads((REPORT / 'source-books.json').read_text()) if b['label'] == 'C')
path = Path(source['source_path'])
sha = hashlib.sha256(path.read_bytes()).hexdigest()
assert sha == source['sha256']
output = REPORT / 'c-visibility-candidate'
output.mkdir(exist_ok=True)
known = json.loads((REPORT / 'c-font-visibility-probe.json').read_text())['fully_covered_runs']
# Glyph identity is stable even if a converter changes process-global font
# metric bounds (PyMuPDF small_glyph_heights). Do not anchor on float equality.
known_keys = {(r['pdf_page'], r['text_seqno'], r['font'], tuple(r['glyph_ids'])) for r in known}
counts = Counter()
known_counts = Counter()
samples = []
all_evidence = []
categories = {}


def text(run):
    return ''.join(chr(c[0]) for c in run['chars'])


with pymupdf.open(path) as doc:
    fonts = repair_missing_font_unicode_maps(doc)
    compositing_verified = standard_compositing(doc)
    graphics_states = [dict(xref=xref, blend=doc.xref_get_key(xref, 'BM'),
                           soft_mask=doc.xref_get_key(xref, 'SMask'))
                      for xref in range(1, doc.xref_length())
                      if doc.xref_get_key(xref, 'BM')[0] != 'null'
                      or doc.xref_get_key(xref, 'SMask')[0] != 'null']
    for page in doc:
        runs = page.get_texttrace()
        retained, evidence = visible_text_runs(page, compositing_verified=compositing_verified)
        drawings = page.get_drawings(extended=True)
        counts['clip_paths'] += sum(d['type'] == 'clip' for d in drawings)
        counts['transparency_groups'] += sum(d['type'] == 'group' for d in drawings)
        for run, verdict in zip(runs, evidence):
            counts[verdict['status']] += 1
            if (page.number + 1, run['seqno'], run['font'], tuple(c[1] for c in run['chars'])) in known_keys:
                known_counts[verdict['status']] += 1
            if verdict['status'] == 'unproven':
                continue
            value = text(run)
            record = dict(verdict, page=page.number + 1, text=value,
                          font=run['font'], glyph_ids=[c[1] for c in run['chars']],
                          expected_visible='NO' if verdict['status'] == 'occluded' else 'REVIEW_REQUIRED')
            all_evidence.append(record)
            tags = [verdict['status']]
            if any('\u05d0' <= c <= '\u05ea' for c in value): tags.append('hebrew')
            if any('\u0591' <= c <= '\u05c7' for c in value): tags.append('niqqud_or_cantillation')
            if any(c.isdigit() for c in value): tags.append('numbers')
            if ':' in value: tags.append('reference_candidate')
            if any(unicodedata.category(c).startswith('P') for c in value): tags.append('punctuation')
            if any(c.isascii() and c.isalpha() for c in value) and 'hebrew' in tags: tags.append('mixed')
            if 'hebrew' in tags and not any(c.isdigit() or (c.isascii() and c.isalpha()) for c in value): tags.append('pure_hebrew')
            if run['bbox'][1] < 70: tags.append('header_candidate')
            for tag in tags:
                if tag not in categories:
                    categories[tag] = record
    # Finish all geometric classification before invoking the converter:
    # to_markdown changes process-global font metrics used by texttrace.
    for pg in (1, 2, 13, 37, 41, 55, 56, 63, 143):
        page = doc[pg - 1]
        retained, _ = visible_text_runs(page, compositing_verified=compositing_verified)
        page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5)).save(output / f'page-{pg}.png')
        raw = page.get_text()
        (output / f'page-{pg}-raw.txt').write_text(raw, encoding='utf-8')
        (output / f'page-{pg}-filtered-traces.txt').write_text('\n'.join(text(r) for r in retained), encoding='utf-8')
        samples.append({'page': pg, 'canonical_filtered_markdown': 'NOT_IMPLEMENTED',
                        'retained_replacement_characters': sum(text(r).count('\ufffd') for r in retained),
                        'raw_is_nfc': unicodedata.is_normalized('NFC', raw),
                        'raw_is_nfd': unicodedata.is_normalized('NFD', raw)})
    for sample in samples:
        # Current converter output intentionally remains unfiltered. This
        # comparison exposes remaining Unicode/order/niqqud blockers.
        md, repairs = page_markdown(doc, sample['page'] - 1)
        sample['repairs'] = repairs
        (output / f"page-{sample['page']}-candidate-unfiltered.md").write_text(md, encoding='utf-8')
result = {'source_sha256': sha, 'source_unchanged': hashlib.sha256(path.read_bytes()).hexdigest() == sha,
          'ingestion_integrated': False, 'ready_for_c_reingest': False,
          'font_recovery': 'CANDIDATE_ONLY', 'font_changes': fonts,
          'standard_compositing_verified': compositing_verified, 'graphics_states': graphics_states,
          'counts': dict(counts), 'known_671_classifications': dict(known_counts),
          'known_runs_matched': sum(known_counts.values()),
          'visible_false_positives': 'NOT_ESTABLISHED_BY_VISUAL_REVIEW',
          'normalization_changed': False, 'representative_categories': categories,
          'review_pages': samples, 'overlapping_runs': all_evidence}
assert result['source_unchanged']
(output / 'audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k: v for k, v in result.items() if k not in ('overlapping_runs', 'representative_categories', 'font_changes', 'review_pages')}, indent=2))
