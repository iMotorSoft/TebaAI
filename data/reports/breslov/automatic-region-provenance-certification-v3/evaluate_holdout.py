"""One-shot sealed evaluation. No rule or annotation changes after opening."""
import hashlib
import json
from pathlib import Path
import sys
import time

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
sys.path.insert(0,str(ROOT/'SrvRestAstroLS_v1/backend'))
from modules.library.automatic_region_certification_v3 import extract_pdf_region_certificates
SOURCE='/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf'


def keys(parts,actual=False):
    return [(p.source_line_ids,p.bbox) if actual else (tuple(tuple(k) for k in p['ids']),tuple(p['bbox'])) for p in parts]


def main():
    assert not (OUT/'holdout-evaluation-started.json').exists(),'Already opened: do not retune or rerun first evaluation'
    seal=OUT/'holdout-v3-sealed-hash.txt'
    for line in seal.read_text().splitlines():
        sha,path=line.split('  ',1)
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==sha,path
    definition=json.loads((OUT/'holdout-v3-definition.json').read_text())
    assert hashlib.sha256(Path(SOURCE).read_bytes()).hexdigest()==definition['source_sha256']
    (OUT/'holdout-evaluation-started.json').write_text(json.dumps({'seal_sha256':hashlib.sha256(seal.read_bytes()).hexdigest(),'start_unix':time.time(),'no_post_evaluation_tuning':True},indent=2)+'\n')
    start=time.monotonic()
    pages=extract_pdf_region_certificates(SOURCE,pages=definition['physical_pages'])
    metrics={'pages':len(pages),'regions':sum(len(p.certificates) for p in pages),
        'correct_certifications':0,'correct_unresolved':0,'correct_accepted':0,
        'unsafe_false_certifications':0,'unsafe_false_provenance_certifications':0,
        'false_body_certifications':0,'unsafe_false_continuations':0,'false_editorial_completions':0,
        'body_supported_count':0,'body_correctly_certified':0,'body_accepted':0,'body_left_unresolved':0,
        'notes_supported_count':0,'notes_correctly_certified':0,'notes_left_unresolved':0,
        'cross_page_units':len(definition['cross_page_units']),'correctly_linked':0,'cross_page_left_unresolved':0}
    rows=[]; matched={}; actual_c={c.region_id:c for p in pages for c in p.certificates}
    for p,expected in zip(pages,definition['pages'],strict=True):
        assert p.provenance.pdf_page==expected['pdf_page']
        units={u.region_id:u for u in p.provenance.units}
        results=[]
        for c in p.certificates:
            u=units[c.region_id]
            matches=[(i,e) for i,e in enumerate(expected['units']) if keys(u.parts,True)==keys(e['parts'])]
            i,e=matches[0] if len(matches)==1 else (None,None)
            proven=bool(e and e['expected_certifiable'] and c.zone_type==e['expected_zone'] and c.note_number==e['note_number'])
            if proven and c.zone_type=='note':
                proven=[part.column for part in u.parts]==[part['column'] for part in e['parts']]
            certified=c.provenance_status=='CERTIFIED'
            wrong_provenance=certified and not proven
            wrong_accepted=certified and c.quality_status=='ACCEPTED' and (not proven or e['expected_quality']!='ACCEPTED')
            metrics['unsafe_false_provenance_certifications']+=wrong_provenance
            metrics['unsafe_false_certifications']+=wrong_accepted
            metrics['false_body_certifications']+=wrong_provenance and c.zone_type=='MAIN_BODY'
            metrics['correct_certifications']+=certified and proven
            metrics['correct_accepted']+=certified and proven and c.quality_status=='ACCEPTED'
            metrics['correct_unresolved']+=not certified and not (e and e['expected_certifiable'])
            if certified and proven:matched[p.provenance.pdf_page,i]=c
            false_link=False
            if c.linked_region_ids:
                target=actual_c.get(c.linked_region_ids[0]); link=e.get('expected_link') if e else None
                false_link=not bool(proven and link and target and target.pdf_page==link['page'] and target.note_number==link['note'] and target.editorial_unit_id==c.editorial_unit_id)
                metrics['unsafe_false_continuations']+=false_link
            # Complete local/cross-page status needs the independently annotated
            # actual end. An open page segment cannot borrow a local box end.
            completion=c.continuation_state=='COMPLETE_LOCAL' or c.continuation_status=='CROSS_PAGE_COMPLETE'
            false_completion=bool(completion and not (e and (e['expected_continuation_state']=='COMPLETE_LOCAL' or (e['expected_link'] and not false_link and c.linked_region_ids))))
            metrics['false_editorial_completions']+=false_completion
            results.append({'certificate':c.to_dict(),'expected_unit_index':i,'expected':e,
                'unsafe_provenance':wrong_provenance,'unsafe_acceptance':wrong_accepted,'false_link':false_link,'false_completion':false_completion})
        rows.append({'pdf_page':p.provenance.pdf_page,'regions':results})
        for i,e in enumerate(expected['units']):
            if not e['expected_certifiable']:continue
            c=matched.get((p.provenance.pdf_page,i))
            if e['expected_zone']=='MAIN_BODY':
                metrics['body_supported_count']+=1
                metrics['body_correctly_certified']+=c is not None
                metrics['body_accepted']+=bool(c and c.quality_status=='ACCEPTED')
            if e['expected_zone']=='note':
                metrics['notes_supported_count']+=1
                metrics['notes_correctly_certified']+=c is not None
    for link in definition['cross_page_units']:
        cs=[c for c in actual_c.values() if c.pdf_page==link['from'] and c.note_number==link['note'] and c.linked_region_ids]
        metrics['correctly_linked']+=bool(len(cs)==1 and actual_c[cs[0].linked_region_ids[0]].pdf_page==link['to'])
    metrics['body_left_unresolved']=metrics['body_supported_count']-metrics['body_correctly_certified']
    metrics['notes_left_unresolved']=metrics['notes_supported_count']-metrics['notes_correctly_certified']
    metrics['cross_page_left_unresolved']=metrics['cross_page_units']-metrics['correctly_linked']
    metrics['body_supported_coverage']=f"{metrics['body_correctly_certified']}/{metrics['body_supported_count']}"
    metrics['cross_page_supported_coverage']=f"{metrics['correctly_linked']}/{metrics['cross_page_units']}"
    metrics['seconds']=time.monotonic()-start
    safety=not any(metrics[k] for k in ['unsafe_false_certifications','unsafe_false_provenance_certifications','false_body_certifications','unsafe_false_continuations','false_editorial_completions'])
    # A majority left unresolved is literally the user's forbidden 'mostly
    # unresolved'; isolated accepted fragments or a single link do not suffice.
    utility=metrics['body_correctly_certified']>metrics['body_left_unresolved'] and metrics['body_accepted']>1 and metrics['correctly_linked']>1
    output={'gate':'PASS' if safety and utility else 'FAIL','safety_pass':safety,'utility_pass':utility,
        'sealed_before_evaluation':True,'rules_changed_after_evaluation':False,'metrics':metrics,'pages':rows}
    (OUT/'holdout-v3-results.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in output.items() if k!='pages'},indent=2))
if __name__=='__main__':main()
