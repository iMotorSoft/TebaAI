"""ONE-SHOT sealed evaluation. Never changes rules, annotations or thresholds."""
import hashlib
import json
from pathlib import Path
import sys
import time

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
sys.path.insert(0,str(ROOT/'SrvRestAstroLS_v1/backend'))
from modules.library.automatic_region_certification_v2 import extract_pdf_region_certificates
SOURCE='/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf'

def part_key(p):
    return (tuple(tuple(k) for k in p['ids']),tuple(p['bbox']))

def main():
    assert not (OUT/'holdout-evaluation-started.json').exists(), 'Holdout already opened; no retuning or second first-run'
    seal=OUT/'holdout-v2-sealed-hash.txt'
    for line in seal.read_text().splitlines():
        digest,path=line.split('  ',1)
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
    definition=json.loads((OUT/'holdout-v2-definition.json').read_text())
    assert hashlib.sha256(Path(SOURCE).read_bytes()).hexdigest()==definition['source_sha256']
    (OUT/'holdout-evaluation-started.json').write_text(json.dumps({'sealed_sha256':hashlib.sha256(seal.read_bytes()).hexdigest(),'start_unix':time.time(),'no_post_evaluation_tuning':True},indent=2)+'\n')
    start=time.monotonic()
    actual=extract_pdf_region_certificates(SOURCE,pages=definition['physical_pages'])
    results=[]; certified=unresolved=unsafe=unsafe_accepted=good_fn=good=correct_accepted=0
    certified_units=set(); classes=set(); notes=0
    for page, expected in zip(actual,definition['pages'],strict=True):
        assert page.provenance.pdf_page==expected['pdf_page']
        units={u.region_id:u for u in page.provenance.units}
        rows=[]
        for c in page.certificates:
            u=units[c.region_id]
            keys=[(p.source_line_ids,p.bbox) for p in u.parts]
            matches=[(i,e) for i,e in enumerate(expected['units']) if keys==[part_key(p) for p in e['parts']]]
            e=matches[0][1] if len(matches)==1 else None
            proven=bool(e and e['expected_decision']=='CERTIFIED' and c.zone_type==e['expected_zone']
                        and c.note_number==e['note_number']
                        and [p.column for p in u.parts]==[p['column'] for p in e['parts']]
                        and (e['expected_zone']!='note' or c.continuation_status==e['continuation']))
            is_cert=c.provenance_status=='CERTIFIED'
            wrong_provenance=is_cert and not proven
            wrong_accepted=is_cert and c.quality_status=='ACCEPTED' and (not proven or e['expected_quality']!='ACCEPTED')
            unsafe+=wrong_provenance
            unsafe_accepted+=wrong_accepted
            certified+=is_cert and proven
            unresolved+=not is_cert and not (e and e['expected_decision']=='CERTIFIED')
            correct_accepted+=is_cert and proven and c.quality_status=='ACCEPTED' and e['expected_quality']=='ACCEPTED'
            if is_cert and proven:
                certified_units.add((expected['pdf_page'],matches[0][0]))
                classes.add(e['expected_zone'])
                if any(p.column==1 for p in u.parts): classes.add('supported_columns')
            rows.append({'certificate':c.to_dict(),'expected_unit_index':matches[0][0] if len(matches)==1 else None,
                         'expected_decision':e['expected_decision'] if e else 'UNRESOLVED',
                         'correct_certification':is_cert and proven,'unsafe_false_provenance_certification':wrong_provenance,
                         'unsafe_false_certification':wrong_accepted,
                         'safe_false_negative':not is_cert and bool(e and e['expected_decision']=='CERTIFIED')})
        results.append({'pdf_page':expected['pdf_page'],'regions':rows})
        for i,e in enumerate(expected['units']):
            if e['expected_decision']=='CERTIFIED':
                good+=1
                good_fn+=(expected['pdf_page'],i) not in certified_units
    useful=bool(certified and correct_accepted)
    utility=useful and {'body','note','supported_columns'}<=classes
    metrics={'pages':len(actual),'regions':sum(len(p.certificates) for p in actual),
        'correct_certified':certified,'correct_unresolved':unresolved,
        'correct_accepted':correct_accepted,'correct_platform_errors':0,'correct_source_errors':0,
        'unsafe_false_certifications':unsafe_accepted,'unsafe_false_provenance_certifications':unsafe,
        'certifiable_good_regions':good,'certified_good_regions':len(certified_units),
        'safe_good_regions_left_unresolved':good_fn,
        'supported_region_coverage_percent':100*len(certified_units)/good if good else 0,
        'useful_supported_regions':useful,'required_class_utility_pass':utility,'certified_classes':sorted(classes),
        'seconds':time.monotonic()-start,
        'coverage_denominator':'Independently annotated good source units, including units not separately discovered; not all emitted candidates.',
        'scope':definition['annotation_scope']}
    gate='PASS' if unsafe==unsafe_accepted==0 and utility else 'FAIL'
    (OUT/'holdout-v2-results.json').write_text(json.dumps({'gate':gate,'sealed_before_evaluation':True,'rules_modified_after_evaluation':False,'metrics':metrics,'pages':results},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(metrics,indent=2))
    print('TEBAAI_BRESLOV_AUTOMATIC_REGION_PROVENANCE_CERTIFICATION_V2_'+gate)
if __name__=='__main__': main()
