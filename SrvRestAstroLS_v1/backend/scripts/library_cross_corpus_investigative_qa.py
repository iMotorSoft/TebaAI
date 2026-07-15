"""Local literal-only batch across Kitzur chunks, LM II pages, and LH final search."""
from __future__ import annotations
import argparse,asyncio,json,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import psycopg
from psycopg.rows import dict_row
from globalVar import POSTGRES_DSN
ROOT=Path(__file__).resolve().parents[3]; DEFAULT=ROOT/'data/reports/breslov/2026-07-15-cross-corpus-investigative-qa-v1'
def snippet(text,term):
 i=text.lower().find(term.lower());return text[max(0,i-180):i+420].strip() if i>=0 else text[:500].strip()
def page_marker(text):
 m=list(re.finditer(r'## Page (\d+)',text));return int(m[-1].group(1)) if m else None
async def hits(cur,term):
 out=[]
 await cur.execute("""select c.content,d.title from library_document_chunks c join library_documents d on d.id=c.document_id where d.title='KITZUR' and c.content ilike %s limit 3""",(f'%{term}%',))
 for r in await cur.fetchall():
  page=page_marker(r['content']);out.append({'work':'Kitzur','document_title':r['title'],'pdf_page':page,'quote':snippet(r['content'],term),'evidence_type_cross_corpus':'literal_same_document_page','source':'library_document_chunks','search_record_type':'chunk','evidence_level':'literal_page','confidence':.9,'warning':None if page is not None else 'kitzur_chunk_has_no_page_marker'})
 await cur.execute("select pdf_page_number,printed_page_number,literal_text,lesson_number from library_lmii_search_ready_v2 where literal_text ilike %s limit 3",(f'%{term}%',))
 for r in await cur.fetchall():out.append({'work':'Likutey Moharán II','document_title':'Likutey Moharán II','pdf_page':r['pdf_page_number'],'printed_page':r['printed_page_number'],'section':r['lesson_number'],'quote':snippet(r['literal_text'],term),'evidence_type_cross_corpus':'same_topic_same_work','source':'library_lmii_search_ready_v2','search_record_type':'page_literal','evidence_level':'literal_page','confidence':.85})
 await cur.execute("""select pdf_page,printed_page,halakhah_header_hint,visible_note_number,coalesce(resolution_quote,nominal_reference_quote,note_source_quote,fine_zone_quote,page_text) quote,search_record_type,evidence_level,surface_form,resolution_decision from library_likutey_halajot_investigative_search_v1 where coalesce(resolution_quote,nominal_reference_quote,note_source_quote,fine_zone_quote,page_text,'') ilike %s limit 5""",(f'%{term}%',))
 for r in await cur.fetchall():
  typ='note_source_context' if r['search_record_type'] in ('note_source_unit','fine_zone') else ('explicit_nominal_reference' if r['search_record_type'] in ('nominal_reference','resolved_reference') else 'same_topic_same_work')
  out.append({'work':'Likutey Halajot','document_title':'Likutey Halajot','pdf_page':r['pdf_page'],'printed_page':r['printed_page'],'section':r['halakhah_header_hint'],'visible_note_number':r['visible_note_number'],'quote':snippet(r['quote'],term),'surface_form':r['surface_form'],'evidence_type_cross_corpus':typ,'source':'library_likutey_halajot_investigative_search_v1','search_record_type':r['search_record_type'],'evidence_level':r['evidence_level'],'confidence':.9 if typ!='same_topic_same_work' else .75})
 return out
async def main():
 p=argparse.ArgumentParser();p.add_argument('--questions',type=Path,default=DEFAULT/'investigative_questions.yml');p.add_argument('--report-dir',type=Path,default=DEFAULT);a=p.parse_args();qs=json.loads(a.questions.read_text());a.report_dir.mkdir(parents=True,exist_ok=True);(a.report_dir/'answers').mkdir(exist_ok=True);results=[]
 async with await psycopg.AsyncConnection.connect(POSTGRES_DSN,row_factory=dict_row) as c:
  async with c.cursor() as cur:
   for q in qs:
    found=[]
    for term in q['query_terms_es']:
     for hit in await hits(cur,term):
      if (hit['work'],hit['pdf_page'],hit['quote']) not in {(x['work'],x['pdf_page'],x['quote']) for x in found}:found.append(hit)
    relation='no_cross_evidence' if len({h['work'] for h in found})<2 else ('explicit_cross_reference' if any(h['evidence_type_cross_corpus']=='explicit_nominal_reference' for h in found) else 'same_topic_parallel')
    results.append({'question':q,'hits':found,'cross_relation':relation,'warnings':['no_external_corpus_or_ai_used','thematic_parallel_is_not_doctrinal_relation']})
    groups={w:[h for h in found if h['work']==w] for w in ('Kitzur','Likutey Moharán II','Likutey Halajot')}
    lines=[f"# {q['title']}","","## Resumen breve",f"Hallazgos locales: {len(found)}. Relación: `{relation}`; toda conexión temática es contextual.",""]
    for work,rows in groups.items():
     lines+= [f'## {work}']
     lines += [f"- PDF {x.get('pdf_page')}; evidencia `{x['evidence_type_cross_corpus']}`; quote: {x['quote'][:350]!r}" for x in rows] or ['- Sin resultado literal local.']
    lines += ['','## Qué se puede afirmar',f"- Medio/débil: `{relation}` sólo según los quotes listados.",'','## Vacíos','- No se afirma relación doctrinal, autoría ni fuente fuera del corpus cargado.']
    (a.report_dir/'answers'/f"{q['id']}.md").write_text('\n'.join(lines)+'\n')
 (a.report_dir/'cross_corpus_qa_results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
 print(json.dumps({'questions':len(results),'with_hits':sum(bool(x['hits']) for x in results),'cross':sum(x['cross_relation']!='no_cross_evidence' for x in results),'report':str(a.report_dir)},ensure_ascii=False))
if __name__=='__main__':asyncio.run(main())
