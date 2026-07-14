"""Create page-anchored, searchable satellite extracts for visible commentators."""
from __future__ import annotations
import asyncio, hashlib, re
import psycopg
from psycopg.rows import dict_row
from globalVar import POSTGRES_DSN

MARKERS={"Rashbam":("rashbam_commentary","rabbinic_commentary"),"Rashi":("marginal_rabbinic_commentary","rabbinic_commentary"),"Tosafot":("marginal_rabbinic_commentary","rabbinic_commentary"),"Mei HaNajal":("source_commentary","secondary_explanatory"),"Parparaot LeJojmá":("source_commentary","secondary_explanatory"),"Biur HaLikutim":("source_commentary","secondary_explanatory")}
async def main():
 async with await psycopg.AsyncConnection.connect(POSTGRES_DSN,row_factory=dict_row) as c:
  async with c.cursor() as q:
   await q.execute("""select n.content_node_id,n.content_unit_id,n.page_anchor_id,n.literal_text,n.language from library_content_nodes_v2 n join library_content_units_v2 u on u.content_unit_id=n.content_unit_id where u.document_id=(select id from library_documents where document_code='likutey_moharan_ii_spanish_bri') and n.node_role='primary'""")
   rows=await q.fetchall(); count=0
   for r in rows:
    for marker,(typ,authority) in MARKERS.items():
     if marker.casefold() not in r['literal_text'].casefold(): continue
     # paragraph containing marker: derivative evidence, original primary remains untouched
     paras=re.split(r'\n\s*\n',r['literal_text']); text=next((p for p in paras if marker.casefold() in p.casefold()),r['literal_text'])
     norm=' '.join(text.split()); h=hashlib.sha256((marker+norm).encode()).hexdigest()
     await q.execute("""insert into library_content_nodes_v2 (content_unit_id,node_role,content_type,relation_to_primary,authority_level,language,script,literal_text,normalized_text,literal_hash,page_anchor_id,node_order,citable,metadata_json) select %s,'satellite',%s,'comments_on_source',%s,%s,'latin',%s,%s,%s,%s,999,true,jsonb_build_object('investigative_derivative',true,'source_or_commentator',%s::text,'evidence_origin','deterministic_marker') where not exists(select 1 from library_content_nodes_v2 where literal_hash=%s and metadata_json->>'source_or_commentator'=%s::text) returning content_node_id""",(r['content_unit_id'],typ,authority,r['language'],text,norm,h,r['page_anchor_id'],marker,h,marker))
     node=await q.fetchone()
     if node:
      nid=node['content_node_id']; await q.execute("insert into library_literal_spans_v2(content_node_id,start_char,end_char,literal_text,normalized_text,hash) values(%s,0,%s,%s,%s,%s)",(nid,len(text),text,norm,h)); await q.execute("insert into library_semantic_units_v2(content_node_id,text,text_hash,chunk_order,chunker_name,language) values(%s,%s,%s,1,'investigative_marker_extract',%s)",(nid,text,h,r['language'])); count+=1
  await c.commit(); print({'created':count})
asyncio.run(main())
