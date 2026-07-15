"""Critical coverage and literal-evidence QA for final investigative search."""
from __future__ import annotations
import asyncio,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import psycopg
from psycopg.rows import dict_row
from globalVar import POSTGRES_DSN
async def main():
 async with await psycopg.AsyncConnection.connect(POSTGRES_DSN,row_factory=dict_row) as c:
  async with c.cursor() as q:
   await q.execute("""select (select count(*) from library_likutey_halajot_investigative_search_v1 where search_record_type='page_literal') page_literals,(select count(*) from library_likutey_halajot_investigative_search_v1 where search_record_type in ('fine_zone','note_source_unit','nominal_reference','resolved_reference') and coalesce(fine_zone_quote,note_source_quote,nominal_reference_quote,resolution_quote,'')='') missing_quote,(select count(*) from library_likutey_halajot_investigative_search_v1 where is_authoritative_relation) bad_relation,(select count(*) from library_likutey_halajot_investigative_search_v1 where resolution_decision='rejected_false_positive') leaked_rejected,(select count(*) from library_likutey_halajot_investigative_audit_v1 where resolution_decision='rejected_false_positive') audit_rejected""")
   r=await q.fetchone()
 print(json.dumps(r))
 if r['page_literals']!=268 or any(r[x] for x in ('missing_quote','bad_relation','leaked_rejected')) or r['audit_rejected']!=68:sys.exit(1)
if __name__=='__main__':asyncio.run(main())
