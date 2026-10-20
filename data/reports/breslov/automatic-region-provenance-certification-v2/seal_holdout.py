"""Create the pre-evaluation definition from independently reviewed source IR.

Manual box/line assignments below are EVALUATION DATA, never imported by V2.
Run only before evaluate_holdout.py; refusing to reseal an evaluated holdout.
"""
import hashlib
import json
from pathlib import Path

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
# Source review: each list is an explicit annotation, not extractor-label inference.
BODY={21:[],22:[2,3,4,6],23:[],24:[2,3,5,6,7,9],41:[4,5,7],42:[4,5,6],43:[4,5,6],61:[5,6,9],62:[6,7,9,10],63:[5,6,7],81:[4,5,6,7],82:[4,5,6,7],83:[5,6,7,8],161:[4,5,7,9,11],162:[4,6,7,8],163:[4,6,7,8],211:[4,5,6],212:[5,6,7,8,9,10]}
# number, [(box, first line, exclusive last line, column)], editorial state
NOTES={
21:[(3,[(9,0,1,0)],'COMPLETE'),(4,[(11,0,1,0)],'COMPLETE'),(5,[(11,1,2,0)],'COMPLETE'),(6,[(10,0,1,1)],'COMPLETE'),(7,[(8,0,1,1)],'COMPLETE')],
22:[(8,[(8,0,1,0)],'COMPLETE'),(9,[(8,1,2,0)],'COMPLETE'),(10,[(8,2,3,0)],'COMPLETE'),(11,[(9,0,1,1)],'COMPLETE'),(12,[(9,1,2,1)],'COMPLETE'),(13,[(9,2,3,1)],'COMPLETE')],
23:[(14,[(9,0,1,0)],'COMPLETE'),(15,[(9,1,2,0)],'COMPLETE'),(16,[(10,0,1,1)],'COMPLETE'),(17,[(10,1,2,1)],'COMPLETE')],
41:[(2,[(10,0,1,0)],'COMPLETE'),(3,[(11,0,5,0),(12,0,6,1)],'COMPLETE')],
42:[(4,[(8,0,9,0)],'COMPLETE'),(5,[(9,0,13,0),(10,0,8,1)],'COMPLETE'),(6,[(11,0,9,1)],'COMPLETE'),(7,[(12,0,5,1)],'CONTINUES')],
43:[(8,[(8,6,15,0)],'COMPLETE'),(9,[(9,0,7,0),(10,0,6,1)],'COMPLETE'),(10,[(11,0,15,1)],'UNRESOLVED_CONTINUATION')],
61:[(50,[(11,3,5,0),(12,0,4,1)],'COMPLETE')],
62:[(51,[(12,0,3,0)],'COMPLETE'),(52,[(13,0,2,0)],'COMPLETE'),(53,[(14,0,2,0),(15,0,4,1)],'COMPLETE'),(54,[(16,0,3,1)],'CONTINUES')],
63:[(55,[(11,0,5,1)],'UNRESOLVED_CONTINUATION')],
161:[(43,[(13,0,1,0)],'COMPLETE'),(44,[(13,1,4,0)],'COMPLETE'),(45,[(13,4,5,0)],'COMPLETE'),(46,[(14,0,5,1)],'UNRESOLVED_CONTINUATION')],
162:[(47,[(10,0,5,0)],'COMPLETE'),(48,[(10,5,8,0),(11,0,1,1)],'COMPLETE'),(49,[(11,1,2,1)],'COMPLETE'),(50,[(12,0,2,1)],'COMPLETE'),(51,[(13,0,4,1)],'UNRESOLVED_CONTINUATION')],
212:[(34,[(11,0,1,0)],'COMPLETE'),(35,[(12,0,6,0),(13,0,3,1)],'COMPLETE'),(36,[(14,0,1,1)],'COMPLETE'),(37,[(15,0,2,1)],'UNRESOLVED_CONTINUATION')],
}
# All other candidate regions are deliberately unresolved until full forward
# editorial ownership is proved. This includes damaged Hebrew, merged columns,
# duplicate native line ownership, and unlabelled cross-page continuations.

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    assert not (OUT/'holdout-v2-results.json').exists(), 'Cannot reseal an evaluated holdout'
    assert not (OUT/'holdout-v2-sealed-hash.txt').exists(), 'Already sealed'
    inventory=json.loads((OUT/'holdout-source-inventory.json').read_text())
    pages=[]
    for p in inventory:
        n=p['page']; units=[]
        for bi in BODY[n]:
            b=p['boxes'][bi]
            units.append({'expected_zone':'body','note_number':None,'expected_decision':'CERTIFIED',
                'expected_quality':'UNRESOLVED','continuation':'NOT_APPLICABLE',
                'parts':[dict(l,column=None) for l in b['lines']],
                'basis':'Source rendering + source IR: independent Spanish body paragraph, not a note or marginal citation. Text quality is not positively annotated.'})
        if n in (22,24,42,62,82,162,212):
            for bi in (0,1):
                units.append({'expected_zone':'header','note_number':None,'expected_decision':'CERTIFIED',
                    'expected_quality':'UNRESOLVED','continuation':'NOT_APPLICABLE',
                    'parts':[dict(l,column=None) for l in p['boxes'][bi]['lines']],
                    'basis':'Source-rendered running title/folio, independent of extractor classification; quality unverified.'})
        for num,segments,state in NOTES.get(n,[]):
            parts=[dict(l,column=col) for bi,start,end,col in segments for l in p['boxes'][bi]['lines'][start:end]]
            pure=not any('\ufffd' in l['text'] or any('\u0590'<=ch<='\u05ff' for ch in l['text']) for l in parts)
            complete=state=='COMPLETE'
            units.append({'expected_zone':'note','note_number':num,
                'expected_decision':'CERTIFIED' if pure and complete else 'UNRESOLVED',
                'expected_quality':'ACCEPTED' if pure and complete else 'UNRESOLVED',
                'continuation':state,'parts':parts,
                'basis':'Manual source box/line/column annotation reviewed before V2 execution; complete boundaries use subsequent marker or adjacent-page source. Mixed-script logical order remains unproven.'})
        pages.append({'pdf_page':n,'units':units,'default_decision':'UNRESOLVED',
                      'default_basis':'No full positive annotation: uncertain zone/direction, unlabelled continuation, damaged text or overlapping/merged columns. Any certification without exact reviewed ownership is unsafe.'})
    definition={'version':'v2','source_sha256':'440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a',
        'physical_pages':[p['page'] for p in inventory], 'excluded_v1_pages':[55,56,57,167,168,70,80,90,100,110,120,130,140,150,180,190,200],
        'selection':'18 fixed source pages in six separated bands; selected and source reviewed without running V2 on them.',
        'source_review':'holdout-source-inventory.json and contact sheets 1–3; review by implementing agent, NOT independent human adjudication or exhaustive glyph QA.',
        'diversity':['Spanish body','Hebrew source','mixed RTL/LTR','headers','notes','two-column notes','single-column body','cross-page notes 7 and 54','unsupported formula/list','merged/duplicate source regions'],
        'annotation_scope':'Exact source identities, zones, note boundaries, column flow, continuation and source/native text comparison. No claim of exhaustive rendered glyph fidelity.',
        'safety_rule':'Count both CERTIFIED+ACCEPTED unsafe decisions and any incorrect CERTIFIED provenance, even with quality UNRESOLVED.',
        'utility_rule':'Useful supported Spanish body AND simple notes AND supported columns required; zero coverage in body fails utility. No numeric percentage target.',
        'no_tuning_after_execution':True,'pages':pages}
    target=OUT/'holdout-v2-definition.json'
    target.write_text(json.dumps(definition,ensure_ascii=False,indent=2)+'\n')
    files=[target,OUT/'holdout-source-inventory.json',Path(__file__).resolve(),
           ROOT/'SrvRestAstroLS_v1/backend/modules/library/automatic_region_certification_v2.py',
           ROOT/'SrvRestAstroLS_v1/backend/modules/library/automatic_region_certification.py',
           ROOT/'SrvRestAstroLS_v1/backend/modules/library/region_markdown_provenance.py',
           ROOT/'SrvRestAstroLS_v1/backend/tests/test_automatic_region_certification_v2.py',
           OUT/'evaluate_holdout.py']
    (OUT/'holdout-v2-sealed-hash.txt').write_text(''.join(f'{sha(p)}  {p.relative_to(ROOT)}\n' for p in files))
if __name__=='__main__': main()
