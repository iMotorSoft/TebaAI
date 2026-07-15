#!/usr/bin/env python3
"""Read-only probe for the LM XV KDP page-first column-aware view."""
import argparse, asyncio, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import psycopg
from globalVar import POSTGRES_DSN

async def main():
    p=argparse.ArgumentParser();p.add_argument('--pdf-page',type=int);p.add_argument('--query');p.add_argument('--hebrew',action='store_true');p.add_argument('--needs-layout-review',action='store_true');p.add_argument('--block-role');p.add_argument('--page-status');p.add_argument('--json',action='store_true');a=p.parse_args()
    clauses=[];args=[]
    if a.pdf_page:clauses.append('pdf_page=%s');args.append(a.pdf_page)
    if a.query:clauses.append('(normalized_text ilike %s or raw_text ilike %s)');args += [f'%{a.query}%',f'%{a.query}%']
    if a.hebrew:clauses.append('has_hebrew')
    if a.needs_layout_review:clauses.append('needs_layout_review')
    if a.block_role:clauses.append('%s = any(block_role_candidates)');args.append(a.block_role)
    if a.page_status:clauses.append('page_status=%s');args.append(a.page_status)
    where=(' where '+' and '.join(clauses)) if clauses else ''
    sql='select pdf_page,page_status,left(raw_text,320) quote,reading_order_method,block_count,warnings,source_run_id from library_lm_xv_kdp_search_ready_v1'+where+' order by pdf_page limit 50'
    async with await psycopg.AsyncConnection.connect(POSTGRES_DSN,row_factory=psycopg.rows.dict_row) as c:
        async with c.cursor() as q:await q.execute(sql,args);rows=await q.fetchall()
    print(json.dumps(rows,ensure_ascii=False,indent=2) if a.json else '\n'.join(f"p.{x['pdf_page']} [{x['page_status']}] {x['quote'][:150]}" for x in rows))
asyncio.run(main())
