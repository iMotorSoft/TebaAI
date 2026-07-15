#!/usr/bin/env python3
"""Read-only local structural profile; embedded blocks remain authoritative."""
import asyncio,json,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import psycopg
from globalVar import POSTGRES_DSN
ROOT=Path(__file__).resolve().parents[3];R=ROOT/'data/reports/breslov/2026-07-15-lm-xv-kdp-structural-detector-v1';RUN='likutey_moharan_xv_kdp_page_first_column_aware_v1'
def role(t,b):
 s=t.strip(); y=b['bbox'][1]
 if re.fullmatch(r'\d+',s):return 'page_number'
 if y<60:return 'header'
 if y>700:return 'footer'
 if len(re.findall(r'[\u0590-\u05ff]',s))>len(s)*.35:return 'hebrew_text'
 if re.search(r'notas?(?:\s+y\s+fuentes)?|fuentes?',s,re.I):return 'note_candidate'
 if len(s)<100 and re.search(r'lecci[oó]n|tor[aá]|introducci[oó]n|[A-ZÁÉÍÓÚÑ]{5,}',s):return 'title'
 return 'main_text'
async def main():
 R.mkdir(parents=True,exist_ok=True)
 async with await psycopg.AsyncConnection.connect(POSTGRES_DSN,row_factory=psycopg.rows.dict_row) as c:
  async with c.cursor() as q:
   await q.execute("select p.pdf_page,p.page_status,p.block_count,p.reading_order_method,p.has_hebrew,p.has_latin,p.raw_text,b.id block_id,b.block_index_original,b.bbox,b.text from library_lm_xv_kdp_pages_v1 p left join library_lm_xv_kdp_page_blocks_v1 b on b.document_id=p.document_id and b.pdf_page=p.pdf_page and b.source_run_id=p.source_run_id where p.source_run_id=%s order by p.pdf_page,b.block_index_original",(RUN,)); rows=await q.fetchall()
 pages={};blocks=[]
 for x in rows:
  p=pages.setdefault(x['pdf_page'],{'pdf_page':x['pdf_page'],'page_status':x['page_status'],'block_count':x['block_count'],'reading_order_method':x['reading_order_method'],'has_hebrew':x['has_hebrew'],'has_latin':x['has_latin'],'blocks':[]})
  if x['block_id']:
   b={'block_id':str(x['block_id']),'block_index':x['block_index_original'],'bbox':x['bbox'],'text':x['text'],'candidate_role':role(x['text'],x)};p['blocks'].append(b);blocks.append({'pdf_page':x['pdf_page'],**b})
 out=[]
 for p in pages.values():
  text=' '.join(b['text'] for b in p['blocks']); first=p['blocks'][0] if p['blocks'] else None;blank=p['page_status']=='blank';quote='' if blank else (first['text'][:300] if first else '')
  out.append({k:p[k] for k in ('pdf_page','page_status','block_count','reading_order_method','has_hebrew','has_latin')}|{'dominant_script':'hebrew' if p['has_hebrew'] and not p['has_latin'] else 'mixed' if p['has_hebrew'] else 'latin','likely_blank':blank,'likely_front_matter':p['pdf_page']<20 and not blank,'likely_index':bool(re.search(r'índice|contenido',text,re.I)),'likely_main_text':not blank and p['pdf_page']>=20 and p['pdf_page']<500,'likely_back_matter':p['pdf_page']>=500 and not blank,'likely_notes_sources':bool(re.search(r'notas?(?:\s+y\s+fuentes)?',text,re.I)),'likely_title_page':bool(first and first['candidate_role']=='title'),'likely_section_title':bool(any(b['candidate_role']=='title' for b in p['blocks'])),'likely_unknown_textual':not blank,'evidence_quotes':[] if blank else [quote],'evidence_block_ids':[] if not first else [first['block_id']],'confidence':.95 if blank else .75,'warnings':[]})
 (R/'structural_profile_pages.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));(R/'structural_profile_blocks.jsonl').write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in blocks)+'\n');(R/'structural_profile_summary.md').write_text(f'# Structural profile\n\nPages: {len(out)}. Blocks: {len(blocks)}. OCR: not used.\n');print(json.dumps({'pages':len(out),'blocks':len(blocks)}))
asyncio.run(main())
