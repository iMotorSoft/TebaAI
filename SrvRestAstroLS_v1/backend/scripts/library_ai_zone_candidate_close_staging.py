"""Close staging candidates without writing authoritative corpus objects."""
from __future__ import annotations
import asyncio
import psycopg
from globalVar import POSTGRES_DSN
async def main():
 async with await psycopg.AsyncConnection.connect(POSTGRES_DSN) as c:
  async with c.cursor() as q:
   await q.execute("update library_ai_zone_candidates_v2 set final_decision=case when validation_decision='reject_candidate' then 'rejected_candidate' else 'page_literal_only' end,final_decision_reason='staging closes to page-first unless future explicit promotion',final_decision_at=now(),final_decision_run_id='lmii_final_ingestion_v1',archived_for_audit=true where final_decision is null")
   print({'closed':q.rowcount})
  await c.commit()
asyncio.run(main())
