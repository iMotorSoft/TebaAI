"""Read-only reproducible evaluation. No manual certificate input to extraction.
Run from backend: uv run python ../../data/reports/breslov/automatic-region-provenance-certification-v1/evaluate.py [PDF]
Holdout definition/annotations and V1 rules are sealed; do not tune this V1.
"""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
BACKEND = ROOT / 'SrvRestAstroLS_v1/backend'
sys.path.insert(0, str(BACKEND))
from modules.library.automatic_region_certification import extract_pdf_region_certificates
from pymupdf4llm.helpers.document_layout import parse_document
import pymupdf
import pymupdf4llm

OUT = Path(__file__).resolve().parent
SOURCE = '/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf'
SHA = '440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a'
GOLD = json.loads((BACKEND / 'tests/fixtures/region_markdown_editorial_goldens_v1.json').read_text())


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def counters(certificates):
    return {'regions_discovered': len(certificates),
            'regions_certified': sum(c['provenance_status'] == 'CERTIFIED' for c in certificates),
            'regions_unresolved': sum(c['provenance_status'] == 'UNRESOLVED' for c in certificates),
            **{key: sum(c['quality_status'] == status for c in certificates)
               for key, status in [('accepted','ACCEPTED'), ('platform_errors','PLATFORM_EXTRACTION_ERROR'),
                                    ('source_errors','SOURCE_PDF_ERROR'), ('quality_unresolved','UNRESOLVED')]}}


def run(source):
    assert hashlib.sha256(Path(source).read_bytes()).hexdigest() == SHA
    seal = json.loads((OUT / 'holdout-seal.json').read_text())
    assert hashlib.sha256((OUT / 'holdout-definition.json').read_bytes()).hexdigest() == seal['definition_sha256']
    assert hashlib.sha256((OUT / 'holdout-annotations.json').read_bytes()).hexdigest() == seal['annotations_sha256']
    assert hashlib.sha256((BACKEND / 'modules/library/automatic_region_certification.py').read_bytes()).hexdigest() == seal['frozen_implementation_sha256']
    runs = [[p.to_dict() for p in extract_pdf_region_certificates(source, pages=[55,56,57,167,168])]
            for _ in range(3)]
    save('stability-results.json', {'fresh_extractions':3,'run_digests':[digest(r) for r in runs],
                                  'equal':runs[0] == runs[1] == runs[2]})
    pages = {p['pdf_page']:p for p in runs[0]}
    for n in (55,56,167):
        page = pages[n]
        result = {'automatic_certificate_input': False, 'manual_boundaries_input': False,
                  'page':page, 'metrics':counters(page['certificates'])}
        if n in (56,167):
            notes = [c for c in page['certificates'] if c['note_number'] is not None]
            units = extract_pdf_region_certificates(source, pages=[n])[0].provenance.units
            by_note = {u.note_number:u for u in units if u.note_number}
            boundaries = all(g['number'] in by_note and
                             by_note[g['number']].parts[0].source_text == g['start'] and
                             by_note[g['number']].parts[-1].source_text == g['end'] and
                             [list(k) for p in by_note[g['number']].parts for k in p.source_line_ids] == g['source_lines']
                             for g in GOLD[str(n)])
            columns = all(list(dict.fromkeys(p.column for p in by_note[g['number']].parts)) == g['columns']
                          for g in GOLD[str(n)] if g['number'] in by_note)
            result.update({'notes_automatically_discovered': [c['note_number'] for c in notes],
                           'page_local_boundaries': 'PASS' if boundaries else 'FAIL',
                           'column_ownership':'PASS' if columns else 'FAIL',
                           'note_order':'PASS' if [c['note_number'] for c in notes] == [g['number'] for g in GOLD[str(n)]] else 'FAIL',
                           'notes_all_certified': all(c['provenance_status']=='CERTIFIED' for c in notes),
                           'notes_all_accepted':all(c['quality_status']=='ACCEPTED' for c in notes),
                           'full_editorial_end_certified':False,
                           'cross_page_continuation_supported':'NO',
                           'offsets_stable':runs[0]==runs[1]==runs[2]})
        if n == 167:
            # Evaluation-only source golden bounds. NOT inputs to extractor.
            body = [c for c in page['certificates'] if 260<c['bbox'][1]<550]
            hebrew = [c for c in page['certificates'] if 60<c['bbox'][1]<230]
            result.update({'body_discovered_automatically':'NO (text boxes discovered; body zone unproven)',
                           'body_provenance_certified':all(c['provenance_status']=='CERTIFIED' for c in body),
                           'body_quality':[c['quality_status'] for c in body],
                           'Hebrew_regions_detected_independently':len(hebrew)==2,
                           'Hebrew_direction':[c['direction'] for c in hebrew],
                           'Hebrew_quality':[c['quality_status'] for c in hebrew],
                           'page_aggregate':page['page_aggregate'], 'expected_certificates':'FAIL'})
        elif n == 55:
            certs=page['certificates']
            bad=next(c for c in certs if 'NATIVE_TO_LAYOUT_REPLACEMENT' in c['reason_codes'])
            i=certs.index(bad)
            result.update({'corrupt_region_auto_detected':True,'quality':bad['quality_status'],
                           'previous_neighbor_auto_certified':certs[i-1]['provenance_status']=='CERTIFIED',
                           'previous_neighbor_quality':certs[i-1]['quality_status'],
                           'next_neighbor_auto_certified':certs[i+1]['provenance_status']=='CERTIFIED',
                           'next_neighbor_quality':certs[i+1]['quality_status'],
                           'neighbor_sequence_preserved':certs[i-1]['markdown_ranges'][0][1] == bad['markdown_ranges'][0][0]
                            and bad['markdown_ranges'][0][1] == certs[i+1]['markdown_ranges'][0][0],
                           'expected_certificates':'FAIL (whole previous box is not the offline selected good tail)'})
        else:
            result['expected_certificates']='FAIL (no automatic continuation identity/end on 57)'
        save(f'page{n}-results.json',result)
    save('supporting-pages-results.json',{'pages':[pages[57],pages[168]]})
    definition=json.loads((OUT/'holdout-definition.json').read_text())
    annotated=json.loads((OUT/'holdout-annotations.json').read_text())
    annotations={p['pdf_page']:p for p in annotated['pages']}
    # This is the first automatic holdout evaluation. The sealed V1 module is
    # never changed in response to the results below.
    holdout=extract_pdf_region_certificates(source,pages=definition['physical_pages'])
    results=[]; correct=unresolved=unsafe=good_unresolved=0
    for actual in holdout:
        expected=annotations[actual.provenance.pdf_page]['boxes']
        region_results=[]
        for c in actual.certificates:
            ids=set(c.source_line_ids)
            owners=[b for b in expected if ids & {tuple(k) for k in b['source_line_ids']}]
            zones=sorted({b['expected_zone'] for b in owners})
            certifiable=bool(owners) and all(b['expected_certifiable'] for b in owners) and len(zones)==1
            certified=c.provenance_status=='CERTIFIED'
            matches=certified and certifiable and zones==[c.zone_type]
            unsafe_region=certified and not matches
            correct+=matches
            unresolved+=(not certified and not certifiable)
            unsafe+=unsafe_region
            good_unresolved+=(not certified and certifiable)
            region_results.append({'expected_zones':zones,'expected_certifiable':certifiable,
                                   'source_annotation_boxes':[b['source_box_index'] for b in owners],
                                   'actual_certificate':c.to_dict(),'correct_certification':matches,
                                   'correct_unresolved':not certified and not certifiable,
                                   'unsafe_false_certification':unsafe_region})
        results.append({'pdf_page':actual.provenance.pdf_page,'regions':region_results})
    all_c=[c.to_dict() for p in holdout for c in p.certificates]
    metrics={**counters(all_c),'pages':len(holdout),'correct_certifications':correct,
             'correct_unresolved':unresolved,'unsafe_false_certifications':unsafe,
             'good_certifiable_regions_left_unresolved':good_unresolved,
             'scope':'annotated structural ownership/zones only; NOT exhaustive visible glyph quality'}
    save('holdout-results.json',{'metrics':metrics,'pages':results,'rules_tuned_after_evaluation':False})
    save('evaluation-summary.json',{'gate':'TEBAAI_BRESLOV_AUTOMATIC_REGION_PROVENANCE_CERTIFICATION_V1_FAIL',
                                  'READY_FOR_C_REINGEST':'NO','holdout':metrics,
                                  'goldens_all_pass':False,'worker_ready':False,
                                  'engine_versions':{'pymupdf':pymupdf.__version__,'pymupdf4llm':pymupdf4llm.__version__}})
    print(json.dumps(metrics,indent=2))
    print('TEBAAI_BRESLOV_AUTOMATIC_REGION_PROVENANCE_CERTIFICATION_V1_FAIL')


if __name__=='__main__':
    run(sys.argv[1] if len(sys.argv)>1 else SOURCE)
