"""Ingest a verified Hebrew/Spanish LM II page-pair pilot into canonical V3."""
from __future__ import annotations
import argparse, asyncio, hashlib, json
from pathlib import Path
import fitz, psycopg
from psycopg.rows import dict_row
from globalVar import POSTGRES_DSN
from modules.library.investigative_model import normalize_literal, stable_hash
from modules.library.likutey_moharan_ii_layout import PROFILE_NAME, classify_page, lesson_ref

SOURCE = Path('/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY MOHARAN II Interior.pdf')
DOC_CODE = 'likutey_moharan_ii_spanish_bri'

async def ingest(apply: bool, pages: list[int]) -> dict[str, object]:
    doc = fitz.open(SOURCE)
    async with await psycopg.AsyncConnection.connect(POSTGRES_DSN, row_factory=dict_row) as conn:
      async with conn.cursor() as cur:
        await cur.execute("SELECT id, collection_id, knowledge_scope_id, organization_id, workspace_id, project_id FROM library_documents WHERE document_code=%s", (DOC_CODE,))
        row = await cur.fetchone()
        if not row:
            await cur.execute("SELECT collection_id,knowledge_scope_id,organization_id,workspace_id,project_id FROM library_documents WHERE title='KITZUR' LIMIT 1")
            template = await cur.fetchone()
            if not template: raise RuntimeError('missing library document context')
            if not apply: return {'dry_run': True, 'would_create_document': True, 'pages': pages}
            digest = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
            await cur.execute("""INSERT INTO library_documents (id,collection_id,title,language,source_type,source_path,source_filename,source_mime_type,source_size_bytes,source_sha256,status,metadata,bibliographic_metadata,organization_id,workspace_id,project_id,knowledge_scope_id,document_code,canonical_text_role)
              VALUES (gen_random_uuid(),%s,'Likutey Moharán II — edición española BRI','es','pdf',%s,%s,'application/pdf',%s,%s,'test_candidate',jsonb_build_object('layout_profile',%s::text), '{}',%s,%s,%s,%s,%s,'candidate') RETURNING id,collection_id,knowledge_scope_id,organization_id,workspace_id,project_id""",
              (template['collection_id'],str(SOURCE),SOURCE.name,SOURCE.stat().st_size,digest,PROFILE_NAME,template['organization_id'],template['workspace_id'],template['project_id'],template['knowledge_scope_id'],DOC_CODE))
            row = await cur.fetchone()
        document_id=row['id']
        result={'document_id':str(document_id),'profile':PROFILE_NAME,'pages':pages,'nodes':0,'anchors':0,'spans':0,'semantic_units':0,'relations':0,'dry_run':not apply}
        if not apply: return result
        await cur.execute("""INSERT INTO library_content_units_v2 (document_id,unit_type,canonical_ref,title,order_index,language_original,is_breslov_primary_source,is_direct_rebbe_nachman,source_run_id,metadata_json)
          VALUES (%s,'work','LMII','Likutey Moharán II',0,'he',true,true,NULL,jsonb_build_object('profile',%s::text))
          ON CONFLICT (document_id,canonical_ref) WHERE canonical_ref IS NOT NULL DO UPDATE SET title=EXCLUDED.title RETURNING content_unit_id""",(document_id,PROFILE_NAME))
        work=(await cur.fetchone())['content_unit_id']; section_units={}; primaries={}
        for pdf_page in pages:
          page=doc[pdf_page-1]; blocks=[(b[0],b[1],b[2],b[3],b[4]) for b in page.get_text('blocks')]; pieces=classify_page(blocks,pdf_page)
          page_text=page.get_text('text'); ref=lesson_ref(page_text)
          # Structural detection is enrichment only.  Never contaminate an
          # unknown page by assigning the historic LMII 7:1 fallback.
          if ref is None:
            raise RuntimeError(f'UNKNOWN_STRUCTURAL_SCOPE: PDF page {pdf_page}; use the page-first ingester')
          key=f'LMII {ref[0]}:{ref[1]}'
          if key not in section_units:
            await cur.execute("""INSERT INTO library_content_units_v2 (parent_content_unit_id,document_id,unit_type,canonical_ref,title,order_index,language_original,is_breslov_primary_source,is_direct_rebbe_nachman,metadata_json)
              VALUES (%s,%s,'lesson',%s,%s,%s,'he',true,true,jsonb_build_object('profile',%s::text)) ON CONFLICT (document_id,canonical_ref) WHERE canonical_ref IS NOT NULL DO UPDATE SET title=EXCLUDED.title RETURNING content_unit_id""",(work,document_id,f'LMII {ref[0]}',f'Lección {ref[0]}',ref[0],PROFILE_NAME)); lesson=(await cur.fetchone())['content_unit_id']
            await cur.execute("""INSERT INTO library_content_units_v2 (parent_content_unit_id,document_id,unit_type,canonical_ref,title,order_index,language_original,is_breslov_primary_source,is_direct_rebbe_nachman,metadata_json)
              VALUES (%s,%s,'lesson_section',%s,%s,%s,'he',true,true,jsonb_build_object('profile',%s::text)) ON CONFLICT (document_id,canonical_ref) WHERE canonical_ref IS NOT NULL DO UPDATE SET title=EXCLUDED.title RETURNING content_unit_id""",(lesson,document_id,key,f'Lección {ref[0]}, sección {ref[1]}',ref[1],PROFILE_NAME)); section_units[key]=(await cur.fetchone())['content_unit_id']
          await cur.execute("""INSERT INTO library_page_anchors_v2 (source_file_id,document_id,edition_id,pdf_page_number,printed_page_number,page_label,confidence,metadata_json) VALUES (%s,%s,%s,%s,%s,%s,.99,jsonb_build_object('profile',%s::text)) ON CONFLICT (document_id,pdf_page_number,edition_id) DO UPDATE SET printed_page_number=EXCLUDED.printed_page_number RETURNING page_anchor_id""",(document_id,document_id,PROFILE_NAME,pdf_page,pdf_page-10,str(pdf_page-10),PROFILE_NAME)); anchor=(await cur.fetchone())['page_anchor_id']; result['anchors']+=1
          page_primary=None
          for order,piece in enumerate(pieces,1):
            if piece.kind=='page_header': role,authority,relation,language,citable='satellite','navigational','navigates','es',False
            elif piece.kind=='hebrew_main_text': role,authority,relation,language,citable='primary','primary_original','is_core_text','he',True
            elif piece.kind=='spanish_translation': role,authority,relation,language,citable='primary','primary_parallel','translates','es',True
            elif piece.kind=='numbered_footnote': role,authority,relation,language,citable='satellite','secondary_explanatory','explains','es',True
            else: role,authority,relation,language,citable='satellite','unknown','unknown','und',False
            await cur.execute("""INSERT INTO library_content_nodes_v2 (content_unit_id,node_role,content_type,relation_to_primary,authority_level,language,script,literal_text,normalized_text,literal_hash,page_anchor_id,node_order,citable,metadata_json)
              SELECT %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,jsonb_build_object('profile',%s::text,'pdf_page',%s)
              WHERE NOT EXISTS (SELECT 1 FROM library_content_nodes_v2 WHERE page_anchor_id=%s AND node_order=%s AND metadata_json->>'profile'=%s) RETURNING content_node_id""",(section_units[key],role,piece.kind,relation,authority,language,'hebrew' if language=='he' else 'latin',piece.text,normalize_literal(piece.text),stable_hash(piece.text),anchor,order,citable,PROFILE_NAME,pdf_page,anchor,order,PROFILE_NAME))
            node=await cur.fetchone()
            if not node: continue
            nid=node['content_node_id']; result['nodes']+=1
            if citable:
              await cur.execute("INSERT INTO library_literal_spans_v2 (content_node_id,start_char,end_char,literal_text,normalized_text,hash,metadata_json) VALUES (%s,0,%s,%s,%s,%s,jsonb_build_object('profile',%s::text)) RETURNING literal_span_id",(nid,len(piece.text),piece.text,normalize_literal(piece.text),stable_hash(piece.text),PROFILE_NAME)); span=(await cur.fetchone())['literal_span_id']; result['spans']+=1
              await cur.execute("INSERT INTO library_semantic_units_v2 (content_node_id,literal_span_id,text,text_hash,chunk_order,chunker_name,chunker_config_json,language,metadata_json) VALUES (%s,%s,%s,%s,1,'layout_node_v1',jsonb_build_object('crosses_node',false),%s,jsonb_build_object('profile',%s::text))",(nid,span,normalize_literal(piece.text),stable_hash(piece.text),language,PROFILE_NAME)); result['semantic_units']+=1
            if role=='primary': page_primary=nid; primaries[pdf_page]=nid
            elif page_primary and piece.kind == 'numbered_footnote':
              await cur.execute("INSERT INTO library_content_relations_v2 (source_content_node_id,target_content_node_id,relation_type,evidence_type,confidence,explanation,metadata_json) VALUES (%s,%s,'explains','editorial_explanation',%s,'same page, explicit footnote geometry',jsonb_build_object('profile',%s::text))",(nid,page_primary,piece.confidence,PROFILE_NAME)); result['relations']+=1
        for even in pages:
          if even % 2 == 0 and even in primaries and even+1 in primaries:
            await cur.execute("INSERT INTO library_content_relations_v2 (source_content_node_id,target_content_node_id,relation_type,evidence_type,confidence,explanation,metadata_json) VALUES (%s,%s,'parallel_translation','translation_alignment',.90,'alternating Hebrew/Spanish pages with same lesson-section header',jsonb_build_object('profile',%s::text))",(primaries[even],primaries[even+1],PROFILE_NAME)); result['relations']+=1
        await conn.commit(); return result

def main():
 p=argparse.ArgumentParser(); p.add_argument('--apply',action='store_true'); p.add_argument('--pages',default='12-43'); a=p.parse_args(); raw=a.pages; pages=list(range(*[int(v) for v in raw.split('-')])) if '-' in raw else [int(v) for v in raw.split(',')]; pages = pages + ([int(raw.split('-')[1])] if '-' in raw else []); print(json.dumps(asyncio.run(ingest(a.apply,pages)),ensure_ascii=False,indent=2))
if __name__=='__main__': main()
