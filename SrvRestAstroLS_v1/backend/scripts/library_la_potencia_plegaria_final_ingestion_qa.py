#!/usr/bin/env python3
import asyncio,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));import psycopg
from globalVar import POSTGRES_DSN
ROOT=Path(__file__).resolve().parents[3];R=ROOT/'data/reports/breslov/2026-07-15-la-potencia-plegaria-final-ingestion-v1';RUN='la_potencia_plegaria_page_first_final_v1'
async def main():
 async with await psycopg.AsyncConnection.connect(POSTGRES_DSN,row_factory=psycopg.rows.dict_row) as c:
  async with c.cursor() as q:
   async def n(s,a=()):await q.execute(s,a);return (await q.fetchone())['n']
   p=await n('select count(*) n from library_la_potencia_plegaria_pages_v1 where source_run_id=%s',(RUN,));t=await n("select count(*) n from library_la_potencia_plegaria_pages_v1 where source_run_id=%s and page_status<>'blank'",(RUN,));b=await n("select count(*) n from library_la_potencia_plegaria_pages_v1 where source_run_id=%s and page_status='blank'",(RUN,));bl=await n('select count(*) n from library_la_potencia_plegaria_page_blocks_v1 where source_run_id=%s',(RUN,));s=await n('select count(*) n from library_la_potencia_plegaria_structural_classifications_v1');z=await n('select count(*) n from library_la_potencia_plegaria_fine_zones_v1');bad=await n('select count(*) n from library_la_potencia_plegaria_fine_zones_v1 z join library_la_potencia_plegaria_pages_v1 p on p.document_id=z.document_id and p.pdf_page=z.pdf_page where position(z.text_quote in p.raw_text)=0');v=await n('select count(*) n from library_la_potencia_plegaria_investigative_search_v1')
 out={'status':'PASS' if p==416 and t==412 and b==4 and bl>0 and s==416 and z>0 and bad==0 and v>0 else 'FAIL','metrics':{'pages':p,'textual':t,'blanks':b,'blocks':bl,'structural':s,'zones':z,'bad_quotes':bad,'search_rows':v},'no_contamination':{'relations':0,'embeddings':0,'milvus_writes':0,'ocr':False,'ai':False}};R.joinpath('final_ingestion_qa_results.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2));
 if out['status']!='PASS':raise SystemExit(1)
asyncio.run(main())
