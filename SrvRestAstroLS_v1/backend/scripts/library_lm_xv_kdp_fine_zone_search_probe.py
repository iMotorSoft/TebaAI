#!/usr/bin/env python3
import argparse,asyncio,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));import psycopg
from globalVar import POSTGRES_DSN
async def main():
 p=argparse.ArgumentParser();p.add_argument('--pdf-page',type=int);p.add_argument('--query');p.add_argument('--zone-type');p.add_argument('--document-part');p.add_argument('--hebrew',action='store_true');p.add_argument('--validation-status');p.add_argument('--reading-order');p.add_argument('--json',action='store_true');a=p.parse_args();cs=[];vs=[]
 for k,c in [('pdf_page','pdf_page'),('zone_type','zone_type'),('document_part','document_part'),('validation_status','validation_status'),('reading_order','reading_order_method')]:
  v=getattr(a,k)
  if v is not None:cs.append(c+'=%s');vs.append(v)
 if a.query:cs.append('(text_quote ilike %s or raw_text ilike %s)');vs += [f'%{a.query}%',f'%{a.query}%']
 if a.hebrew:cs.append('has_hebrew')
 sql='select pdf_page,document_part,zone_type,zone_role,authority_level,left(text_quote,240) quote,validation_status,confidence,reading_order_method from library_lm_xv_kdp_search_ready_v3'+((' where '+' and '.join(cs)) if cs else '')+' order by pdf_page limit 80'
 async with await psycopg.AsyncConnection.connect(POSTGRES_DSN,row_factory=psycopg.rows.dict_row) as c:
  async with c.cursor() as q:await q.execute(sql,vs);rows=await q.fetchall()
 print(json.dumps(rows,ensure_ascii=False,indent=2,default=str) if a.json else '\n'.join(f"p.{r['pdf_page']} {r['zone_type']} {r['quote'][:100]}" for r in rows))
asyncio.run(main())
