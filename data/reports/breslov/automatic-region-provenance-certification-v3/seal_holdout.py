"""Freeze source-reviewed expectations, independent of V3 candidate output."""
import hashlib
import json
from pathlib import Path
import re

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
# Manually source-reviewed indices, not classifier output. Interleaved/duplicated
# sidebar boxes are intentionally absent from the good-body list.
BODY={45:[5,6,7,8],46:[4,5,6],47:[5,7,9],48:[4,5,6,7],58:[4,5,6],59:[5,6,7],64:[5,6,7],
      65:[],73:[4,5],74:[4,5,6],85:[5,7,8,10,11,12],86:[3,4,6,8],87:[6,7,8],88:[4,5,7],
      171:[5,6,8,9,10],172:[6,7,8,9],173:[7,8,9,10],174:[5,8],215:[6,8,9,10],
      216:[6,7,9],217:[5,6,7],218:[4]}
BAD_BODY={47:[6],64:[10],65:[5,6],73:[6],87:[4],88:[8,9],174:[6],216:[4],218:[5,7]}
NOTE_BOXES={25:[12,13],26:[7,8],28:[8,9],45:[13,14,15,16],46:[11,12],47:[10,11],48:[9,10,11,12],
 58:[8,9,10,11,12],59:[9,10,11,12],64:[12,13,14,15],65:[8,9,10,11,12],73:[9,10,11,12,13,14],74:[8,9,10,11,12,13],
 85:[14,15],86:[10,11,12,13],87:[10,11,12],88:[11,12,13,14,15,16,17],171:[12,13,14,15,16],172:[11,12,13,14],
 174:[10,11,12],215:[11,12,13,14,15],216:[10,11],217:[8],218:[9,10,11,12],244:[11]}
LEADING={45:12,59:43,65:58,74:86,87:123}
CROSS=[(58,59,43),(64,65,58),(73,74,86),(86,87,123)]


def unit(parts,zone,good,*,note=None,state='CONTINUATION_UNRESOLVED',basis='Source-reviewed box identity and editorial role'):
    text='\n'.join(p['text'] for p in parts)
    mixed=any('\u0590'<=c<='\u05ff' for c in text) or '\ufffd' in text
    return {'parts':parts,'expected_zone':zone,'expected_certifiable':bool(good and not mixed),
        'expected_quality':'ACCEPTED' if good and not mixed else 'UNRESOLVED', 'note_number':note,
        'expected_continuation_state':state,'expected_link':None,'basis':basis}


def main():
    assert not (OUT/'holdout-evaluation-started.json').exists()
    inventory=json.loads((OUT/'holdout-source-inventory.json').read_text())
    excluded={55,56,57,167,168,70,80,90,100,110,120,130,140,150,180,190,200}
    excluded.update(json.loads((OUT.parent/'automatic-region-provenance-certification-v2/holdout-v2-definition.json').read_text())['physical_pages'])
    assert not excluded.intersection(p['page'] for p in inventory)
    pages=[]
    for p in inventory:
        n=p['page']; units=[]; note_indices=NOTE_BOXES.get(n,[])
        for b in p['boxes']:
            if b['index'] in note_indices:continue
            good=b['index'] in BODY.get(n,[])
            bad=b['index'] in BAD_BODY.get(n,[])
            zone='MAIN_BODY' if good or bad else ('PREFACE' if n in [26,28] and b['class']=='text' else b['class'])
            units.append(unit(b['lines'],zone,good,basis='Manual source review: full main paragraph/inset vs header, source-language zone, sidebar, ornament or unsupported family. Known interleaved sidebar text is unsafe.'))
        parts=[dict(l,column=0 if (l['bbox'][0]+l['bbox'][2])/2 < p['width']/2 else 1)
               for b in p['boxes'] if b['index'] in note_indices for l in b['lines']]
        parts.sort(key=lambda l:(l['column'],l['bbox'][1],l['bbox'][0],l['ids']))
        current=[]; number=LEADING.get(n)
        for part in parts:
            marker=re.match(r'^\s*(\d{1,3})\s+',part['text'])
            if marker:
                if current:
                    units.append(unit(current,'note',True,note=number,state='COMPLETE_LOCAL'))
                current=[];number=int(marker.group(1))
            current.append(part)
        if current:units.append(unit(current,'note',True,note=number))
        for u in units:
            if u['expected_zone']=='note':
                # A malformed source/column unit cannot be made safe by a label.
                if n==217 or (n==87 and u['note_number']==124):
                    u.update(expected_certifiable=False,expected_quality='UNRESOLVED')
                if n==244:u['expected_certifiable']=False
                for a,b,num in CROSS:
                    if u['note_number']==num and n in [a,b]:
                        u['expected_continuation_state']='CONTINUES_NEXT_PAGE' if n==a else 'CONTINUED_FROM_PREVIOUS'
                        u['expected_link']={'page':b if n==a else a,'note':num}
        pages.append({'pdf_page':n,'units':units})
    definition={'version':'v3','physical_pages':[p['page'] for p in inventory],
        'source_sha256':'440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a',
        'pages':pages,'cross_page_units':[{'from':a,'to':b,'note':num} for a,b,num in CROSS],
        'selection':'30 source-only reviewed pages: fixed separated bands, four observed cross-page notes; all V1/V2 holdout and development targets excluded.',
        'annotation_scope':'Implementing-agent source/IR review, not independent human adjudication nor exhaustive rendered glyph QA. Exact source identity, roles, note column flow and cross-page membership.',
        'utility_rule':'Both main-body certification and cross-page linkage must be useful, not isolated fragments or one development link. Report provenance and ACCEPTED separately. No arbitrary percentage gate.',
        'diversity':['preface/header','main body','main body + heading','main body + Hebrew','sidebar interleaving','same-page note','two-column notes','single-column notes','four cross-page notes','page-start note continuation','unsupported appendix/title/blank','mixed direction'],
        'no_post_evaluation_tuning':True}
    (OUT/'holdout-v3-definition.json').write_text(json.dumps(definition,indent=2,ensure_ascii=False)+'\n')
    paths=[OUT/'holdout-v3-definition.json',OUT/'holdout-source-inventory.json',OUT/'evaluate_holdout.py',OUT/'seal_holdout.py',
        ROOT/'SrvRestAstroLS_v1/backend/tests/test_automatic_region_certification_v3.py']
    paths+=list((ROOT/'SrvRestAstroLS_v1/backend/modules/library').glob('automatic_region_certification*.py'))
    paths += [ROOT/'SrvRestAstroLS_v1/backend/modules/library'/s for s in ['region_markdown_provenance.py','editorial_evidence_v2.py','region_quality.py']]
    paths += [ROOT/'SrvRestAstroLS_v1/backend/uv.lock']
    paths += list(OUT.glob('holdout-source-contact-*.png'))
    paths += [OUT/name for name in ['body-proof-contract.md','continuation-proof-contract.md','cross-page-model.md']]
    (OUT/'holdout-v3-sealed-hash.txt').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(ROOT)}\n' for p in sorted(paths)))
if __name__=='__main__':main()
