"""Deterministic marker metadata for LM II research nodes; never creates relations."""
from __future__ import annotations
import asyncio,re
import psycopg
from psycopg.rows import dict_row
from globalVar import POSTGRES_DSN
MARKERS=('Rashbam','Rashi','Tosafot','Mei HaNajal','Parparaot LeJojmá','Biur HaLikutim')
async def main():
 async with await psycopg.AsyncConnection.connect(POSTGRES_DSN,row_factory=dict_row) as c:
  async with c.cursor() as q:
   await q.execute("""select n.content_node_id,n.literal_text,n.content_type,n.node_role from library_content_nodes_v2 n join library_content_units_v2 u on u.content_unit_id=n.content_unit_id where u.document_id=(select id from library_documents where document_code='likutey_moharan_ii_spanish_bri')""")
   rows=await q.fetchall(); counts={'number':0,'commentary':0,'missing':0}
   for r in rows:
    text=r['literal_text'].lstrip(); start=text[:160]; m=re.match(r'(\d{1,3})[.)]\s',text)
    marker=next((x for x in MARKERS if x.casefold() in text.casefold()),None)
    if m:
     vals=('note_number',m.group(1),'explicit',int(m.group(1)),None,'explicit_numbered_start',start,True,False,.99,'deterministic_regex');counts['number']+=1
    elif marker:
     vals=('commentary_label',marker,'explicit',None,None,'explicit_commentary_label_start',start,False,False,.95,'deterministic_regex');counts['commentary']+=1
    elif r['node_role']=='satellite' and r['content_type'] in ('citable_unlinked_note','unlinked_footnote_fragment','probable_footnote_continuation'):
     vals=('none',None,'probable_continuation',None,None,'probable_unmarked_continuation',start,False,True,.62,'layout_detected');counts['missing']+=1
    else: continue
    await q.execute("update library_content_nodes_v2 set marker_kind=%s,marker_value=%s,marker_status=%s,visible_note_number=%s,probable_note_number=%s,note_start_status=%s,visible_start_text=%s,is_note_start=%s,is_continuation_candidate=%s,marker_confidence=%s,marker_detection_origin=%s where content_node_id=%s",(*vals,r['content_node_id']))
  await c.commit();print(counts)
asyncio.run(main())
