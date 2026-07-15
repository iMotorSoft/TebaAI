#!/usr/bin/env python3
import argparse,asyncio,hashlib,json,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));import psycopg
from globalVar import POSTGRES_DSN
ROOT=Path(__file__).resolve().parents[3];R=ROOT/'data/reports/breslov/2026-07-15-lm-xv-kdp-fine-zone-detector-v1';SOURCE='likutey_moharan_xv_kdp_page_first_column_aware_v1';STRUCT='likutey_moharan_xv_kdp_structural_detector_v1_20260715';RUN='likutey_moharan_xv_kdp_fine_zone_detector_v1_20260715'
def meta(t):
 if t in ('header','footer','page_number'):return 'navigational','navigational','validated',.9
 if t=='note_or_source_candidate':return 'satellite','support_text','candidate',.75
 if t=='unknown_textual_zone':return 'unknown','unknown','candidate',.5
 return 'primary','primary_text','validated',.85
async def main():
 a=argparse.ArgumentParser();a.add_argument('--apply',action='store_true');x=a.parse_args();zs=[json.loads(l) for l in (R/'fine_zone_profile_blocks.jsonl').read_text().splitlines() if l]
 async with await psycopg.AsyncConnection.connect(POSTGRES_DSN,row_factory=psycopg.rows.dict_row) as c:
  async with c.cursor() as q:
   await q.execute("select id from library_documents where document_code='likutey_moharan_xv_kdp'");did=(await q.fetchone())['id'];await q.execute('select pdf_page,raw_text from library_lm_xv_kdp_pages_v1 where source_run_id=%s',(SOURCE,));pages={r['pdf_page']:r['raw_text'] for r in await q.fetchall()}
   inserted=0
   for z in zs:
    quote=z['text_quote'];typ=z['candidate_zone_type'];role,auth,val,conf=meta(typ)
    if quote not in pages[z['pdf_page']]:raise RuntimeError(f"quote outside page {z['pdf_page']}")
    if x.apply:
     await q.execute("insert into library_lm_xv_kdp_fine_zones_v1(document_id,document_code,source_run_id,structural_detector_run_id,fine_zone_run_id,pdf_page,parent_block_id,block_index,bbox,zone_type,zone_role,authority_level,text_quote,normalized_quote,quote_hash,confidence,evidence_origin,detection_rule,validation_status,warnings,raw_detection) values(%s,'likutey_moharan_xv_kdp',%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,'embedded_block','deterministic_block_zone',%s,'[]',%s::jsonb) on conflict(fine_zone_run_id,pdf_page,block_index) do update set zone_type=excluded.zone_type,text_quote=excluded.text_quote,validation_status=excluded.validation_status",(did,SOURCE,STRUCT,RUN,z['pdf_page'],z['block_id'],z['block_index'],json.dumps(z['bbox']),typ,role,auth,quote,re.sub(r'\s+',' ',quote).strip(),hashlib.sha256(quote.encode()).hexdigest(),conf,val,json.dumps(z,ensure_ascii=False)));inserted+=q.rowcount
   if x.apply:await c.commit()
 out={'run':RUN,'applied':x.apply,'zones':len(zs),'inserted_or_updated':inserted,'ocr_used':False,'ai_used':False,'embeddings':False,'milvus':False,'relations':False};(R/'fine_zone_detector_apply_report.json').write_text(json.dumps(out,indent=2));(R/'fine_zone_detector_apply_summary.md').write_text('# Fine zones\n\n'+json.dumps(out,indent=2));print(json.dumps(out))
asyncio.run(main())
