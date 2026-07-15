"""Read-only probe for investigative nominal-reference resolutions."""
from __future__ import annotations
import argparse,asyncio,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import psycopg
from psycopg.rows import dict_row
from globalVar import POSTGRES_DSN
async def main():
 p=argparse.ArgumentParser();[p.add_argument(x) for x in ('--reference','--normalized','--decision','--method','--kind','--note-number','--halakhah','--query')];p.add_argument('--pdf-page',type=int);a=p.parse_args(); clauses=[];params=[]
 for col,val in [('surface_form',a.reference),('resolved_normalized_reference_name',a.normalized),('resolution_decision',a.decision),('resolution_method',a.method),('resolved_reference_kind',a.kind),('visible_note_number',a.note_number),('halakhah_header_hint',a.halakhah),('text_quote',a.query)]:
  if val:clauses.append(f'{col} ilike %s');params.append(f'%{val}%')
 if a.pdf_page:clauses.append('pdf_page=%s');params.append(a.pdf_page)
 if not clauses:p.error('provide a filter')
 async with await psycopg.AsyncConnection.connect(POSTGRES_DSN,row_factory=dict_row) as c:
  async with c.cursor() as q:await q.execute('select * from library_likutey_halajot_nominal_reference_resolution_search_v1 where '+' and '.join(clauses)+' order by pdf_page',params);print(json.dumps(await q.fetchall(),ensure_ascii=False,default=str,indent=2))
if __name__=='__main__':asyncio.run(main())
