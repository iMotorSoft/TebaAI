"""Isolated replay; writes only this report. No PG/Milvus imports/connections.
Annotations must already exist; no rule/threshold editing in this runner.
"""
from pathlib import Path
import csv
import hashlib
import importlib.util
import io
import json
import re
import subprocess
import sys
import unicodedata as ud

OUT=Path(__file__).resolve().parent
PREV=OUT.parent/'hebrew-ocr-orthographic-search-v1'
ROOT=OUT.parents[3]
sys.path.insert(0,str(OUT))
from ocr_gate import decide, POLICY, fold as strict_fold

def save(name,data):
    (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')

def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def frozen():
    b=(OUT/'orthographic-rules-frozen.json').read_bytes()
    assert hashlib.sha256(b).hexdigest()==(OUT/'orthographic-rules-hash.txt').read_text().split()[0]
    artifact=json.loads(b)
    for path,entry in artifact['files'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==entry['sha256']
    return load_module('previous_search',PREV/'search_benchmark.py')

def search(run_semantic=False):
    m=frozen(); definition=(OUT/'holdout-definition.json').read_bytes()
    assert hashlib.sha256(definition).hexdigest()==(OUT/'holdout-definition-hash.txt').read_text().strip()
    cases=json.loads(definition)['cases']; rows=[]
    for c in cases:
        # Only inputs; NO annotation/lexeme guard passes to matcher.
        input_case={'query':c['query'],'canonical_source':c['canonical_source']}
        r=m.match(input_case)
        kind=(r['safest_match_type'] or 'NO_MATCH').upper()
        ranking=[(m.match({'query':c['query'],'canonical_source':s})['safest_match_type'],s)
                 for s in dict.fromkeys([c['canonical_source'],c['query']])]
        priority={None:4,'semantic':3,'orthographic_variant':2,'niqqud_insensitive':1,'exact':0}
        ranked=sorted(ranking,key=lambda pair:priority[pair[0]])
        rows.append(dict(id=c['id'],expected_match=c['expected_match'],final=kind,
            correct=kind in c['allowed_match_types'],generated_variants=r.pop('expanded_variants'),
            exact_priority_preserved=ranked[0][0]=='exact',**r))
    positives=[r for r in rows if r['expected_match']];negatives=[r for r in rows if not r['expected_match']]
    tp=sum(r['final']!='NO_MATCH' for r in positives);fp=sum(r['final']!='NO_MATCH' for r in negatives)
    groups={kind:dict(count=sum(kind in c['allowed_match_types'] for c in cases),
        correct=sum(r['correct'] for c,r in zip(cases,rows) if kind in c['allowed_match_types']))
        for kind in ['EXACT','NIQQUD_INSENSITIVE','ORTHOGRAPHIC_VARIANT','SEMANTIC','NO_MATCH']}
    result=dict(gate='TEBAAI_BRESLOV_HEBREW_ORTHOGRAPHIC_HOLDOUT_V1',status='FAIL_RECALL',
        frozen_rules_hash=(OUT/'orthographic-rules-hash.txt').read_text().split()[0],
        metrics=dict(holdout_size=len(cases),positive_cases=len(positives),negative_cases=len(negatives),
            true_positives=tp,positive_recall=tp/len(positives),precision=tp/(tp+fp) if tp+fp else None,
            dangerous_false_positives=fp,negative_rejection_rate=1-fp/len(negatives),
            exact_ranking_regressions=sum(not r['exact_priority_preserved'] for r in rows),
            exact_preservation_scope=f'{len(cases)} isolated pairwise contests against original-query exact candidate; NOT live retrieval',
            canonical_mutations=0,query_mutations=0),by_expected_type=groups,
        generalizes_beyond_design_set=False,recommended='REJECT',rows=rows,
        limitation='Corpus-grounded editorial query probes; not independently attested paired editions, not blinded human holdout. Zero matches from the eight-entry variant lookup on unseen lexemes.')
    save('holdout-results.json',result)
    focal={'query':'פירוש','canonical_source':'פֵּרוּשׁ'}
    save('known-regressions.json',dict(not_holdout=True,
        focal_without_manual_guard=m.match(focal),
        focal_with_legacy_manual_guard=m.match(dict(focal,lexeme_guard='confirmed_context')),
        note='Legacy manual-guard regression only. Automatic equivalence is NOT demonstrated.'))
    if run_semantic:
        sem=m.semantic([dict(c,expected_positive=c['expected_match']) for c in cases])
        sem['existing_corpus_embeddings_baseline']='NOT_MEASURED: no existing corpus vector snapshot used; no Milvus/PG connection. Same configured model, new transient fixture embeddings only.'
        sem['not_equivalence']='SEMANTIC candidates are never counted as lexical/orthographic true positives.'
        if sem['rows']:
            neg=[r for r in sem['rows'] if not r['expected_positive']]
            pos=[r for r in sem['rows'] if r['expected_positive']]
            sem['metrics']={'positive_top1':sum(r['found_at_1'] for r in pos), 'positive_top3':sum(r['found_at_3'] for r in pos),
                'dangerous_target_top1':sum(r['found_at_1'] for r in neg),'dangerous_target_top3':sum(r['found_at_3'] for r in neg),
                'negative_count':len(neg),'positive_count':len(pos),'threshold':'NONE; ranks are candidates, not acceptance'}
        save('semantic-baseline.json',sem)
    elif not (OUT/'semantic-baseline.json').exists():
        save('semantic-baseline.json',dict(status='BLOCKED',reason='Semantic replay not requested',rows=[]))
    return result

def define_ocr():
    target=OUT/'ocr-quality-fixtures.json'
    if target.exists():return
    old=json.loads((PREV/'ocr-goldens.json').read_text())
    regions=old['regions']
    for r in regions:
        r['golden_text']=r.pop('text')
        if r['id'] in ['R167_C_niqqud','R143_line']:
            r['expected_search']='OCR_ACCEPT_EXPECTED'
            r['expected_display']='OCR_REJECT_EXPECTED' # incomplete/uncertified marks
        else:
            r['expected_search']='OCR_REJECT_EXPECTED'
            r['expected_display']='OCR_REJECT_EXPECTED'
        r['expectation_basis']='Prior visual audit, not current gate output; 400 DPI PSM6 replay primary.'
        r['ground_truth_status']='VISUAL_FRAGMENT' if r['golden_text'] else 'LAYOUT_OR_UNCERTAIN_NO_FULL_TRANSCRIPT'
    regions += [
        dict(id='Q167_title',page=167,bbox=[360,43,425,59],golden_text='ליקוטי הלכות',line=True,expected_search='OCR_ACCEPT_EXPECTED',expected_display='OCR_REJECT_EXPECTED',ground_truth_status='BASE_ONLY_VISUAL_FRAGMENT'),
        dict(id='Q167_folio',page=167,bbox=[428,43,447,59],golden_text='149',line=True,expected_search='OCR_REJECT_EXPECTED',expected_display='OCR_REJECT_EXPECTED',ground_truth_status='VISUAL_AND_RELIABLE_NATIVE_DIGITS'),
        dict(id='Q55_folio',page=55,bbox=[428,43,447,59],golden_text='37',line=True,expected_search='OCR_REJECT_EXPECTED',expected_display='OCR_REJECT_EXPECTED',ground_truth_status='VISUAL_AND_RELIABLE_NATIVE_DIGITS')]
    for r in regions:
        r['config']={'dpi':400,'psm':6,'oem':1}
        r['trusted_reference']=None
        r['trusted_display_reference']=None
        r['trusted_digits']=[str(r['printed_page'])] if r['id'] in ('R167_A','R55_A') else [r['golden_text']] if 'folio' in r['id'] else None
        r['trusted_digit_provenance']='Native ASCII folio corroborated visually in prior audit; not decoded Hebrew' if r['trusted_digits'] else None
    save('ocr-quality-fixtures.json',dict(source_sha256=old['source_sha256'],
        annotation='Prior short visual goldens reused; 3 additional disjoint subregions from audited header. Goldens ONLY for evaluation; not passed into decision function.',
        independence='Known-case safety replay, NOT independent OCR holdout; overlapping regions and config repeats not independent samples.',
        regions=regions))

def ocr():
    b=load_module('previous_benchmark',PREV/'benchmark.py')
    import pymupdf as fitz
    assert hashlib.sha256(b.SOURCE.read_bytes()).hexdigest()==b.SHA
    version=subprocess.run([str(b.ENGINE),'--version'],env=b.ENV,capture_output=True,text=True,check=True).stdout.splitlines()[0]
    assert '5.3.4' in version
    fixtures=json.loads((OUT/'ocr-quality-fixtures.json').read_text());runs=[]
    comparisons=json.loads((PREV/'ocr-comparison.json').read_text())['comparisons']
    with fitz.open(b.SOURCE) as doc:
        for r in fixtures['regions']:
            config_runs=[]
            for dpi in (300,400):
                image=OUT/'crops'/f"{r['id']}-{dpi}.png"
                doc[r['page']-1].get_pixmap(dpi=dpi,clip=fitz.Rect(r['bbox'])).save(image)
                cmd=[str(b.ENGINE),str(image),'stdout','--tessdata-dir',str(b.DATA),'-l',r.get('language','heb'),'--oem','1','--psm','6','--dpi',str(dpi)]
                raw=subprocess.run(cmd,env=b.ENV,capture_output=True,text=True,check=True,timeout=90).stdout
                tsv=subprocess.run(cmd+['tsv'],env=b.ENV,capture_output=True,text=True,check=True,timeout=90).stdout
                words=[x for x in csv.DictReader(io.StringIO(tsv),delimiter='\t') if x.get('level')=='5' and x.get('text','').strip()]
                conf=[float(x['conf']) for x in words if float(x['conf'])>=0]
                text=''.join(c for c in raw if ud.category(c)!='Cf').strip()
                config_runs.append(dict(dpi=dpi,psm=6,raw_output=raw,text=text,
                    mean_word_confidence=sum(conf)/len(conf) if conf else None,
                    tsv_word_boxes=[{k:x[k] for k in ('left','top','width','height','conf','text')} for x in words],
                    tsv_line_count=len(set((x['block_num'],x['par_num'],x['line_num']) for x in words)),
                    crop_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
                    evaluation_metrics=b.metrics(r['golden_text'],text,r.get('pointed',False)) if r['golden_text'] else None))
            primary=config_runs[1];text=primary['text'];other=config_runs[0]['text']
            previous=next((x for x in comparisons if x['region']==r['id']),None)
            native=previous['baseline']['native'] if previous else doc[r['page']-1].get_text(clip=fitz.Rect(r['bbox']))
            signals=dict(text=text,trusted_reference=r['trusted_reference'],trusted_display_reference=r['trusted_display_reference'],
                trusted_digits=r['trusted_digits'],source_visual='GOOD',geometry_verified=r['id']!='R167_E_combined',
                fixed_config_agreement=strict_fold(text)==strict_fold(other))
            diagnostic=dict(ocr_confidence=primary['mean_word_confidence'],native_vs_ocr_disagreement=strict_fold(native)!=strict_fold(text),
                native_token_count=len(native.split()),ocr_token_count=len(text.split()),
                token_count_divergence=len(text.split())-len(native.split()),word_count_divergence=len(text.split())-len(native.split()),
                hebrew_letter_ratio=sum('א'<=c<='ת' for c in text)/max(1,sum(c.isalpha() for c in text)),
                replacement_character_reduction=native.count('\ufffd')-text.count('\ufffd'),
                line_count=primary['tsv_line_count'],line_count_consistency=primary['tsv_line_count']==config_runs[0]['tsv_line_count'],
                unexpected_merges_splits='UNKNOWN_WITHOUT_TRUSTED_REFERENCE',unicode_valid=not any(ud.category(c) in ('Co','Cs') or c=='\ufffd' for c in text),
                native_text=native,native_reliability='ONLY structural ASCII digits trusted where explicit; Hebrew native NOT ground truth')
            decision=decide(signals)
            runs.append(dict(id=r['id'],page=r['page'],bbox=r['bbox'],OCR_output=text,
                expected_search=r['expected_search'],expected_display=r['expected_display'],
                metrics=primary['evaluation_metrics'],signals=signals,diagnostics=diagnostic,config_runs=config_runs,**decision))
    bad=[r for r in runs if r['expected_search']=='OCR_REJECT_EXPECTED'];good=[r for r in runs if r['expected_search']=='OCR_ACCEPT_EXPECTED']
    save('ocr-quality-results.json',dict(gate='TEBAAI_BRESLOV_REGIONAL_OCR_QUALITY_GATE_V1',status='BLOCKED',
        reason='Known unsafe cases rejected, but no independently trusted base-text runtime verifier for damaged Hebrew. Reject-all cannot certify a useful discriminating gate.',
        policy=POLICY,engine=version,source_sha256=b.SHA,
        counts=dict(unique_regions=len(runs),fixed_config_samples=2*len(runs),
            expected_search_accept=len(good),expected_search_reject=len(bad),
            unsafe_search_accepted=sum(r['decision_search']=='SEARCH_ACCEPT' for r in bad),
            safe_search_incorrectly_rejected=sum(r['decision_search']=='SEARCH_REJECT' for r in good),
            display_accepts=sum(r['decision_display']=='DISPLAY_ACCEPT' for r in runs),
            known_header_digit_errors_rejected=all(r['decision_search']=='SEARCH_REJECT' and 'OCR_DIGIT_LOSS' in r['reason_codes'] for r in runs if r['id'] in ('R167_A','R55_A'))),
        confidence_policy='Diagnostic only. No tuning or selecting best configuration.',
        search_gate_usable='NO',display_gate_usable='NO',recommended='MORE_EVIDENCE',rows=runs))

if __name__=='__main__':
    if '--define-ocr' in sys.argv:define_ocr()
    elif '--ocr' in sys.argv:ocr()
    else:search('--semantic' in sys.argv)
