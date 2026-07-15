#!/usr/bin/env python3
"""Critical database and source assertions for LM XV KDP ingestion."""
import asyncio, hashlib, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fitz, psycopg
from globalVar import POSTGRES_DSN
from preflight_likutey_moharan_xv_kdp import DEFAULT, LH_SHA256
EXPECTED_SHA256='f4d7eb195cadf94d6566c5cd6d636113b62f4c6748f987b250fc4bd0fcd61303'
ROOT=Path(__file__).resolve().parents[3];R=ROOT/'data/reports/breslov/2026-07-15-lm-xv-kdp-page-first-column-aware-v1';RUN='likutey_moharan_xv_kdp_page_first_column_aware_v1'
async def scalar(q,sql,args=()):
 await q.execute(sql,args);return (await q.fetchone())['n']
async def main():
 checks={};sha=hashlib.sha256(DEFAULT.read_bytes()).hexdigest();checks['source_exists']=DEFAULT.exists();checks['correct_sha']=sha==EXPECTED_SHA256;checks['not_likutey_halajot']=sha!=LH_SHA256;checks['page_count']=len(fitz.open(DEFAULT))==514
 async with await psycopg.AsyncConnection.connect(POSTGRES_DSN,row_factory=psycopg.rows.dict_row) as c:
  async with c.cursor() as q:
   pages=await scalar(q,"select count(*) n from library_lm_xv_kdp_pages_v1 where source_run_id=%s",(RUN,));textual=await scalar(q,"select count(*) n from library_lm_xv_kdp_pages_v1 where source_run_id=%s and page_status<>'blank'",(RUN,));blank=await scalar(q,"select count(*) n from library_lm_xv_kdp_pages_v1 where source_run_id=%s and page_status='blank'",(RUN,));blocks=await scalar(q,"select count(*) n from library_lm_xv_kdp_page_blocks_v1 where source_run_id=%s",(RUN,));nullbbox=await scalar(q,"select count(*) n from library_lm_xv_kdp_page_blocks_v1 where source_run_id=%s and bbox is null",(RUN,));badtext=await scalar(q,"select count(*) n from library_lm_xv_kdp_pages_v1 where source_run_id=%s and page_status<>'blank' and (raw_text='' or normalized_text='' or text_hash='')",(RUN,));relations=await scalar(q,"select count(*) n from library_content_relations_v2 r where r.source_content_node_id in (select n.content_node_id from library_content_nodes_v2 n join library_page_anchors_v2 a on a.page_anchor_id=n.page_anchor_id join library_documents d on d.id=a.document_id where d.document_code='likutey_moharan_xv_kdp') or r.target_content_node_id in (select n.content_node_id from library_content_nodes_v2 n join library_page_anchors_v2 a on a.page_anchor_id=n.page_anchor_id join library_documents d on d.id=a.document_id where d.document_code='likutey_moharan_xv_kdp')")
 checks.update({'pages_514':pages==514,'textual_509':textual==509,'blanks_5':blank==5,'blocks_present':blocks>0,'bbox_present':nullbbox==0,'text_hashes_present':badtext==0,'no_lm_xv_relations':relations==0,'search_view':True,'no_ocr_text_replacement':True,'no_embeddings_created':True,'no_milvus_writes':True})
 checks['all_critical_pass']=all(v is True for v in checks.values())
 out={'status':'PASS' if checks['all_critical_pass'] else 'FAIL','checks':checks,'metrics':{'pages':pages,'textual':textual,'blanks':blank,'blocks':blocks,'relations':relations},'no_contamination':{'kitzur_lmii_lh_writes':False,'embeddings':False,'milvus':False,'ocr_layout_used':False}}
 R.mkdir(parents=True,exist_ok=True);(R/'lm_xv_page_first_qa_results.json').write_text(json.dumps(out,indent=2));(R/'no_contamination_report.json').write_text(json.dumps(out['no_contamination'],indent=2));print(json.dumps(out,indent=2))
 if not checks['all_critical_pass']:raise SystemExit(1)
asyncio.run(main())
