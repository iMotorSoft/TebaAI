#!/usr/bin/env python3
import argparse,asyncio,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));import psycopg
from globalVar import POSTGRES_DSN
async def main():
 p=argparse.ArgumentParser();p.add_argument('--query');p.add_argument('--pdf-page',type=int);p.add_argument('--document-part');p.add_argument('--zone-type');p.add_argument('--note-number');p.add_argument('--reference');p.add_argument('--normalized');p.add_argument('--json',action='store_true');a=p.parse_args();c=[];v=[]
 for k,col in [('pdf_page','pdf_page'),('document_part','document_part'),('zone_type','zone_type'),('note_number','note_number'),('reference','surface_form'),('normalized','normalized_reference_name')]:
  x=getattr(a,k)
  if x is not None:c.append(col+'=%s');v.append(x)
 if a.query:c.append('quote ilike %s');v.append('%'+a.query+'%')
 sql='select * from library_la_potencia_plegaria_investigative_search_v1'+((' where '+' and '.join(c)) if c else '')+' order by pdf_page limit 50'
 async with await psycopg.AsyncConnection.connect(POSTGRES_DSN,row_factory=psycopg.rows.dict_row) as x:
  async with x.cursor() as q:await q.execute(sql,v);r=await q.fetchall()
 print(json.dumps(r,ensure_ascii=False,indent=2,default=str) if a.json else '\n'.join(f"p.{x['pdf_page']} {x['search_record_type']} {x['quote'][:110]}" for x in r))
asyncio.run(main())
