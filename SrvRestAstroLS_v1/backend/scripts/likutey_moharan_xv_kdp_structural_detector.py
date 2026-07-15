#!/usr/bin/env python3
import argparse,asyncio,json,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import psycopg
from globalVar import POSTGRES_DSN
ROOT=Path(__file__).resolve().parents[3];R=ROOT/'data/reports/breslov/2026-07-15-lm-xv-kdp-structural-detector-v1';SOURCE='likutey_moharan_xv_kdp_page_first_column_aware_v1';RUN='likutey_moharan_xv_kdp_structural_detector_v1_20260715'
def decide(p):
 n=p['pdf_page'];blank=p['likely_blank'];q=(p['evidence_quotes']or[None])[0];bid=(p['evidence_block_ids']or[None])[0]
 if blank:return ('blank','blank_page','unknown',None,None,'embedded_blank',.99,q,bid)
 if p['likely_index']:return ('index','classified','index',None,None,'literal_index_marker',.92,q,bid)
 if p['likely_notes_sources']:return ('notes_sources','classified','notes_sources',None,None,'literal_notes_marker',.88,q,bid)
 if p['likely_front_matter']:return ('front_matter','classified','front_matter',None,None,'initial_local_layout',.78,q,bid)
 if p['likely_back_matter']:return ('back_matter','classified','back_matter',None,None,'final_local_layout',.72,q,bid)
 m=re.search(r'(?i)(?:lecci[oó]n|tor[aá])\s+([\w#:.]+)',q or '')
 if m:return ('main_text','classified','lesson',m.group(0),m.group(1),'literal_lesson_marker',.9,q,bid)
 if p['likely_main_text']:return ('main_text','classified','main_text',None,None,'text_density_continuity',.76,q,bid)
 return ('unknown','page_literal_only','unknown',None,None,'no_local_structure_evidence',.5,q,bid)
async def main():
 a=argparse.ArgumentParser();a.add_argument('--apply',action='store_true');x=a.parse_args();pages=json.loads((R/'structural_profile_pages.json').read_text());result=[]
 async with await psycopg.AsyncConnection.connect(POSTGRES_DSN,row_factory=psycopg.rows.dict_row) as c:
  async with c.cursor() as q:
   await q.execute("select id from library_documents where document_code='likutey_moharan_xv_kdp'");did=(await q.fetchone())['id']
   for p in pages:
    part,status,typ,label,num,rule,conf,quote,bid=decide(p);raw={'profile':p}
    rec={'pdf_page':p['pdf_page'],'document_part':part,'structural_status':status,'unit_type':typ,'unit_label':label,'unit_number':num,'evidence_quote':quote,'evidence_block_id':bid,'detection_rule':rule,'confidence':conf};result.append(rec)
    if x.apply:
     await q.execute("insert into library_lm_xv_kdp_structural_classifications_v1(document_id,document_code,source_run_id,structural_detector_run_id,pdf_page,page_status,document_part,structural_status,unit_type,unit_label,unit_number,evidence_quote,evidence_block_id,detection_rule,confidence,warnings,raw_detection) values(%s,'likutey_moharan_xv_kdp',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'[]',%s::jsonb) on conflict(structural_detector_run_id,pdf_page) do update set document_part=excluded.document_part,structural_status=excluded.structural_status,unit_type=excluded.unit_type,unit_label=excluded.unit_label,unit_number=excluded.unit_number,evidence_quote=excluded.evidence_quote,evidence_block_id=excluded.evidence_block_id,detection_rule=excluded.detection_rule,confidence=excluded.confidence,raw_detection=excluded.raw_detection",(did,SOURCE,RUN,p['pdf_page'],p['page_status'],part,status,typ,label,num,quote,bid,rule,conf,json.dumps(raw,ensure_ascii=False)))
   if x.apply:await c.commit()
 out={'run':RUN,'applied':x.apply,'pages':len(result),'blank_pages':sum(x['document_part']=='blank' for x in result),'lessons':sum(x['unit_type']=='lesson' for x in result),'ocr_layout_assist_used':False,'results':result};(R/'structural_detector_apply_report.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));(R/'structural_detector_apply_summary.md').write_text(f"# Structural detector\n\nApplied: {x.apply}; pages: {len(result)}; blanks: {out['blank_pages']}; lessons: {out['lessons']}.\n");print(json.dumps({k:v for k,v in out.items() if k!='results'}))
asyncio.run(main())
