"""Read-only PyMuPDF layout profile for the guarded LM XV KDP source."""
from __future__ import annotations
import argparse,json,re,statistics,sys
from collections import Counter
from pathlib import Path
import fitz
from preflight_likutey_moharan_xv_kdp import DEFAULT,EXPECTED_BASENAME,LH_SHA256
import hashlib
ROOT=Path(__file__).resolve().parents[3]; OUT=ROOT/'data/reports/breslov/2026-07-15-lm-xv-kdp-layout-profile-v1'
def guard(src:Path):
 if not src.is_file():raise RuntimeError('BLOCKED_SOURCE_FILE_NOT_FOUND')
 sha=hashlib.sha256(src.read_bytes()).hexdigest()
 if EXPECTED_BASENAME not in src.name or sha==LH_SHA256:raise RuntimeError('BLOCKED_SOURCE_IDENTITY_MISMATCH')
 d=fitz.open(src)
 if len(d)!=514:raise RuntimeError('BLOCKED_SOURCE_IDENTITY_MISMATCH_PAGE_COUNT')
 return d,sha
def role(text,bbox,w,h):
 he=len(re.findall(r'[\u0590-\u05ff]',text)); low=text.lower()
 if he>len(text)*.35:return 'hebrew_text',.85
 if bbox[1]<h*.12:return 'header',.7
 if bbox[1]>h*.86:return 'footer',.7
 if re.search(r'notas|fuentes|notes|sources',low):return 'note',.8
 if len(text)<90 and (text.isupper() or bbox[1]<h*.3):return 'title',.65
 return 'spanish_text' if re.search(r'[a-záéíóúñ]',low) else 'unknown',.55
def main():
 p=argparse.ArgumentParser();p.add_argument('--source-file',type=Path,default=DEFAULT);p.add_argument('--out',type=Path,default=OUT);a=p.parse_args();doc,sha=guard(a.source_file);a.out.mkdir(parents=True,exist_ok=True); pages=[];blocks=[]
 for n,page in enumerate(doc,1):
  text=page.get_text('text') or ''; data=page.get_text('dict'); raw=page.get_text('blocks',sort=True) or []; w,h=page.rect.width,page.rect.height; lines=sum(len(b.get('lines',[])) for b in data.get('blocks',[]) if b.get('type')==0);spans=sum(len(l.get('spans',[])) for b in data.get('blocks',[]) if b.get('type')==0 for l in b.get('lines',[])); xs=[b[0] for b in raw if b[4].strip()]; clusters=len({round(x/(w/4)) for x in xs}); cols=2 if clusters>=2 and len(raw)>=4 else 1; he=len(re.findall(r'[\u0590-\u05ff]',text)); latin=len(re.findall(r'[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]',text)); low=text.lower(); blank=not text.strip();
  flags={'likely_blank':blank,'likely_title_page':len(text.strip())<180 and n<12,'likely_front_matter':n<20 and not blank,'likely_index':bool(re.search(r'índice|contenido|contents',low)),'likely_main_text':n>=20 and n<490 and len(text)>500,'likely_notes_or_sources':bool(re.search(r'notas|fuentes|notes|sources',low)),'likely_appendix_or_back_matter':n>=490,'likely_diagram_or_visual':len(raw)<=2 and len(page.get_drawings())>5,'likely_header_footer_only':len(text.strip())<120 and not blank}
  pages.append({'pdf_page':n,'width':w,'height':h,'rotation':page.rotation,'text_length':len(text),'normalized_text_length':len(re.sub(r'\s+',' ',text)),'block_count':len(raw),'line_count':lines,'span_count':spans,'image_count':len(page.get_images(full=True)),'drawing_count':len(page.get_drawings()),'hebrew_char_count':he,'latin_char_count':latin,'digit_count':sum(c.isdigit() for c in text),'dominant_script':'hebrew' if he>latin else 'latin','has_text':not blank,'probable_columns':cols>1,'column_count_estimate':cols,'y_density_summary':'dense' if len(text)>2500 else 'sparse','x_density_summary':f'{clusters}_x_clusters','warnings':[] if not blank else ['blank_page'],**flags})
  for i,b in enumerate(raw):
   t=b[4].strip()
   if not t:continue
   r,c=role(t,b[:4],w,h);blocks.append({'pdf_page':n,'block_index':i,'bbox':[round(x,2) for x in b[:4]],'text_length':len(t),'line_count':t.count('\n')+1,'text_sample':t[:700],'script_mix':{'hebrew':len(re.findall(r'[\u0590-\u05ff]',t)),'latin':len(re.findall(r'[A-Za-z]',t))},'likely_role':r,'confidence':c,'warnings':[]})
 (a.out/'layout_profile_pages.json').write_text(json.dumps(pages,ensure_ascii=False,indent=2));(a.out/'layout_profile_blocks.jsonl').write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in blocks)+'\n')
 samples=sorted({1,2,3,4,5,119,310,504,514,max(pages,key=lambda x:x['column_count_estimate'])['pdf_page']});manifest=[{'pdf_page':x,'reason':'mandatory_or_max_column_score','metrics':pages[x-1]} for x in samples];(a.out/'layout_samples_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2));sample_blocks=[b for b in blocks if b['pdf_page'] in samples];(a.out/'layout_samples_blocks.jsonl').write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in sample_blocks)+'\n');(a.out/'layout_samples_reading_order.md').write_text('\n'.join(f"## PDF {x}\n\n"+'\n'.join(f"- {b['bbox']}: {b['likely_role']} — {b['text_sample'][:180]!r}" for b in sample_blocks if b['pdf_page']==x) for x in samples))
 order='COLUMN_AWARE_ORDER_REQUIRED' if sum(x['probable_columns'] for x in pages)>200 else 'BLOCK_ORDER_REQUIRED';(a.out/'reading_order_probe_report.json').write_text(json.dumps({'decision':order,'samples':list(samples),'raw_text_ok_for_page_first':True,'warnings':['store_bbox_and_reading_order_for_multicolumn_pages']}));(a.out/'reading_order_probe_report.md').write_text(f'# Reading order\n\nDecision: `{order}`. Raw page text is usable, but {sum(x["probable_columns"] for x in pages)} pages require stored block coordinates for later reconstruction.\n')
 candidates=[];parts=[]
 for x in pages:
  part='blank' if x['likely_blank'] else 'front_matter' if x['likely_front_matter'] else 'index' if x['likely_index'] else 'back_matter' if x['likely_appendix_or_back_matter'] else 'notes_sources' if x['likely_notes_or_sources'] else 'main_text' if x['likely_main_text'] else 'unknown';parts.append({'pdf_page':x['pdf_page'],'document_part_candidate':part,'evidence_quote':'layout/text local','evidence_block_index':None,'confidence':.85 if part!='unknown' else .4,'warnings':[]})
 for b in blocks:
  if b['likely_role'] in ('title','header','note','hebrew_text'):candidates.append({'pdf_page':b['pdf_page'],'candidate_type':b['likely_role'],'surface_form':b['text_sample'][:160],'quote':b['text_sample'],'block_index':b['block_index'],'bbox':b['bbox'],'confidence':b['confidence'],'detection_rule':'local_block_role','warnings':['candidate_only']})
 (a.out/'document_part_candidates.json').write_text(json.dumps(parts,ensure_ascii=False,indent=2));(a.out/'document_part_classifier_report.md').write_text(f'# Part candidates\n\nMain text: {sum(x["document_part_candidate"]=="main_text" for x in parts)}; unknown: {sum(x["document_part_candidate"]=="unknown" for x in parts)}.\n');(a.out/'structural_candidates.json').write_text(json.dumps(candidates,ensure_ascii=False,indent=2));(a.out/'structural_candidates_report.md').write_text(f'# Structural candidates\n\n{len(candidates)} local block candidates; none promoted to corpus structure.\n')
 strategy='PAGE_FIRST_COLUMN_AWARE_REQUIRED';(a.out/'layout_ingestion_strategy_recommendation.md').write_text(f'# Strategy\n\n`{strategy}`: ingest page-first only later, preserve raw/normalized page text, blocks, bbox and reading order. Keep blanks, front matter and back matter as page states. Decode embedded Hebrew as needed; OCR and IA are not required.\n')
 summary={'status':'LM_XV_LAYOUT_PROFILE_READY_WITH_LIMITATIONS','source_file_path':str(a.source_file),'source_basename':a.source_file.name,'sha256':sha,'page_count':514,'text_pages':sum(x['has_text'] for x in pages),'blank_pages':[x['pdf_page'] for x in pages if x['likely_blank']],'column_pages':sum(x['probable_columns'] for x in pages),'hebrew_pages':sum(x['hebrew_char_count']>0 for x in pages),'structural_candidates':len(candidates),'reading_order_decision':order,'strategy':strategy,'ocr_used':False,'ai_used':False,'db_writes':False};(a.out/'source_identity_report.json').write_text(json.dumps({k:summary[k] for k in ('source_file_path','source_basename','sha256','page_count')},ensure_ascii=False,indent=2));(a.out/'layout_profile_summary.md').write_text('# LM XV KDP layout profile\n\n'+json.dumps(summary,ensure_ascii=False,indent=2));(a.out/'no_contamination_report.json').write_text(json.dumps({'db_writes':False,'embeddings':False,'milvus_writes':False,'relations':False,'ocr':False,'ai':False,'reason':'scripts use only local PyMuPDF and report files'},indent=2));print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
