"""Read-only probe over quote-verified Likutey Halajot fine zones."""
from __future__ import annotations
import argparse, asyncio, json
import psycopg
from psycopg.rows import dict_row
from globalVar import POSTGRES_DSN

async def main():
    p=argparse.ArgumentParser();p.add_argument('--zone-type');p.add_argument('--halakhah');p.add_argument('--query');a=p.parse_args()
    if not any((a.zone_type,a.halakhah,a.query)): p.error('provide --zone-type, --halakhah, or --query')
    sql="select pdf_page,zone_type,marker_value,text_quote,validation_status from library_likutey_halajot_fine_zones_v1 where fine_zone_run_id='likutey_halajot_fine_zone_detector_v1_20260714'";params=[]
    if a.zone_type: sql+=' and zone_type=%s';params.append(a.zone_type)
    if a.halakhah: sql+=" and zone_type='halakhah_header' and text_quote ilike %s";params.append(f'%{a.halakhah}%')
    if a.query: sql+=' and text_quote ilike %s';params.append(f'%{a.query}%')
    async with await psycopg.AsyncConnection.connect(POSTGRES_DSN,row_factory=dict_row) as c:
        async with c.cursor() as q:
            await q.execute(sql+' order by pdf_page',params);print(json.dumps(await q.fetchall(),ensure_ascii=False,default=str))
asyncio.run(main())
