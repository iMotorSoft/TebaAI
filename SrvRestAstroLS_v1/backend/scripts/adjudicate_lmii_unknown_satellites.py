"""Send all LM II unknown textual blocks through LiteLLM, preserving fallback citations."""
from __future__ import annotations
import asyncio,json
import psycopg
from psycopg.rows import dict_row
from globalVar import POSTGRES_DSN
from modules.library.ai_note_continuity_analyzer import analyze,PROMPT_VERSION
async def main():
 out=[]
 async with await psycopg.AsyncConnection.connect(POSTGRES_DSN,row_factory=dict_row) as conn:
  async with conn.cursor() as cur:
   await cur.execute("""SELECT n.content_node_id,a.pdf_page_number,n.literal_text,u.canonical_ref FROM library_content_nodes_v2 n JOIN library_page_anchors_v2 a ON a.page_anchor_id=n.page_anchor_id JOIN library_content_units_v2 u ON u.content_unit_id=n.content_unit_id WHERE n.content_type='unknown' AND u.document_id=(SELECT id FROM library_documents WHERE document_code='likutey_moharan_ii_spanish_bri')""")
   rows=await cur.fetchall()
   for row in rows:
    decision=await analyze({'candidate_block_text':row['literal_text'],'candidate_physical_page':row['pdf_page_number'],'lesson_section':row['canonical_ref'],'layout_classification':'lower_unmarked_block'})
    linked=decision.decision=='continuation_of_previous_note' and decision.confidence>=.85
    ctype='numbered_footnote_continuation' if linked else 'citable_unlinked_note'
    status='linked_ai_verified' if linked else 'unlinked_citable'; review='ai_verified' if linked else 'fallback_unlinked'
    await cur.execute("UPDATE library_content_nodes_v2 SET content_type=%s,authority_level='secondary_explanatory',citable=true,link_status=%s,review_status=%s,ai_confidence=%s,ai_rationale=%s,ai_prompt_version=%s WHERE content_node_id=%s",(ctype,status,review,decision.confidence,decision.rationale,PROMPT_VERSION,row['content_node_id']))
    out.append({'node_id':str(row['content_node_id']),'page':row['pdf_page_number'],'decision':decision.decision,'confidence':decision.confidence,'rationale':decision.rationale,'model':decision.model_name})
  await conn.commit()
 print(json.dumps(out,ensure_ascii=False))
asyncio.run(main())
