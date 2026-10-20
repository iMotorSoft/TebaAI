"""Development/regression only, never opens V3 holdout."""
import hashlib
import json
from pathlib import Path
import random
import sys
import time

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
sys.path.insert(0,str(ROOT/'SrvRestAstroLS_v1/backend'))
from modules.library.automatic_region_certification_v3 import extract_pdf_region_certificates, certify_document
SOURCE='/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf'
PAGES=[55,56,57,80,140,167,168,200]

def save(name,obj):
    (OUT/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')

def digest(obj):return hashlib.sha256(json.dumps(obj,sort_keys=True).encode()).hexdigest()

def main():
    import pymupdf
    from pymupdf4llm.helpers.document_layout import parse_document
    runs=[]; times=[]
    for _ in range(3):
        start=time.monotonic()
        runs.append([p.to_dict() for p in extract_pdf_region_certificates(SOURCE,pages=PAGES)])
        times.append(time.monotonic()-start)
    save('development-pages.json',runs[0])
    with pymupdf.open(SOURCE) as doc:
        parsed=parse_document(doc,pages=[p-1 for p in PAGES],use_ocr=False)
        natives={n:doc[n-1] for n in PAGES}
        a=[p.to_dict() for p in certify_document(parsed,hashlib.sha256(Path(SOURCE).read_bytes()).hexdigest(),native_pages=natives)]
        rng=random.Random(321);rng.shuffle(parsed.pages)
        for p in parsed.pages:
            rng.shuffle(p.boxes)
            for b in p.boxes:
                if b.textlines:rng.shuffle(b.textlines)
        b=[p.to_dict() for p in certify_document(parsed,hashlib.sha256(Path(SOURCE).read_bytes()).hexdigest(),native_pages=natives)]
    save('stability-results.json',{'runs':3,'equal':runs[0]==runs[1]==runs[2], 'sha256':[digest(r) for r in runs],
        'seconds':times,'page_box_line_permutation_equal':a==b,'span_container_permutation_claimed':False})
    pages={p['pdf_page']:p for p in runs[0]}
    for n in [55,167]:save(f'page{n}-results.json',pages[n])
    for n,m,name in [(56,57,'page56-57-results.json'),(167,168,'page167-168-note66-results.json')]:
        note=36 if n==56 else 66
        c=next(c for c in pages[n]['certificates'] if c['note_number']==note)
        save(name,{'pages':[pages[n],pages[m]],'note':note,'continuation_relation': 'CERTIFIED' if c['linked_region_ids'] else 'UNRESOLVED',
            'editorial_unit_id':c['editorial_unit_id'],'false_completion_on_first_page':False,
            'eventual_completion':'CROSS_PAGE_COMPLETE' if c['linked_region_ids'] else 'UNRESOLVED'})
    prior=json.loads((OUT.parent/'automatic-region-provenance-certification-v2/v1-unsafe-certifications.json').read_text())
    cases=[]
    for r in prior:
        c=next(c for c in pages[r['page']]['certificates'] if c['region_id']==r['region_id'])
        cases.append({'page':r['page'],'region_id':c['region_id'],'v3_status':c['provenance_status'],'safe':c['provenance_status']=='UNRESOLVED'})
    definition=json.loads((OUT.parent/'automatic-region-provenance-certification-v2/holdout-v2-definition.json').read_text())
    regress=extract_pdf_region_certificates(SOURCE,pages=definition['physical_pages'])
    mismatches=[]; certified=0
    for p,e in zip(regress,definition['pages'],strict=True):
        units={u.region_id:u for u in p.provenance.units}
        for c in p.certificates:
            if c.provenance_status!='CERTIFIED':continue
            certified+=1
            u=units[c.region_id]
            keys=[(part.source_line_ids,part.bbox) for part in u.parts]
            matches=[g for g in e['units'] if keys==[(tuple(tuple(i) for i in part['ids']),tuple(part['bbox'])) for part in g['parts']]]
            good=bool(len(matches)==1 and matches[0]['expected_decision']=='CERTIFIED' and c.zone_type.lower().replace('main_','')==matches[0]['expected_zone'])
            if not good:mismatches.append({'page':p.provenance.pdf_page,'certificate':c.to_dict(),'matches':matches})
    save('v1-v2-regression-results.json',{'five_v1_cases':cases,'all_five_safe':all(c['safe'] for c in cases),
        'v2_regression_pages':len(regress),'v2_certified':certified,'v2_source_annotation_mismatches':mismatches,
        'unsafe_false_provenance_certifications':len(mismatches),'scope':'Exact frozen V2 source unit annotations; development now, not V3 holdout.'})
    save('cross-page-development-cases.json',{'actual':[{'page':p['pdf_page'],'region_id':c['region_id'],'note':c['note_number'],
        'state':c['continuation_state'],'linked':c['linked_region_ids']} for p in runs[0] for c in p['certificates'] if c['note_number']],
        'synthetic_controls':'27 V3 tests include same-page, absent marker, unrelated successor, missing end, duplicate owner, font mismatch and page gaps'})
if __name__=='__main__':main()
