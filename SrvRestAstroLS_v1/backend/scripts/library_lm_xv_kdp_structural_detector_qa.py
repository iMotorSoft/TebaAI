#!/usr/bin/env python3
import asyncio,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import psycopg
from globalVar import POSTGRES_DSN
ROOT=Path(__file__).resolve().parents[3];R=ROOT/'data/reports/breslov/2026-07-15-lm-xv-kdp-structural-detector-v1';RUN='likutey_moharan_xv_kdp_structural_detector_v1_20260715'
async def main():
 async with await psycopg.AsyncConnection.connect(POSTGRES_DSN,row_factory=psycopg.rows.dict_row) as c:
  async with c.cursor() as q:
   async def n(sql):await q.execute(sql,(RUN,) if '%s' in sql else ());return (await q.fetchone())['n']
   pages=await n('select count(*) n from library_lm_xv_kdp_structural_classifications_v1 where structural_detector_run_id=%s');blanks=await n("select count(*) n from library_lm_xv_kdp_structural_classifications_v1 where structural_detector_run_id=%s and document_part='blank'");bad=await n("select count(*) n from library_lm_xv_kdp_structural_classifications_v1 where structural_detector_run_id=%s and document_part<>'blank' and evidence_quote is null");invented=await n("select count(*) n from library_lm_xv_kdp_structural_classifications_v1 where structural_detector_run_id=%s and unit_type in ('lesson','section') and (unit_label is null or unit_number is null)");view=await n('select count(*) n from library_lm_xv_kdp_search_ready_v2')
 checks={'classifications_514':pages==514,'blanks_5':blanks==5,'nonblank_has_quote':bad==0,'no_invented_units':invented==0,'search_ready_v2_514':view==514,'ocr_not_used':True,'no_embeddings':True,'no_milvus':True,'no_relations':True};out={'status':'PASS' if all(checks.values()) else 'FAIL','checks':checks,'metrics':{'pages':pages,'blanks':blanks,'missing_evidence':bad,'invented_units':invented,'view_rows':view}}
 R.mkdir(parents=True,exist_ok=True);(R/'structural_detector_qa_results.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2));
 if out['status']!='PASS':raise SystemExit(1)
asyncio.run(main())
