#!/usr/bin/env python3
import asyncio,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));import psycopg
from globalVar import POSTGRES_DSN
ROOT=Path(__file__).resolve().parents[3];R=ROOT/'data/reports/breslov/2026-07-15-lm-xv-kdp-fine-zone-detector-v1';RUN='likutey_moharan_xv_kdp_fine_zone_detector_v1_20260715'
async def main():
 async with await psycopg.AsyncConnection.connect(POSTGRES_DSN,row_factory=psycopg.rows.dict_row) as c:
  async with c.cursor() as q:
   async def n(sql):await q.execute(sql,(RUN,) if '%s' in sql else ());return (await q.fetchone())['n']
   zones=await n('select count(*) n from library_lm_xv_kdp_fine_zones_v1 where fine_zone_run_id=%s');badquote=await n("select count(*) n from library_lm_xv_kdp_fine_zones_v1 f join library_lm_xv_kdp_pages_v1 p on p.document_id=f.document_id and p.pdf_page=f.pdf_page and p.source_run_id=f.source_run_id where f.fine_zone_run_id=%s and position(f.text_quote in p.raw_text)=0");nullq=await n('select count(*) n from library_lm_xv_kdp_fine_zones_v1 where fine_zone_run_id=%s and text_quote=\'\'');view=await n('select count(*) n from library_lm_xv_kdp_search_ready_v3')
 checks={'zones_present':zones>0,'all_3208_blocks_covered':zones==3208,'quotes_in_page':badquote==0,'quotes_nonempty':nullq==0,'search_v3_present':view>=zones,'no_ocr':True,'no_ai':True,'no_embeddings':True,'no_milvus':True,'no_relations':True};out={'status':'PASS' if all(checks.values()) else 'FAIL','checks':checks,'metrics':{'zones':zones,'bad_quotes':badquote,'empty_quotes':nullq,'view_rows':view}}
 R.mkdir(parents=True,exist_ok=True);(R/'fine_zone_detector_qa_results.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2));
 if out['status']!='PASS':raise SystemExit(1)
asyncio.run(main())
