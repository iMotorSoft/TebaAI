"""Safe page-first LM II ingestion: unknown structure never prevents citation."""
from __future__ import annotations
import asyncio,fitz,hashlib
import psycopg
from psycopg.rows import dict_row
from globalVar import POSTGRES_DSN
from modules.library.investigative_model import normalize_literal,stable_hash
SOURCE='/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY MOHARAN II Interior.pdf'; DOC='likutey_moharan_ii_spanish_bri'
async def main():
 doc=fitz.open(SOURCE)
 async with await psycopg.AsyncConnection.connect(POSTGRES_DSN,row_factory=dict_row) as c:
  async with c.cursor() as q:
   await q.execute("select id from library_documents where document_code=%s",(DOC,)); did=(await q.fetchone())['id']
   await q.execute("select content_unit_id from library_content_units_v2 where document_id=%s and canonical_ref='LMII'",(did,)); work=(await q.fetchone())['content_unit_id']
   done=blank=0
   for n,p in enumerate(doc,1):
    text=p.get_text('text').strip()
    await q.execute("insert into library_page_anchors_v2(source_file_id,document_id,edition_id,pdf_page_number,printed_page_number,page_label,confidence,metadata_json) values(%s,%s,'lmii_page_first_v1',%s,%s,%s,.8,'{}') on conflict(document_id,pdf_page_number,edition_id) do update set pdf_page_number=excluded.pdf_page_number returning page_anchor_id",(did,did,n,n-10,str(n-10))); anchor=(await q.fetchone())['page_anchor_id']
    if not text: blank+=1;continue
    ref=f'LMII PAGE {n}';await q.execute("insert into library_content_units_v2(parent_content_unit_id,document_id,unit_type,canonical_ref,title,order_index,language_original,is_breslov_primary_source,is_direct_rebbe_nachman,metadata_json) values(%s,%s,'page',%s,%s,%s,'und',false,false,jsonb_build_object('structural_status','unclassified')) on conflict(document_id,canonical_ref) where canonical_ref is not null do update set title=excluded.title returning content_unit_id",(work,did,ref,f'PDF page {n}',n)); unit=(await q.fetchone())['content_unit_id']; norm=normalize_literal(text);h=stable_hash(text)
    await q.execute("insert into library_content_nodes_v2(content_unit_id,node_role,content_type,relation_to_primary,authority_level,language,script,literal_text,normalized_text,literal_hash,page_anchor_id,node_order,citable,metadata_json,link_status,review_status) select %s,'satellite','citable_page_text','same_page','secondary_explanatory','und','latin',%s,%s,%s,%s,1,true,jsonb_build_object('structural_status','unclassified','classification_status','fallback_page_level','source_run_id','lmii_full_page_first_v1'), 'unlinked_citable','needs_structural_classification' where not exists(select 1 from library_content_nodes_v2 where page_anchor_id=%s and metadata_json->>'source_run_id'='lmii_full_page_first_v1') returning content_node_id",(unit,text,norm,h,anchor,anchor)); r=await q.fetchone()
    if r:
     nid=r['content_node_id'];await q.execute("insert into library_literal_spans_v2(content_node_id,start_char,end_char,literal_text,normalized_text,hash) values(%s,0,%s,%s,%s,%s)",(nid,len(text),text,norm,h));await q.execute("insert into library_semantic_units_v2(content_node_id,text,text_hash,chunk_order,chunker_name,language) values(%s,%s,%s,1,'page_first_v1','und')",(nid,text,h));done+=1
  await c.commit();print({'pages':len(doc),'text_pages':done,'blank':blank})
asyncio.run(main())
