#!/usr/bin/env python3
import asyncio,json,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));import psycopg
from globalVar import POSTGRES_DSN
ROOT=Path(__file__).resolve().parents[3];R=ROOT/'data/reports/breslov/2026-07-15-lm-xv-kdp-fine-zone-detector-v1';SOURCE='likutey_moharan_xv_kdp_page_first_column_aware_v1'
def typ(t,b):
 s=t.strip();h=len(re.findall(r'[\u0590-\u05ff]',s));lat=len(re.findall(r'[A-Za-zÁÉÍÓÚáéíóúÑñ]',s));y=b['bbox'][1]
 if re.fullmatch(r'\d+',s):return 'page_number'
 if y<55:return 'header'
 if y>735:return 'footer'
 if re.search(r'notas?|fuentes?|referencia|véase|\bver\b|\bcf\.',s,re.I):return 'note_or_source_candidate'
 if len(s)<120 and (re.search(r'lecci[oó]n|tor[aá]|introducci[oó]n|likutey mohar',s,re.I) or re.search(r'[A-ZÁÉÍÓÚÑ]{5,}',s)):return 'title'
 if h and lat:return 'mixed_hebrew_spanish'
 if h:return 'main_text_hebrew'
 return 'main_text_spanish' if lat else 'unknown_textual_zone'
async def main():
 R.mkdir(parents=True,exist_ok=True)
 async with await psycopg.AsyncConnection.connect(POSTGRES_DSN,row_factory=psycopg.rows.dict_row) as c:
  async with c.cursor() as q:
   await q.execute("select p.pdf_page,p.page_status,s.document_part,s.structural_status,p.reading_order_method,p.block_count,p.has_hebrew,p.has_latin,b.id block_id,b.block_index_original,b.bbox,b.text from library_lm_xv_kdp_pages_v1 p join library_lm_xv_kdp_structural_classifications_v1 s on s.document_id=p.document_id and s.pdf_page=p.pdf_page and s.source_run_id=p.source_run_id left join library_lm_xv_kdp_page_blocks_v1 b on b.document_id=p.document_id and b.pdf_page=p.pdf_page and b.source_run_id=p.source_run_id where p.source_run_id=%s order by p.pdf_page,b.block_index_original",(SOURCE,));rows=await q.fetchall()
 pages={};bl=[]
 for x in rows:
  p=pages.setdefault(x['pdf_page'],{k:x[k] for k in ('pdf_page','page_status','document_part','structural_status','reading_order_method','block_count','has_hebrew','has_latin')}|{'zones':[]})
  if x['block_id']:
   z={'pdf_page':x['pdf_page'],'block_id':str(x['block_id']),'block_index':x['block_index_original'],'bbox':x['bbox'],'text_quote':x['text'],'candidate_zone_type':typ(x['text'],x)};p['zones'].append(z);bl.append(z)
 out=[]
 for p in pages.values():
  ts=[z['candidate_zone_type'] for z in p['zones']];first=p['zones'][0] if p['zones'] else None;out.append({k:p[k] for k in p if k!='zones'}|{'dominant_script':'mixed' if p['has_hebrew'] and p['has_latin'] else 'hebrew' if p['has_hebrew'] else 'latin','zone_candidates_count':len(ts),'likely_title_zone':'title' in ts,'likely_header_zone':'header' in ts,'likely_footer_zone':'footer' in ts,'likely_main_text_zone':any(t.startswith('main_text') for t in ts),'likely_hebrew_zone':'main_text_hebrew' in ts,'likely_mixed_hebrew_spanish_zone':'mixed_hebrew_spanish' in ts,'likely_note_or_source_zone':'note_or_source_candidate' in ts,'likely_unknown_textual_zone':'unknown_textual_zone' in ts,'evidence_quotes':[] if not first else [first['text_quote'][:300]],'evidence_block_ids':[] if not first else [first['block_id']],'confidence':.8,'warnings':[]})
 (R/'fine_zone_profile_pages.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));(R/'fine_zone_profile_blocks.jsonl').write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in bl)+'\n');(R/'fine_zone_profile_summary.md').write_text(f'# Fine zone profile\n\nPages: {len(out)}; blocks evaluated: {len(bl)}; OCR/IA: no.\n');print(json.dumps({'pages':len(out),'blocks':len(bl)}))
asyncio.run(main())
