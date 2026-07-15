"""Critical preservation and quote evidence checks for Fine Zone V1."""
from __future__ import annotations
import asyncio,json,psycopg
from psycopg.rows import dict_row
from globalVar import POSTGRES_DSN

async def main():
    async with await psycopg.AsyncConnection.connect(POSTGRES_DSN,row_factory=dict_row) as c:
        async with c.cursor() as q:
            await q.execute("select (select count(*) from library_likutey_halajot_page_final_status_v2) pages,(select count(*) from library_likutey_halajot_search_ready_v2) text_pages,(select count(*) from library_likutey_halajot_fine_zones_v1) zones,(select count(*) from library_likutey_halajot_fine_zones_v1 z join library_content_nodes_v2 n on n.page_anchor_id=z.page_anchor_id where position(z.text_quote in n.literal_text)=0) bad_quotes,(select count(*) from library_likutey_halajot_fine_zones_v1 where visible_note_number is not null) notes")
            r=await q.fetchone();r['pass']=r['pages']==284 and r['text_pages']==268 and r['zones']>0 and r['bad_quotes']==0 and r['notes']==0;print(json.dumps(r))
            if not r['pass']: raise SystemExit(1)
asyncio.run(main())
