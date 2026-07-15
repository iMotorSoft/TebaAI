"""Read-only final investigative search across Likutey Halajot evidence layers."""
from __future__ import annotations
import argparse,asyncio,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import psycopg
from psycopg.rows import dict_row
from globalVar import POSTGRES_DSN
async def main():
 p=argparse.ArgumentParser()
 for arg in ('--query','--halakhah','--note-number','--record-type','--reference','--normalized','--reference-kind','--resolution-decision','--resolution-method','--zone-type','--final-status'):p.add_argument(arg)
 p.add_argument('--pdf-page',type=int);p.add_argument('--printed-page',type=int);p.add_argument('--include-audit',action='store_true');a=p.parse_args();clauses=[];params=[]
 for col,val in [('halakhah_header_hint',a.halakhah),('visible_note_number',a.note_number),('search_record_type',a.record_type),('surface_form',a.reference),('normalized_reference_name',a.normalized),('reference_kind',a.reference_kind),('resolution_decision',a.resolution_decision),('resolution_method',a.resolution_method),('fine_zone_type',a.zone_type),('final_page_status',a.final_status)]:
  if val:clauses.append(f'{col} ilike %s');params.append(f'%{val}%')
 if a.query:clauses.append("coalesce(page_text,fine_zone_quote,note_source_quote,nominal_reference_quote,resolution_quote,'') ilike %s");params.append(f'%{a.query}%')
 if a.pdf_page:clauses.append('pdf_page=%s');params.append(a.pdf_page)
 if a.printed_page:clauses.append('printed_page=%s');params.append(a.printed_page)
 if not clauses:p.error('provide at least one filter')
 view='library_likutey_halajot_investigative_audit_v1' if a.include_audit else 'library_likutey_halajot_investigative_search_v1'
 async with await psycopg.AsyncConnection.connect(POSTGRES_DSN,row_factory=dict_row) as c:
  async with c.cursor() as q:
   await q.execute(f'select * from {view} where '+' and '.join(clauses)+' order by pdf_page,search_record_type',params)
   print(json.dumps(await q.fetchall(),ensure_ascii=False,default=str,indent=2))
if __name__=='__main__':asyncio.run(main())
