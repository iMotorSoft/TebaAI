#!/usr/bin/env python3
import argparse,asyncio,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import psycopg
from globalVar import POSTGRES_DSN
async def main():
 p=argparse.ArgumentParser();p.add_argument('--pdf-page',type=int);p.add_argument('--query');p.add_argument('--document-part');p.add_argument('--structural-status');p.add_argument('--hebrew',action='store_true');p.add_argument('--reading-order');p.add_argument('--unit-type');p.add_argument('--unit-label');p.add_argument('--json',action='store_true');a=p.parse_args();cs=[];vs=[]
 for key,col in [('pdf_page','pdf_page'),('document_part','document_part'),('structural_status','structural_status'),('reading_order','reading_order_method'),('unit_type','unit_type'),('unit_label','unit_label')]:
  v=getattr(a,key)
  if v is not None:cs.append(f'{col}=%s');vs.append(v)
 if a.query:cs.append('(raw_text ilike %s or normalized_text ilike %s)');vs += [f'%{a.query}%',f'%{a.query}%']
 if a.hebrew:cs.append('has_hebrew')
 sql='select pdf_page,document_part,structural_status,unit_type,unit_label,left(raw_text,260) quote,reading_order_method,evidence_quote,confidence from library_lm_xv_kdp_search_ready_v2'+((' where '+' and '.join(cs)) if cs else '')+' order by pdf_page limit 50'
 async with await psycopg.AsyncConnection.connect(POSTGRES_DSN,row_factory=psycopg.rows.dict_row) as c:
  async with c.cursor() as q:await q.execute(sql,vs);rows=await q.fetchall()
 print(json.dumps(rows,ensure_ascii=False,indent=2,default=str) if a.json else '\n'.join(f"p.{r['pdf_page']} {r['document_part']} {r['quote'][:100]}" for r in rows))
asyncio.run(main())
