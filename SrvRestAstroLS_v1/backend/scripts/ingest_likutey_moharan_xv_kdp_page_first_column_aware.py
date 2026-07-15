from __future__ import annotations
import asyncio,hashlib,json,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import fitz,psycopg
from psycopg.rows import dict_row
from globalVar import POSTGRES_DSN
from preflight_likutey_moharan_xv_kdp import DEFAULT,EXPECTED_BASENAME,LH_SHA256
RUN='likutey_moharan_xv_kdp_page_first_column_aware_v1';ROOT=Path(__file__).resolve().parents[3];R=ROOT/'data/reports/breslov/2026-07-15-lm-xv-kdp-page-first-column-aware-v1'
def norm(t):return re.sub(r'\s+',' ',t).strip()
async def main():
 sha=hashlib.sha256(DEFAULT.read_bytes()).hexdigest()
 if EXPECTED_BASENAME not in DEFAULT.name or sha==LH_SHA256:raise RuntimeError('source guard failed')
 rules={x['pdf_page']:x for x in json.loads((R/'column_rules_report.json').read_text())['pages']};doc=fitz.open(DEFAULT);inserted_pages=inserted_blocks=0
 async with await psycopg.AsyncConnection.connect(POSTGRES_DSN,row_factory=dict_row) as c:
  async with c.cursor() as q:
   await q.execute("select id,collection_id,knowledge_scope_id,organization_id,workspace_id,project_id from library_documents where document_code='likutey_halajot_interior_final'");base=await q.fetchone();await q.execute("select id from library_documents where document_code='likutey_moharan_xv_kdp'");row=await q.fetchone()
   if row:did=row['id']
   else:
    await q.execute("insert into library_documents(id,collection_id,title,language,source_type,source_path,source_filename,source_mime_type,source_size_bytes,source_sha256,status,organization_id,workspace_id,project_id,knowledge_scope_id,document_code,canonical_text_role) values(gen_random_uuid(),%s,'Likutey Moharán XV KDP','es','pdf',%s,%s,'application/pdf',%s,%s,'test_candidate',%s,%s,%s,%s,'likutey_moharan_xv_kdp','candidate') returning id",(base['collection_id'],str(DEFAULT),DEFAULT.name,DEFAULT.stat().st_size,sha,base['organization_id'],base['workspace_id'],base['project_id'],base['knowledge_scope_id']));did=(await q.fetchone())['id']
   for n,p in enumerate(doc,1):
    text=p.get_text('text') or '';raw=p.get_text('blocks',sort=True) or [];r=rules[n];nt=norm(text);status='blank' if not nt else ('front_matter' if n<20 else 'back_matter' if n>=490 else 'textual');await q.execute("insert into library_lm_xv_kdp_pages_v1(document_id,source_run_id,pdf_page,page_status,raw_text,normalized_text,text_hash,extraction_engine,extraction_quality_score,has_hebrew,has_latin,block_count,reading_order_method,column_count_estimate,warnings) values(%s,%s,%s,%s,%s,%s,%s,'PyMuPDF',.95,%s,%s,%s,%s,%s,'[]') on conflict(source_run_id,pdf_page) do update set raw_text=excluded.raw_text,normalized_text=excluded.normalized_text,text_hash=excluded.text_hash,block_count=excluded.block_count,reading_order_method=excluded.reading_order_method,column_count_estimate=excluded.column_count_estimate",(did,RUN,n,status,text,nt,hashlib.sha256(text.encode()).hexdigest(),bool(re.search(r'[\u0590-\u05ff]',text)),bool(re.search(r'[A-Za-z]',text)),len(raw),r['reading_order_method'],r['column_count_estimate']));inserted_pages+=q.rowcount
    for i,b in enumerate(raw):
     t=b[4].strip()
     if not t:continue
     role='hebrew_text' if len(re.findall(r'[\u0590-\u05ff]',t))>len(t)*.35 else 'main_text';await q.execute("insert into library_lm_xv_kdp_page_blocks_v1(document_id,source_run_id,pdf_page,block_index_original,block_index_ordered,reading_order_method,bbox,text,normalized_text,text_hash,block_role_candidate,script_mix,confidence) values(%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s::jsonb,.8) on conflict(source_run_id,pdf_page,block_index_original) do update set text=excluded.text,normalized_text=excluded.normalized_text,bbox=excluded.bbox",(did,RUN,n,i,i,r['reading_order_method'],json.dumps(b[:4]),t,norm(t),hashlib.sha256(t.encode()).hexdigest(),role,json.dumps({'hebrew':len(re.findall(r'[\u0590-\u05ff]',t)),'latin':len(re.findall(r'[A-Za-z]',t))})));inserted_blocks+=q.rowcount
  await c.commit()
 report={'document_id':str(did),'run':RUN,'pages':514,'inserted_or_updated_pages':inserted_pages,'inserted_or_updated_blocks':inserted_blocks,'ocr_layout_assist_used':False,'embeddings':False,'milvus':False};(R/'lm_xv_page_first_ingest_report.json').write_text(json.dumps(report,indent=2));(R/'lm_xv_page_first_ingest_summary.md').write_text('# Ingest\n\n'+json.dumps(report,indent=2));print(json.dumps(report))
asyncio.run(main())
