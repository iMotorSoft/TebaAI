"""Controlled page-first ingestion for Likutey Halajot; no structural fallback."""
from __future__ import annotations
import asyncio,hashlib
from pathlib import Path
import fitz,psycopg
from psycopg.rows import dict_row
from globalVar import POSTGRES_DSN
from modules.library.investigative_model import normalize_literal,stable_hash
PDF=Path('/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf'); CODE='likutey_halajot_interior_final'; RUN='likutey_halajot_page_first_v1'; EDITION='likutey_halajot_page_first_v1'
async def main():
 d=fitz.open(PDF)
 async with await psycopg.AsyncConnection.connect(POSTGRES_DSN,row_factory=dict_row) as c:
  async with c.cursor() as q:
   await q.execute('select id,collection_id,knowledge_scope_id,organization_id,workspace_id,project_id from library_documents where document_code=%s',(CODE,));docrow=await q.fetchone()
   if not docrow:
    await q.execute("select collection_id,knowledge_scope_id,organization_id,workspace_id,project_id from library_documents where document_code='likutey_moharan_ii_spanish_bri'");t=await q.fetchone();await q.execute("insert into library_documents(id,collection_id,title,language,source_type,source_path,source_filename,source_mime_type,source_size_bytes,source_sha256,status,organization_id,workspace_id,project_id,knowledge_scope_id,document_code,canonical_text_role) values(gen_random_uuid(),%s,'Likutey Halajot','es','pdf',%s,%s,'application/pdf',%s,%s,'test_candidate',%s,%s,%s,%s,%s,'candidate') returning id,collection_id,knowledge_scope_id,organization_id,workspace_id,project_id",(t['collection_id'],str(PDF),PDF.name,PDF.stat().st_size,hashlib.sha256(PDF.read_bytes()).hexdigest(),t['organization_id'],t['workspace_id'],t['project_id'],t['knowledge_scope_id'],CODE));docrow=await q.fetchone()
   did=docrow['id'];await q.execute("insert into library_content_units_v2(document_id,unit_type,canonical_ref,title,order_index,language_original,is_breslov_primary_source,is_direct_rebbe_nachman,metadata_json) values(%s,'work','LH','Likutey Halajot',0,'he',true,false,'{}') on conflict(document_id,canonical_ref) where canonical_ref is not null do update set title=excluded.title returning content_unit_id",(did,));work=(await q.fetchone())['content_unit_id'];textpages=blank=0
   for i,p in enumerate(d,1):
    text=p.get_text('text').replace('\x00', '').strip();await q.execute("insert into library_page_anchors_v2(source_file_id,document_id,edition_id,pdf_page_number,page_label,confidence,metadata_json) values(%s,%s,%s,%s,%s,.9,'{}') on conflict(document_id,pdf_page_number,edition_id) do update set page_label=excluded.page_label returning page_anchor_id",(did,did,EDITION,i,str(i)));a=(await q.fetchone())['page_anchor_id']
    if not text:blank+=1;continue
    ref=f'LH PAGE {i}';await q.execute("insert into library_content_units_v2(parent_content_unit_id,document_id,unit_type,canonical_ref,title,order_index,language_original,is_breslov_primary_source,is_direct_rebbe_nachman,metadata_json) values(%s,%s,'page',%s,%s,%s,'und',false,false,jsonb_build_object('structural_status','unclassified')) on conflict(document_id,canonical_ref) where canonical_ref is not null do update set title=excluded.title returning content_unit_id",(work,did,ref,f'PDF page {i}',i));unit=(await q.fetchone())['content_unit_id'];n=normalize_literal(text);h=stable_hash(text)
    await q.execute("insert into library_content_nodes_v2(content_unit_id,node_role,content_type,relation_to_primary,authority_level,language,script,literal_text,normalized_text,literal_hash,page_anchor_id,node_order,citable,metadata_json,link_status,review_status) select %s,'satellite','citable_page_text','same_page','secondary_explanatory','und','latin',%s,%s,%s,%s,1,true,jsonb_build_object('source_run_id',%s::text,'structural_status','unclassified','classification_status','fallback_page_level'),'unlinked_citable','needs_structural_classification' where not exists(select 1 from library_content_nodes_v2 where page_anchor_id=%s and metadata_json->>'source_run_id'=%s::text) returning content_node_id",(unit,text,n,h,a,RUN,a,RUN));row=await q.fetchone()
    if row:
     nid=row['content_node_id'];await q.execute('insert into library_literal_spans_v2(content_node_id,start_char,end_char,literal_text,normalized_text,hash) values(%s,0,%s,%s,%s,%s)',(nid,len(text),text,n,h));await q.execute("insert into library_semantic_units_v2(content_node_id,text,text_hash,chunk_order,chunker_name,language) values(%s,%s,%s,1,'page_first_v1','und')",(nid,text,h));textpages+=1
  await c.commit();print({'pages':len(d),'text_pages':textpages,'blank':blank,'run':RUN})
asyncio.run(main())
