"""Real-source offline gate. No runtime, database, vector, or OCR operations.
Run from backend: uv run python ../../data/reports/breslov/region-markdown-provenance-editorial-boundaries-v1/validate_offline.py [PDF]
"""
from copy import deepcopy
from dataclasses import asdict, replace
from pathlib import Path
import ast
import hashlib
import json
import random
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[4]
BACKEND = ROOT / 'SrvRestAstroLS_v1/backend'
sys.path[:0] = [str(BACKEND), str(BACKEND / 'tests')]
from build_fixtures import DEFAULT_SOURCE, SHA, small_fixture, source_layout
from modules.library.region_markdown_provenance import map_layout_page, classify_owned_unit
from modules.library.region_quality import QualityPage
# Reuse executable golden assertions instead of inventing report-only acceptance.
from test_region_markdown_provenance import GOLD, IR, assert_notes, compact, semantic, text
import pymupdf
import pymupdf4llm

OUT = Path(__file__).resolve().parent
GATE = 'TEBAAI_BRESLOV_REGION_MARKDOWN_PROVENANCE_AND_EDITORIAL_BOUNDARIES_V1'


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def digest(value):
    return hashlib.sha256(json.dumps(value, default=list, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def evidence_pages(parsed):
    for page in parsed.pages:
        support = GOLD['continuations'].get(str(page.page_number))
        if support:
            # Supporting evidence is NOTES ONLY, not a claim about the rest of
            # these pages. Full57 has an unrelated duplicate marginal line;
            # the adapter correctly refuses that ambiguous full-page layout.
            top = (support['note_zone_bbox'][1] if support['note_zone_bbox'] else
                   min(b.y0 for b in page.boxes if b.boxclass == 'footnote'))
            page = replace(page, boxes=[b for b in page.boxes if b.y0 >= top - 1])
        yield page


def map_all(parsed):
    results = {}
    for page in evidence_pages(parsed):
        support = GOLD['continuations'].get(str(page.page_number))
        results[page.page_number] = map_layout_page(
            parsed, page, SHA, note_direction='ltr',
            note_zone_bbox=support['note_zone_bbox'] if support else None,
            continued_from=results[support['from_page']] if support else None)
    return results


def metadata(result, unit):
    d = asdict(unit)
    # Do not duplicate whole pages; enough exact geometry/IDs to reproduce.
    for part in d['parts']:
        source = part.pop('source_text')
        part['source_text_sha256'] = hashlib.sha256(source.encode()).hexdigest()
        part['source_text_length'] = len(source)
    d['canonical_sha256'] = hashlib.sha256(result.canonical_text[unit.canonical_start:unit.canonical_end].encode()).hexdigest()
    d['markdown_sha256'] = hashlib.sha256(text(result, unit).encode()).hexdigest()
    return d


def run(source):
    parsed_runs = [source_layout(source) for _ in range(3)]
    assert digest(small_fixture(parsed_runs[0])) == digest(IR), 'Real source diverges from committed small IR fixture'
    runs = [map_all(p) for p in parsed_runs]
    assert runs[0] == runs[1] == runs[2]
    results = runs[0]
    for n in (56, 167):
        assert_notes(results[n], n)
    for n, golden in GOLD['continuations'].items():
        current = results[int(n)]
        unit = next(u for u in current.units if u.continuation_of)
        assert unit.note_number == golden['number']
        assert unit.parts[0].source_text == golden['start']
        assert unit.parts[-1].source_text == golden['end']
        assert [list(k) for p in unit.parts for k in p.source_line_ids] == golden['source_lines']
        assert unit.end_reason == 'NEXT_NOTE_IN_COLUMN_FLOW'
        assert compact(semantic(text(current, unit))) == compact(current.canonical_text[unit.canonical_start:unit.canonical_end])
    permutation = {}
    for page in evidence_pages(deepcopy(parsed_runs[0])):
        support = GOLD['continuations'].get(str(page.page_number))
        if support and support['note_zone_bbox']:
            top = support['note_zone_bbox'][1]
        else:
            top = min(min(l['bbox'][1] for l in b.textlines) for b in page.boxes if b.boxclass == 'footnote')
        stable = [b for b in page.boxes if min(l['bbox'][1] for l in b.textlines) < top - 1]
        notes = [b for b in page.boxes if b not in stable]
        random.Random(91).shuffle(notes)
        for box in notes:
            random.Random(91).shuffle(box.textlines)
        page.boxes = stable + notes
        remapped = map_layout_page(parsed_runs[0], page, SHA, note_direction='ltr',
                                  note_zone_bbox=support['note_zone_bbox'] if support else None,
                                  continued_from=results[support['from_page']] if support else None)
        assert remapped == results[page.page_number]
        permutation[str(page.page_number)] = 'PASS (note geometry only; non-note sequence retained)'
    r167 = results[167]
    body = [u for u in r167.units if 260 < u.source_bbox[1] < 550]
    assert len(body) == 5
    body_ids = {u.region_id for u in body}
    for u in body:
        assert compact(semantic(text(r167, u))) == compact(r167.canonical_text[u.canonical_start:u.canonical_end])
        assert r167.owners(u.markdown_start, u.markdown_end) == (u,)
        assert all(p.column is None for p in u.parts)
    hebrew = [u for u in r167.units if 60 < u.source_bbox[1] < 230]
    assert len(hebrew) == 2
    assert not body_ids & {u.region_id for u in hebrew}
    # Reproduce current serializer defect without mutating the retained IR.
    baseline = deepcopy(parsed_runs[0])
    broken = next(p for p in baseline.pages if p.page_number == 167)
    broken_md = replace(baseline, pages=[broken]).to_markdown()
    assert broken_md.index('66 Comentando') < broken_md.index('64 Ver')
    assert r167.markdown.index('64 Ver') < r167.markdown.index('65 Estudia') < r167.markdown.index('se refrena') < r167.markdown.index('66 Comentando')
    save('page167-provenance.json', {
        'physical_page': 167, 'printed_page': 149, 'printed_page_provenance': 'prior visual golden',
        'Spanish_body_provenance': 'PASS', 'Spanish_notes_provenance': 'PASS',
        'Spanish_notes_boundaries': 'PASS', 'Spanish_notes_order': 'PASS', 'column_ownership': 'PASS',
        'Hebrew_region_independently_addressable': 'YES', 'page_aggregate_candidate': 'PARTIAL',
        'source_sha256': SHA, 'body_region_ids': sorted(body_ids),
        'hebrew_region_ids': [u.region_id for u in hebrew],
        'units': [metadata(r167, u) for u in r167.units],
        'offset_unit': 'Python Unicode code points, page-local, half-open; before exclusion'})
    save('page167-notes-order.json', {
        'manual_golden': GOLD['167'], 'direction_evidence': 'visual crop: LTR complete left then right',
        'old_order_bug_reproduced': True, 'corrected_order': [u.note_number for u in r167.units if u.note_number],
        'cross_column_note': 65, 'note66_terminal_page': 168,
        'notes': [metadata(r167, u) for u in r167.units if u.note_number],
        'note66_continuation': metadata(results[168], next(u for u in results[168].units if u.continuation_of)),
        'terminal_boundary_golden': GOLD['continuations']['168'], 'status': 'PASS'})
    r55 = results[55]
    bad = next(u for u in r55.units if u.parts[0].source_text == GOLD['55']['bad_region_text'])
    i = r55.units.index(bad)
    previous, following = r55.units[i - 1], r55.units[i + 1]
    assert previous.parts[-1].source_text == GOLD['55']['previous_good_tail']
    assert following.parts[0].source_text == GOLD['55']['next_good_start']
    expected = tuple((u.region_id, text(r55, u)) for u in r55.units if u != bad)
    actual = r55.exclude({bad.region_id})
    assert actual == expected
    assert dict(actual)[previous.region_id] == text(r55, previous)
    assert dict(actual)[following.region_id] == text(r55, following)
    with pymupdf.open(source) as pdf:
        native = [s['text'] for b in pdf[54].get_text('dict')['blocks'] for l in b.get('lines', [])
                  for s in l['spans'] if 550 < s['bbox'][1] < 565]
    assert any(unicodedata.category(c) == 'Cc' for s in native for c in s)
    save('page55-neighbor-preservation.json', {
        'physical_page': 55, 'bad_region_isolated': 'YES', 'previous_good_neighbor_preserved': 'YES',
        'next_good_neighbor_preserved': 'YES', 'good_neighbor_sequence_unchanged': 'YES',
        'bad_region': metadata(r55, bad), 'previous_region': metadata(r55, previous),
        'next_region': metadata(r55, following), 'manual_golden': GOLD['55'],
        'native_heading_spans': native, 'layout_heading': bad.parts[0].source_text,
        'Cc_to_U_FFFD_present': True, 'repair_attempted': False,
        'full_original_slice_sequence_equal_after_single_region_exclusion': actual == expected,
        'preserved_sequence_sha256': digest(actual),
        'scope': 'Corrupt notes heading isolated. Verified good preceding tail and entire following note33 preserved. Entire previous box unchanged, NOT certified flawless: its independent marginal/body interleaving remains out of scope.'})
    r56 = results[56]
    save('page56-note-boundaries.json', {
        'physical_page': 56, 'note35_start': 'PASS', 'note35_end': 'PASS',
        'note36_start': 'PASS', 'note36_end': 'PASS', 'editorial_order': 'PASS',
        'offset_stability': 'PASS', 'Markdown_decoration_preserves_provenance': 'PASS',
        'manual_golden': GOLD['56'], 'notes': [metadata(r56, u) for u in r56.units if u.note_number],
        'note36_terminal_page': 57,
        'note36_continuation': metadata(results[57], next(u for u in results[57].units if u.continuation_of)),
        'terminal_boundary_golden': GOLD['continuations']['57'],
        'important': 'Page56 boundary is NOT note36 termination. Continuation owns 12 lines on57, ends before37, without absorbing37/38.'})
    quality = QualityPage(tuple(classify_owned_unit(
        r167, u.region_id, evidence_refs=('source-raw-IR', 'manual-editorial-golden-v1'),
        visual_good=True, text_verified=u.region_id in body_ids or u.note_number is not None,
        order_verified=True, structure_verified=True) for u in r167.units))
    assert quality.quality.value == 'PARTIAL'
    accepted = dict(quality.evidence_units)
    rejected = {r.candidate.region_id for r in quality.regions if not r.accepted_markdown}
    assert not rejected & accepted.keys()
    assert '\ufffd' not in quality.canonical_markdown
    assert all(u.region_id in accepted for u in body + [u for u in r167.units if u.note_number])
    save('offline-quality-recheck.json', {
        'scope': 'Offline candidate ONLY, never a corpus/index/citation guarantee',
        'page167': quality.metadata(), 'known_bad_text_indexed_candidate': 0,
        'known_bad_text_citable_candidate': 0, 'good_text_lost_due_neighbor_failure': 0,
        'quarantined_regions_untracked': 0, 'counters_verified_by': 'exact unit IDs, original slices, ordered sequence; no count-only comparison',
        'unapproved_transformations': [metadata(r, u) for r in results.values() for u in r.units if u.transformation_status != 'ALLOWLIST_ONLY'],
        'worker_modified': False, 'corpus_writes': False, 'READY_FOR_C_REINGEST': 'NO'})
    code = (BACKEND / 'modules/library/region_markdown_provenance.py').read_text()
    constants = [n.value for n in ast.walk(ast.parse(code)) if isinstance(n, ast.Constant)]
    assert not any(n in constants for n in (35, 36, 55, 56, 57, 60, 66, 167, 168))
    assert 'LIKUTEY' not in code and '.find(' not in code and '.index(' not in code
    save('genericity-check.json', {
        'status': 'PASS', 'filename_hardcoding': False, 'page_number_hardcoding': False,
        'note_number_hardcoding': False, 'substring_or_regex_mapping': False,
        'source': 'modules/library/region_markdown_provenance.py', 'source_sha256': hashlib.sha256(code.encode()).hexdigest(),
        'method': 'AST constants + source review + generic synthetic and duplicate-text tests',
        'supported_layout_contract': 'text boxes; certified bottom note zone; disjoint columns; explicit direction. Unresolved layouts raise UnresolvedLayout; no drops.',
        'note57_zone': 'Explicit manual geometry certificate in fixture, because extractor labels ALL its notes text. Not an automatic universal zone detector.'})
    save('idempotence-results.json', {
        'status': 'PASS', 'fresh_PDF_extractions': 3,
        'run_digests': [digest({n: asdict(r) for n, r in run.items()}) for run in runs],
        'equal_region_ids_boundaries_order_offsets_ownership': True, 'input_permutation': permutation,
        'engine_versions': {'pymupdf': pymupdf.__version__, 'pymupdf4llm': pymupdf4llm.__version__},
        'small_fixture_matches_real_IR': True})
    save('gate-result.json', {'gate': GATE, 'status': 'PASS', 'verdict': GATE + '_PASS',
        'NEXT_GATE': 'TEBAAI_BRESLOV_QUALITY_ENFORCEMENT_WORKER_E2E_V1',
        'READY_FOR_C_REINGEST': 'NO', 'worker_modified': False, 'production_modified': False,
        'PostgreSQL_writes': False, 'Milvus_writes': False, 'publication_changes': False,
        'OCR': False, 'visibility_modified': False, 'commit': False, 'push': False})
    print(GATE + '_PASS')


if __name__ == '__main__':
    try:
        run(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SOURCE)
    except Exception as exc:
        save('gate-result.json', {'gate': GATE, 'status': 'FAIL',
             'verdict': GATE + '_FAIL', 'reason': str(exc),
             'READY_FOR_C_REINGEST': 'NO', 'worker_modified': False})
        raise
