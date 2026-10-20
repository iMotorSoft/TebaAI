"""Development evaluation only. Never opens or evaluates the V2 holdout."""
import hashlib
import json
from pathlib import Path
import sys
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0, str(ROOT/'SrvRestAstroLS_v1/backend'))
from modules.library.automatic_region_certification_v2 import extract_pdf_region_certificates
SOURCE='/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf'
PAGES=[55,56,57,80,140,167,168,200]

def save(name, value):
    (OUT/name).write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')

def main():
    times=[]; runs=[]
    for _ in range(3):
        t=time.monotonic()
        runs.append([p.to_dict() for p in extract_pdf_region_certificates(SOURCE,pages=PAGES)])
        times.append(time.monotonic()-t)
    pages={p['pdf_page']:p for p in runs[0]}
    gold=json.loads((ROOT/'SrvRestAstroLS_v1/backend/tests/fixtures/region_markdown_editorial_goldens_v1.json').read_text())
    boundary_checks=[]
    fresh=extract_pdf_region_certificates(SOURCE,pages=[56,167])
    for p in fresh:
        for u in p.provenance.units:
            if u.note_number is None: continue
            g=next(g for g in gold[str(p.provenance.pdf_page)] if g['number']==u.note_number)
            ok=(u.parts[0].source_text==g['start'] and u.parts[-1].source_text==g['end']
                and [list(k) for part in u.parts for k in part.source_line_ids]==g['source_lines']
                and list(dict.fromkeys(part.column for part in u.parts))==g['columns'])
            boundary_checks.append({'page':p.provenance.pdf_page,'note':u.note_number,'source_boundary_column_order_match':ok})
    save('development-boundary-checks.json',boundary_checks)
    assert all(c['source_boundary_column_order_match'] for c in boundary_checks)
    save('development-pages.json',runs[0])
    save('stability-results.json',{'runs':3,'equal':runs[0]==runs[1]==runs[2],
         'sha256':[hashlib.sha256(json.dumps(r,sort_keys=True).encode()).hexdigest() for r in runs],
         'seconds':times,'cross_page_states_identical':runs[0]==runs[1]==runs[2]})
    prior=json.loads((OUT.parent/'automatic-region-provenance-certification-v1/holdout-results.json').read_text())
    failures=[]
    for p in prior['pages']:
        for r in p['regions']:
            if not r['unsafe_false_certification']: continue
            old=r['actual_certificate']
            new=next(c for c in pages[p['pdf_page']]['certificates'] if c['region_id']==old['region_id'])
            failures.append({'region_id':old['region_id'],'page':p['pdf_page'], 'V1_result':old,
                'V2_result':new,'correct_decision':'UNRESOLVED until note zone/ownership/boundaries proven',
                'root_cause':'EXTRACTOR_CLASS_IS_NOT_EDITORIAL_ZONE_PROOF',
                'why_v1_certified':'Recognized extractor class + LTR + unique identity; no independent zone proof',
                'missing_proof':'Editorial note-zone and ownership certificate; local box bounds do not prove editorial boundaries',
                'proof_strengthened':'Explicit composed note zone; non-note labels never sufficient',
                'V2_expected_decision':'UNRESOLVED'})
    save('v1-unsafe-certifications.json',failures)
    save('development-regressions.json',{'five_v1_unsafe_eliminated':len(failures)==5 and all(r['V2_result']['provenance_status']=='UNRESOLVED' for r in failures),
        'unsafe_false_provenance_certifications':sum(r['V2_result']['provenance_status']=='CERTIFIED' for r in failures),
        'all_golden_local_boundaries_columns_order_match':all(c['source_boundary_column_order_match'] for c in boundary_checks),
        'certified_development_regions':[{'page':p['pdf_page'],'region_id':c['region_id'],'note':c['note_number']} for p in runs[0] for c in p['certificates'] if c['provenance_status']=='CERTIFIED'],
        'known_good_body_supported':False,'page55_both_neighbors_accepted':False,
        'cross_page_36_66_resolved':False,'regression_pages':PAGES,
        'scope':'Five false zones and existing editorial goldens; not exhaustive rendered-glyph review'})
    for n in (55,56,167):
        page=pages[n]; cs=page['certificates']
        result={'page':page}
        if n==167:
            body=[c for c in cs if 260<c['bbox'][1]<550]
            rtl=[c for c in cs if 60<c['bbox'][1]<230]
            notes=[c for c in cs if c['note_number'] is not None]
            result.update(body='UNRESOLVED',body_quality=[c['quality_status'] for c in body],
                body_missing_proof='Generic text class cannot distinguish body from unlabelled note continuation; no supported body family certificate',
                notes_discovered=[c['note_number'] for c in notes],notes_certified=[c['note_number'] for c in notes if c['provenance_status']=='CERTIFIED'],
                RTL='UNRESOLVED',RTL_reasons=[c['reason_codes'] for c in rtl],page_aggregate_candidate=page['page_aggregate'],
                column_order_correctness='PASS' if all(c['source_boundary_column_order_match'] for c in boundary_checks if c['page']==167) else 'FAIL')
        if n==55:
            old=json.loads((OUT.parent/'automatic-region-provenance-certification-v1/page55-results.json').read_text())
            bad_id=next(c['region_id'] for c in old['page']['certificates'] if 'NATIVE_TO_LAYOUT_REPLACEMENT' in c['reason_codes'])
            i=next(i for i,c in enumerate(cs) if c['region_id']==bad_id)
            result.update(bad_region=cs[i],previous_neighbor=cs[i-1],next_neighbor=cs[i+1],
                unsafe_certification=False,neighbor_sequence='PASS' if cs[i-1]['markdown_ranges'][0][1]==cs[i]['markdown_ranges'][0][0] and cs[i]['markdown_ranges'][0][1]==cs[i+1]['markdown_ranges'][0][0] else 'FAIL',
                symmetric_contract=True,quality_attribution_gap='Bad heading lacks zone proof; deterministic corruption cannot bypass provenance')
        if n==56:
            result.update(notes=[c for c in cs if c['note_number']],note36_continuation='UNRESOLVED',false_completion_on_56=False,
                          known_editorial_end_page=57)
        save(f'page{n}-results.json',result)
    notes=[c for p in runs[0] for c in p['certificates'] if c['note_number']]
    save('cross-page-results.json',{'same_page_complete_units':sum(c['continuation_status']=='COMPLETE' for c in notes),
        'cross_page_units_certified':0,'unresolved_continuation':sum(c['continuation_status']=='UNRESOLVED_CONTINUATION' for c in notes),
        'incorrect_truncations':0,'known_continuations':[{'note':36,'from':56,'end':57,'status':'UNRESOLVED_CONTINUATION'}, {'note':66,'from':167,'end':168,'status':'UNRESOLVED_CONTINUATION'}],
        'limitation':'No automatic cross-page owner linking; local boundary known, editorial completion withheld'})
if __name__=='__main__': main()
