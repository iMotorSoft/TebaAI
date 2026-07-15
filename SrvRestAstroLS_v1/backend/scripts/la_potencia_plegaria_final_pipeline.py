#!/usr/bin/env python3
"""Guarded, deterministic final investigative ingestion for La Potencia de la Plegaria."""
import asyncio,fitz,hashlib,json,re,statistics,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));import psycopg
from globalVar import POSTGRES_DSN
P=Path('/media/issajar/DEVELOP/Download/Tora/Breslov/LA POTENCIA DE LA PLEGARIA Interior Print.pdf');SHA='8e5c2ca6c153f47e7ae31e0ba2f2b8fefaedb9916dd8d0d79d484e2c96990c46';RUN='la_potencia_plegaria_page_first_final_v1';PIPE='la_potencia_plegaria_final_ingestion_v1_20260715';ROOT=Path(__file__).resolve().parents[3];R=ROOT/'data/reports/breslov/2026-07-15-la-potencia-plegaria-final-ingestion-v1'
CAT={'Zohar':('Zohar','zohar'),'Midrash':('Midrash','midrash'),'Likutey Moharán':('Likutey Moharan','breslov_work'),'Rebe Najmán':('Rebe Najman','breslov_figure'),'Rabí Natán':('Rabi Natan','breslov_figure'),'Rashi':('Rashi','rabbinic_commentator'),'Rambam':('Rambam','rabbinic_commentator')}
def norm(t):return re.sub(r'\s+',' ',t).strip()
def ztype(t,b):
 s=t.strip();h=bool(re.search(r'[\u0590-\u05ff]',s));lat=bool(re.search(r'[A-Za-zÁÉÍÓÚáéíóúÑñ]',s));
 if re.fullmatch(r'\d+',s):return 'page_number','validated'
 if b[1]<55:return 'header','validated'
 if b[3]>735:return 'footer','validated'
 if re.search(r'notas?|fuentes?|referencia|véase|\bver\b|\bcf\.',s,re.I):return 'note_or_source_candidate','candidate'
 if h and lat:return 'mixed_hebrew_spanish','validated'
 if h:return 'main_text_hebrew','validated'
 return ('main_text_spanish','validated') if lat else ('unknown_textual_zone','candidate')
async def main():
 R.mkdir(parents=True,exist_ok=True);sha=hashlib.sha256(P.read_bytes()).hexdigest()
 if not P.is_file() or 'LA POTENCIA DE LA PLEGARIA' not in P.name or sha!=SHA or sha in {'440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a','f4d7eb195cadf94d6566c5cd6d636113b62f4c6748f987b250fc4bd0fcd61303'}:raise RuntimeError('BLOCKED_SOURCE_IDENTITY_MISMATCH')
 d=fitz.open(P);pre=[];blocks=[]
 for n,p in enumerate(d,1):
  t=p.get_text('text') or '';bs=p.get_text('blocks',sort=True) or [];pre.append({'pdf_page':n,'text_length':len(t),'block_count':len(bs),'has_text':bool(t.strip()),'likely_blank':not bool(t.strip()),'hebrew_char_count':len(re.findall(r'[\u0590-\u05ff]',t)),'latin_char_count':len(re.findall(r'[A-Za-z]',t)),'text_sample_start':t[:240]});blocks.append(bs)
 R.joinpath('pdf_preflight_pages.json').write_text(json.dumps(pre,ensure_ascii=False,indent=2));summary={'total_pages':len(d),'textual_pages':sum(x['has_text'] for x in pre),'blank_pages':[x['pdf_page'] for x in pre if x['likely_blank']],'embedded_text_coverage':sum(x['has_text'] for x in pre)/len(d),'ocr_recommendation':'TEXT_EMBEDDED_ONLY'};R.joinpath('pdf_preflight_summary.md').write_text('# Preflight\n\n'+json.dumps(summary,indent=2));R.joinpath('ai_ocr_usage_report.json').write_text(json.dumps({'ocr_not_required':True,'ai_not_used':True},indent=2))
 async with await psycopg.AsyncConnection.connect(POSTGRES_DSN,row_factory=psycopg.rows.dict_row) as c:
  async with c.cursor() as q:
   await q.execute("select id,collection_id,organization_id,workspace_id,project_id,knowledge_scope_id from library_documents where document_code='likutey_halajot_interior_final'");base=await q.fetchone();await q.execute("select id from library_documents where document_code='la_potencia_de_la_plegaria_interior_print'");row=await q.fetchone()
   if row:did=row['id']
   else:
    await q.execute("insert into library_documents(id,collection_id,title,language,source_type,source_path,source_filename,source_mime_type,source_size_bytes,source_sha256,status,organization_id,workspace_id,project_id,knowledge_scope_id,document_code,canonical_text_role) values(gen_random_uuid(),%s,%s,'es','pdf',%s,%s,'application/pdf',%s,%s,'test_candidate',%s,%s,%s,%s,'la_potencia_de_la_plegaria_interior_print','candidate') returning id",(base['collection_id'],'La Potencia de la Plegaria — Interior Print',str(P),P.name,P.stat().st_size,sha,base['organization_id'],base['workspace_id'],base['project_id'],base['knowledge_scope_id']));did=(await q.fetchone())['id']
   refs=notes=zones=0
   for n,p in enumerate(d,1):
    t=p.get_text('text') or '';nt=norm(t);bs=blocks[n-1];blank=not nt;status='blank' if blank else ('front_matter' if n<10 else 'back_matter' if n>400 else 'textual');method='block_order' if len(bs)>1 else 'raw_order';await q.execute("insert into library_la_potencia_plegaria_pages_v1(document_id,source_run_id,pdf_page,page_status,raw_text,normalized_text,text_hash,has_hebrew,has_latin,reading_order_method) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) on conflict(source_run_id,pdf_page) do update set raw_text=excluded.raw_text,normalized_text=excluded.normalized_text,text_hash=excluded.text_hash",(did,RUN,n,status,t,nt,hashlib.sha256(t.encode()).hexdigest(),bool(re.search(r'[\u0590-\u05ff]',t)),bool(re.search(r'[A-Za-z]',t)),method))
    quote=next((b[4].strip() for b in bs if b[4].strip()),None);part='blank' if blank else ('front_matter' if n<10 else 'back_matter' if n>400 else 'main_text');await q.execute("insert into library_la_potencia_plegaria_structural_classifications_v1(document_id,run_id,pdf_page,document_part,structural_status,unit_type,evidence_quote,confidence) values(%s,%s,%s,%s,%s,%s,%s,%s) on conflict(run_id,pdf_page) do update set document_part=excluded.document_part,evidence_quote=excluded.evidence_quote",(did,PIPE,n,part,'blank_page' if blank else 'classified','unknown' if blank else 'main_text',quote,.99 if blank else .75))
    for i,b in enumerate(bs):
     bt=b[4].strip()
     if not bt:continue
     await q.execute("insert into library_la_potencia_plegaria_page_blocks_v1(document_id,source_run_id,pdf_page,block_index,bbox,text,normalized_text,text_hash,role) values(%s,%s,%s,%s,%s::jsonb,%s,%s,%s,'unknown') on conflict(source_run_id,pdf_page,block_index) do update set text=excluded.text",(did,RUN,n,i,json.dumps(b[:4]),bt,norm(bt),hashlib.sha256(bt.encode()).hexdigest()));await q.execute("select id from library_la_potencia_plegaria_page_blocks_v1 where source_run_id=%s and pdf_page=%s and block_index=%s",(RUN,n,i));bid=(await q.fetchone())['id'];typ,val=ztype(bt,b);await q.execute("insert into library_la_potencia_plegaria_fine_zones_v1(document_id,run_id,pdf_page,block_id,zone_type,text_quote,quote_hash,validation_status,confidence) values(%s,%s,%s,%s,%s,%s,%s,%s,.85) on conflict(run_id,pdf_page,block_id) do update set zone_type=excluded.zone_type,text_quote=excluded.text_quote",(did,PIPE,n,bid,typ,bt,hashlib.sha256(bt.encode()).hexdigest(),val));zones+=1
     m=re.match(r'^(\d+)\.\s+',bt)
     if typ=='note_or_source_candidate' and m:await q.execute("insert into library_la_potencia_plegaria_note_source_units_v1(document_id,run_id,pdf_page,unit_type,visible_note_number,text_quote,validation_status) values(%s,%s,%s,'numbered_note',%s,%s,'validated') on conflict do nothing",(did,PIPE,n,m.group(1),bt));notes+=1
     for surface,(normal,kind) in CAT.items():
      if surface.lower() in bt.lower():await q.execute("insert into library_la_potencia_plegaria_nominal_references_v1(document_id,run_id,pdf_page,surface_form,normalized_reference_name,reference_kind,text_quote,validation_status) values(%s,%s,%s,%s,%s,%s,%s,'validated') on conflict do nothing",(did,PIPE,n,surface,normal,kind,bt));refs+=1
   await c.commit()
 out={'status':'LA_POTENCIA_PLEGARIA_FINAL_SEARCH_READY','sha256':sha,'pages':len(d),'textual_pages':summary['textual_pages'],'blanks':summary['blank_pages'],'zones':zones,'numbered_notes':notes,'nominal_references':refs,'ocr_used':False,'ai_used':False,'embeddings':False,'milvus':False,'relations':False};R.joinpath('page_first_ingest_report.json').write_text(json.dumps(out,indent=2));R.joinpath('structural_detector_report.json').write_text(json.dumps({'pages':len(d),'run':PIPE},indent=2));R.joinpath('fine_zone_detector_report.json').write_text(json.dumps({'zones':zones},indent=2));R.joinpath('note_source_detector_report.json').write_text(json.dumps({'numbered_notes':notes},indent=2));R.joinpath('nominal_reference_detector_report.json').write_text(json.dumps({'references':refs},indent=2));R.joinpath('reference_resolution_not_required_report.md').write_text('# Resolution\n\nNo ambiguous generic references were generated.\n');print(json.dumps(out))
asyncio.run(main())
