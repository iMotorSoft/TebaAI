"""Conservative note segmentation: explicit line-start numbers only."""
from __future__ import annotations
import asyncio,hashlib,json,re,psycopg
from psycopg.rows import dict_row
from globalVar import POSTGRES_DSN
RUN='likutey_halajot_note_source_detector_v1_20260714'
async def main():
 async with await psycopg.AsyncConnection.connect(POSTGRES_DSN,row_factory=dict_row) as c:
  async with c.cursor() as q:
   await q.execute("select z.id,z.document_id,z.pdf_page,z.page_anchor_id,z.text_quote,n.literal_text from library_likutey_halajot_fine_zones_v1 z join library_content_nodes_v2 n on n.page_anchor_id=z.page_anchor_id where z.fine_zone_run_id='likutey_halajot_fine_zone_detector_v1_20260714' and z.zone_type='notes_sources_block'")
   rows=await q.fetchall();ins=segments=0
   for r in rows:
    block=r['literal_text'][r['literal_text'].find(r['text_quote']):]
    starts=list(re.finditer(r'(?m)^\s*(\d{1,3})\s+(?=[A-ZÁÉÍÓÚÑ“\[])',block))
    items=[]
    for i,m in enumerate(starts):
     end=starts[i+1].start() if i+1<len(starts) else len(block);items.append(('numbered_note','note',m.group(1),block[m.start():end].strip(),m.start(),end,.9,'validated'))
    if not items:items=[('unsegmented_notes_block','block',None,r['text_quote'],0,len(r['text_quote']),.85,'block_only')]
    for typ,role,num,quote,a,b,conf,status in items:
     if quote and quote in r['literal_text']:
      await q.execute("insert into library_likutey_halajot_note_source_units_v1(document_id,pdf_page,page_anchor_id,parent_fine_zone_id,note_source_run_id,unit_type,unit_role,visible_note_number,text_quote,char_start,char_end,quote_hash,confidence,validation_status,review_status,raw_detection) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'not_required',%s::jsonb) on conflict do nothing",(r['document_id'],r['pdf_page'],r['page_anchor_id'],r['id'],RUN,typ,role,num,quote,a,b,hashlib.sha256(quote.encode()).hexdigest(),conf,status,json.dumps({'explicit_line_number':num is not None})));ins+=q.rowcount;segments+=typ=='numbered_note'
  await c.commit();print(json.dumps({'run':RUN,'inserted':ins,'numbered':segments,'parents':len(rows)}))
asyncio.run(main())
