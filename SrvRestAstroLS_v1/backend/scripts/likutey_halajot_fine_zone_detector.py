"""Deterministic, quote-verified fine-zone metadata; never corpus authority."""
from __future__ import annotations
import asyncio,hashlib,json,re
import psycopg
from psycopg.rows import dict_row
from globalVar import POSTGRES_DSN
RUN='likutey_halajot_fine_zone_detector_v1_20260714'; STRUCT='likutey_halajot_structural_detector_v1_20260714'
def zones(t,part):
 out=[]
 def add(kind,m,role='navigational',auth='navigational',marker=None,conf=.95):
  q=m.group(0);out.append((kind,role,auth,marker,q,m.start(),m.end(),conf))
 for m in re.finditer(r'HALAJ[ÁA]\s+\d+\s*:\s*\d+[A-Z]?',t,re.I):add('halakhah_header',m,'navigational','navigational','halakhah',.98)
 for m in re.finditer(r'Notas\s+y\s+Fuentes',t,re.I):add('notes_sources_block',m,'satellite','editorial_support','notes_sources',.95)
 if part=='glossary':
  for m in re.finditer(r'(?m)^([A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ -]{1,50})\s+-',t):add('glossary_entry',m,'navigational','navigational','glossary_term',.92)
 if part=='diagram':
  for m in re.finditer(r'(?i)(diagramas|gráficos|appendices)',t):add('diagram_caption',m,'visual','visual_support','diagram_label',.9)
 if re.search(r'[\u0590-\u05ff]',t):
  m=re.search(r'[\u0590-\u05ff](?:\s*[\u0590-\u05ff]){2,}',t)
  if m:add('hebrew_quote',m,'satellite','source_citation','hebrew',.86)
 return out
async def main():
 async with await psycopg.AsyncConnection.connect(POSTGRES_DSN,row_factory=dict_row) as c:
  async with c.cursor() as q:
   await q.execute("select s.document_id,s.pdf_page,s.page_anchor_id,s.literal_text,s.document_part from library_likutey_halajot_structural_v2 s order by s.pdf_page")
   rows=await q.fetchall();n=0
   for r in rows:
    for kind,role,auth,marker,quote,a,b,conf in zones(r['literal_text'] or '',r['document_part']):
     await q.execute("insert into library_likutey_halajot_fine_zones_v1(document_id,pdf_page,page_anchor_id,source_run_id,structural_detector_run_id,fine_zone_run_id,zone_type,zone_role,authority_level,marker_kind,marker_value,text_quote,char_start,char_end,quote_hash,confidence,evidence_origin,detection_origin,validation_status,review_status,raw_detection) values(%s,%s,%s,'likutey_halajot_page_first_v1',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'literal_regex','deterministic','validated','deterministic',%s::jsonb) on conflict do nothing",(r['document_id'],r['pdf_page'],r['page_anchor_id'],STRUCT,RUN,kind,role,auth,marker,marker,quote,a,b,hashlib.sha256(quote.encode()).hexdigest(),conf,json.dumps({'quote_in_page':quote in (r['literal_text'] or '')})));n+=q.rowcount
  await c.commit();print(json.dumps({'run':RUN,'inserted':n}))
asyncio.run(main())
