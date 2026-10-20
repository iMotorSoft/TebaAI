"""Reproduce quality-contract evidence; no service imports/connections/writes.
Run from backend: uv run python ../../data/reports/breslov/quality-aware-partial-ingestion-v1/validate_offline.py
"""
from pathlib import Path
import hashlib
import json
import sys
from collections import Counter

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'SrvRestAstroLS_v1/backend'))
import pymupdf
from modules.library.pdf_hebrew_fidelity import document_header_info, page_markdown
from modules.library.region_quality import (
    QUALITY_POLICY_VERSION, QualityPage, RegionCandidate, classify_region,
    document_quality, markdown_note_starts,
)
from modules.library.chunking import paragraph_chunks

OUT = Path(__file__).resolve().parent
SOURCE = Path('/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf')
SHA = '440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a'


def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def candidate(page, region, text, *, verified=False, diagnostics=(), bbox=None,
              visual=True, reconnect=False, synthetic=False):
    return classify_region(RegionCandidate(
        SHA if not synthetic else 'a' * 64, page, region, text, 'pymupdf4llm',
        ('synthetic-contract-only',) if synthetic else (
            'regional-ocr-hebrew-search-v1/page167-regions.json' if page == 167 else
            'historical-extraction-solution-audit-v1/closure/trace.json',
        ), bbox=bbox, visual_good=visual, text_verified=verified,
        order_verified=verified, structure_verified=verified, diagnostics=diagnostics,
        safe_reconnect_available=reconnect,
    ))


def run():
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != SHA:
        raise ValueError('Golden source hash mismatch')
    with pymupdf.open(SOURCE) as doc:
        hdr = document_header_info(doc)
        outputs = {n: page_markdown(doc, n - 1, hdr_info=hdr)[0] for n in (55, 56, 167)}
    for n, text in outputs.items():
        save(f'page{n}-candidate.json', {'original_markdown': text,
                                        'source_sha256': SHA, 'pdf_page': n})
    m = outputs[167]
    # Fixture adapter ONLY. These literal source boundaries are NOT production
    # rules, and do not certify a generic raw-span -> Markdown association.
    start = m.index('**protección extra')
    end = m.index('## ~~_Notas y Fuentes')
    body = m[start:end].strip()
    assert '\ufffd' not in body
    assert 'zapato derecho primero' in body
    p167 = QualityPage((
        candidate(167, 'header', m[:m.index('**�**')], bbox=(50, 43, 447, 58)),
        candidate(167, 'hebrew_and_transition', m[m.index('**�**'):start],
                  bbox=(50, 65, 447, 258)),
        candidate(167, 'spanish_body', body, verified=True, bbox=(50, 265, 447, 546)),
        candidate(167, 'notes_heading', m[end:m.index('> 60')], bbox=(50, 553, 447, 567)),
        candidate(167, 'spanish_notes', m[m.index('> 60'):],
                  diagnostics=('known_broken_column_order',), bbox=(50, 573, 447, 651)),
    ))
    chunks = [c['content'] for _, text in p167.evidence_units
              for c in paragraph_chunks(text, 1400, 150, 1)]
    assert chunks and all('\ufffd' not in c for c in chunks)
    assert p167.metadata() == QualityPage(tuple(classify_region(r.candidate) for r in p167.regions)).metadata()
    save('page167-results.json', {
        'physical_page': 167, 'printed_page': 149, 'printed_page_provenance': 'existing visual golden, not extractor metadata',
        'Spanish_body': 'ACCEPTED', 'Spanish_notes': 'PLATFORM_EXTRACTION_ERROR',
        'Hebrew_body': 'PLATFORM_EXTRACTION_ERROR', 'page_aggregate': p167.quality.value,
        'corrupt_Hebrew_indexed': 'NO (offline candidate chunks only)',
        'good_Spanish_indexed': 'NO real index; YES offline body chunks',
        'good_Spanish_notes_indexed': 'NO',
        'reason': 'Current Markdown changes note order: continuation65/66 precedes64/65. Raw native notes remain reliable.',
        'candidate_chunks': len(chunks), 'metadata': p167.metadata(),
        'source_sha256': SHA, 'scope': 'offline selected golden; no worker integration',
    })
    # Page55 is an extraction-corruption sample, NOT a whole-page quarantine
    # recommendation. Its trusted neighboring regions have not been mapped.
    corrupt55 = next(p for p in outputs[55].split('\n\n') if p.count('\ufffd') > 20)
    r55 = candidate(55, 'corrupt_markdown_sample', corrupt55)
    save('page55-results.json', {'classification': r55.metadata(),
        'scope': 'one corrupt Markdown paragraph; bbox correspondence unproven',
        'raw_cause': 'layout flags omit CID fallback; Cc becomes U+FFFD (existing audit)',
        'whole_page_blocked': False, 'good_regions_preservation': 'NOT_VALIDATED'})
    starts = markdown_note_starts(outputs[56])
    assert {35, 36}.issubset({s.number for s in starts})
    save('page56-results.json', {
        'decision': 'SAFE_RECONNECT', 'recovered_start_numbers': [s.number for s in starts],
        'original_offsets': [{'number': s.number, 'start': s.start, 'body_start': s.body_start} for s in starts],
        'capability': 'numbered starts accept blockquote and emphasis wrappers without changing original',
        'historical_raw': 'notes35/36 recognized (existing closure trace)',
        'full_note_acceptance': 'NOT_DEMONSTRATED', 'recovery': 'PARTIAL',
        'remaining': ['terminal region bound', 'anchor/next heading', 'chunk role propagation', 'literal citation E2E'],
        'permanent_quarantine': False,
    })
    source = candidate(1, 'source-error', 'Visibly damaged source fixture.', visual=False, synthetic=True)
    unknown = candidate(1, 'unresolved', 'Plausible but unverified fixture.', visual=None, synthetic=True)
    full = candidate(1, 'good', '# Fully good\n\nReliable control text.', verified=True, synthetic=True)
    save('source-error-results.json', {'synthetic_only': True, 'metadata': source.metadata(), 'indexed': False, 'autofixed': False})
    save('unresolved-results.json', {'synthetic_only': True, 'metadata': unknown.metadata(), 'indexed': False})
    pages = (p167, QualityPage((r55,)), QualityPage((source, full)), QualityPage((unknown,)), QualityPage((full,)))
    counts = Counter(r.state.value for p in pages for r in p.regions)
    aggregates = Counter(p.quality.value for p in pages)
    save('fixture-matrix.json', {
        'cases': [
            {'case': 'fully_good', 'kind': 'synthetic', 'status': 'PASS'},
            {'case': 'page167', 'kind': 'real current Markdown', 'status': 'PARTIAL; notes requirement BLOCKED'},
            {'case': 'page55', 'kind': 'real corrupt sample', 'status': 'PASS sample exclusion; neighbors NOT_VALIDATED'},
            {'case': 'page56', 'kind': 'real current Markdown', 'status': 'PARTIAL_SAFE_RECONNECT'},
            {'case': 'source_error', 'kind': 'synthetic', 'status': 'PASS'},
            {'case': 'unresolved', 'kind': 'synthetic', 'status': 'PASS'},
        ],
        'counts_scope': 'selected classified samples, not whole pages55/56 nor full PDF; E2E none',
        'accepted_regions': counts['ACCEPTED'],
        'platform_extraction_errors': counts['PLATFORM_EXTRACTION_ERROR'],
        'source_pdf_errors': counts['SOURCE_PDF_ERROR'], 'unresolved_regions': counts['UNRESOLVED'],
        'full_pages': aggregates['FULL'], 'partial_pages': aggregates['PARTIAL'],
        'unusable_pages': aggregates['UNUSABLE'], 'document_sample_aggregate': document_quality(pages).value,
    })
    save('indexing-safety.json', {
        'scope': 'offline evidence_units + candidate paragraph chunks; NOT real corpus guarantee',
        'known_bad_text_indexed': 0, 'known_bad_text_embedded': 0, 'known_bad_text_citable': 0,
        'good_text_lost_due_neighbor_failure': 0, 'quarantined_regions_untracked': 0,
        'bad_chunks': sum('\ufffd' in c for c in chunks),
        'real_embeddings_generated': 0, 'real_citations_evaluated': 0,
        'real_PG_writes': False, 'real_Milvus_writes': False,
        'current_worker_protected': False,
        'warning': 'Zero counters are candidate-only. Existing corpus was not read, repaired or certified.',
    })
    save('integration-results.json', {
        'gate': 'TEBAAI_BRESLOV_QUALITY_AWARE_PARTIAL_INGESTION_V1', 'status': 'BLOCKED',
        'offline_gate': 'TEBAAI_BRESLOV_QUALITY_AWARE_PARTIAL_INGESTION_OFFLINE_V1_PASS NOT_EMITTED',
        'contract_tests': 'PASS; see tests.txt', 'pipeline_integration': 'NOT_STARTED (offline prerequisite unmet)',
        'small_real_E2E': 'NOT_RUN', 'READY_FOR_C_REINGEST': 'NO',
        'blockers': ['generic source-region to Markdown provenance absent',
                     'page167 note order broken despite reliable native columns',
                     'page56 numbered starts restored, full editorial boundaries not restored'],
        'quality_policy_version': QUALITY_POLICY_VERSION,
        'production_modified': False, 'production_services_touched': False,
        'PG_writes': False, 'Milvus_writes': False, 'C_reingested': False,
        'OCR_integrated': False, 'orthographic_expansion_integrated': False,
    })
    save('quality-states.json', {'quality_policy_version': QUALITY_POLICY_VERSION,
        'region': ['ACCEPTED', 'PLATFORM_EXTRACTION_ERROR', 'SOURCE_PDF_ERROR', 'UNRESOLVED'],
        'aggregate': ['FULL', 'PARTIAL', 'UNUSABLE'],
        'remediation': ['SAFE_RECONNECT', 'QUARANTINE_REQUIRED', 'SOURCE_ERROR', 'UNRESOLVED']})


if __name__ == '__main__':
    run()
