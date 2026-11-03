"""Derive short measured summaries from raw artifact runs (no service access)."""
from pathlib import Path
import json

OUT=Path(__file__).resolve().parent

def run():
    rows=json.loads((OUT/'ocr-page167-results.json').read_text())['runs']
    summaries=[]
    for dpi in (300,400):
        for psm in (6,7):
            lines=[r for r in rows if r['region'] in ('R167_B_line1','R167_B_line2','R167_B_line3') and r['dpi']==dpi and r['config']['psm']==psm]
            n=sum(r['metrics']['base_letter_reference_count'] for r in lines)
            e=sum(r['metrics']['base_letter_edit_distance'] for r in lines)
            summaries.append({'dpi':dpi,'psm':psm,'scope':'three manually transcribed Hebrew lines ONLY, not entire main region',
                              'base_letter_count':n,'base_letter_edits':e,'base_letter_accuracy':1-e/n,
                              'boundary_f1_by_line':[r['metrics']['word_boundary_accuracy'] for r in lines],
                              'ordered_token_accuracy_by_line':[r['metrics']['word_order_accuracy'] for r in lines],
                              'punctuation_accuracy_by_line':[r['metrics']['punctuation_accuracy'] for r in lines],
                              'unexpected_character_count':sum(r['metrics']['unexpected_character_count'] for r in lines)})
    s=json.loads((OUT/'orthographic-results.json').read_text())
    sr=s['semantic_preflight']['rows']
    positives=[r for r in sr if r['expected_positive']];negatives=[r for r in sr if not r['expected_positive']]
    findings={'ocr_gate':'TEBAAI_BRESLOV_HEBREW_REGIONAL_OCR_REAL_V1','ocr_status':'PASS_NOT_USEFUL',
              'ocr_gate_scope':'real benchmark completed; tested engine/model/config NOT approved as automated fallback for complete primary Hebrew region. Limited exact-base fragments remain useful experimental evidence.',
              'search_gate':s['gate'],'search_status':s['status'],
              'ocr_three_line_summaries':summaries,
              'search_metrics':s['metrics'],
              'semantic_summary':{'status':s['semantic_preflight']['status'], 'positive_top1':sum(r['found_at_1'] for r in positives),'positive_top3':sum(r['found_at_3'] for r in positives),'positive_count':len(positives),
                                  'negative_target_top1':sum(r['found_at_1'] for r in negatives),'negative_target_top3':sum(r['found_at_3'] for r in negatives),'negative_count':len(negatives),
                                  'live_corpus_retrieval':'NOT TESTED; in-memory exact cosine fixture benchmark only'},
              'criteria':{'search': 'For these short fixtures: >=99% base letters, >=99% boundaries, logical order preserved, no materially corrupted or fused target tokens. All required parts of a proposed region must qualify; average alone cannot pass.',
                          'display':'Search criteria plus sufficiently faithful pointed/punctuated source, numbers, no material loss/invention; assistant inspection is not editorial signoff.',
                          'threshold_note':'Conservative explicit experiment acceptance rule, not a calibrated production quality detector.'},
              'regional_recommendations':[
                 {'page':167,'region':'R167_A','classification':'HYBRID_BEST','ocr_search_usable':'title only','ocr_display_usable':False,'reason':'title base exact; OCR 149->9; prefer safe reconstruction title + native number'},
                 {'page':167,'region':'R167_B','classification':'UNRESOLVED','ocr_search_usable':False,'ocr_display_usable':False,'reason':'main body has consonant corruption and materially fused words; short reconstruction goldens pass but full body remains uncertified'},
                 {'page':167,'region':'R167_C','classification':'UNRESOLVED','ocr_search_usable':False,'ocr_display_usable':False,'reason':'reference line 2 base edits/48; no full-line acceptance'},
                 {'page':167,'region':'R167_C_niqqud','classification':'OCR_BEST_FOR_SEARCH','ocr_search_usable':True,'ocr_display_usable':False,'reason':'8/8 base letters and logical order/boundaries; missing holam: 4/5 marks; no reverse'},
                 {'page':167,'region':'R167_D','classification':'NATIVE_BEST','ocr_search_usable':'not needed','ocr_display_usable':False,'reason':'good native Spanish; OCR damages superscript note numbers'},
                 {'page':167,'region':'R167_E_left/right','classification':'NATIVE_BEST','ocr_search_usable':'not needed','ocr_display_usable':False,'reason':'native geometry keeps columns; combined OCR visibly fuses them'},
                 {'page':55,'region':'R55_A','classification':'RECONSTRUCTION_BEST','ocr_search_usable':'title only','ocr_display_usable':False,'reason':'OCR 11/11 title base better than native/historical; 37->7, reconstruction already retains title and folio'},
                 {'page':143,'region':'R143_line','classification':'RECONSTRUCTION_BEST','ocr_search_usable':True,'ocr_display_usable':False,'reason':'400dpi OCR 37/37 base, boundaries/order exact; no full-niqqud golden; reconstruction also preserves the whole sampled line'}],
              'logical_order':'PASS for reviewed Hebrew lines after removing Cf controls ONLY; no global reordering; token accuracy separately records recognition errors',
              'ocr_layout':'FAIL for combined two-column control; not for isolated upper Hebrew fragment',
              'regional_ocr_recommended_now':False, 'full_page_ocr_recommended':False,
              'ready_for_c_reingest':False,'pipeline_modified':False,'pg_writes':False,'milvus_writes':False,'production_modified':False}
    (OUT/'findings.json').write_text(json.dumps(findings,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':run()
