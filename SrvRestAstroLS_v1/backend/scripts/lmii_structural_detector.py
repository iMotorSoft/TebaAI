"""Conservative structural layer: page-first remains authoritative."""
from __future__ import annotations
import asyncio,json
import psycopg
from psycopg.rows import dict_row
from globalVar import POSTGRES_DSN
RUN='lmii_structural_detector_v2_20260714'; EDITION='lmii_page_first_v1'
def classify(page, has_text):
 if not has_text:return ('blank','blank_page',None,1.0,'blank_page_detection','promote','deterministic')
 if 12<=page<=43:return ('lesson','classified',7,.90,'continuity_from_verified_range','promote','human_validated_pattern')
 if 44<=page<=95:return ('lesson','classified',8,.90,'continuity_from_verified_range','promote','human_validated_pattern')
 # Seed ranges are deliberately candidates only, never promotions.
 candidate=next((lesson for lesson,a,b in [(9,96,129),(10,130,177),(11,178,221),(12,222,265),(13,266,313),(14,314,363),(15,364,393),(16,394,402)] if a<=page<=b),None)
 return ('unknown','unclassified',None,.60 if candidate else 0.0,'known_range_seed' if candidate else 'fallback_none','keep_unclassified','needs_review')
async def main():
 async with await psycopg.AsyncConnection.connect(POSTGRES_DSN,row_factory=dict_row) as c:
  async with c.cursor() as q:
   await q.execute('delete from library_page_structural_classifications_v2 where source_run_id like %s',('lmii_structural_detector_v1%',)); deleted=q.rowcount
   await q.execute("""select a.page_anchor_id,a.pdf_page_number,a.printed_page_number,n.content_node_id from library_page_anchors_v2 a left join library_content_nodes_v2 n on n.page_anchor_id=a.page_anchor_id and n.metadata_json->>'source_run_id'='lmii_full_page_first_v1' where a.edition_id=%s order by a.pdf_page_number""",(EDITION,));rows=await q.fetchall();out=[]
   for r in rows:
    part,status,lesson,conf,origin,action,review=classify(r['pdf_page_number'],bool(r['content_node_id']))
    await q.execute("insert into library_page_structural_classifications_v2(source_run_id,page_anchor_id,content_node_id,pdf_page,printed_page,document_part,structural_status,lesson_number,confidence,evidence_origin,evidence_text,detector_version,classification_action,review_status,rationale) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,'v2',%s,%s,%s)",(RUN,r['page_anchor_id'],r['content_node_id'],r['pdf_page_number'],r['printed_page_number'],part,status,lesson,conf,json.dumps([origin]),json.dumps([f'PDF page {r["pdf_page_number"]}']),action,review,'verified LMII 7/8 range or conservative candidate'))
    out.append({'pdf_page':r['pdf_page_number'],'action':action,'lesson':lesson,'confidence':conf})
  await c.commit();print(json.dumps({'deleted_permissive':deleted,'evaluated':len(out),'promoted':sum(x['action']=='promote' for x in out),'unclassified':sum(x['action']!='promote' for x in out)}))
asyncio.run(main())
