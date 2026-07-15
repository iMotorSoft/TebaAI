"""Deterministic, literal-only cross-corpus QA including La Potencia."""
import argparse,asyncio,json,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));import psycopg
from psycopg.rows import dict_row
from globalVar import POSTGRES_DSN
ROOT=Path(__file__).resolve().parents[3];D=ROOT/'data/reports/breslov/2026-07-15-cross-corpus-qa-potencia-v1'
def snip(t,x):
 i=t.lower().find(x.lower());return t[max(0,i-150):i+380].strip() if i>=0 else t[:400].strip()
async def main():
 p=argparse.ArgumentParser();p.add_argument('--questions',type=Path,default=D/'investigative_questions.yml');a=p.parse_args();qs=json.loads(a.questions.read_text());D.mkdir(parents=True,exist_ok=True);(D/'answers').mkdir(exist_ok=True);out=[]
 async with await psycopg.AsyncConnection.connect(POSTGRES_DSN,row_factory=dict_row) as c:
  async with c.cursor() as q:
   for x in qs:
    hs=[]
    for term in x['query_terms_es']:
     for work,sql in [('Kitzur',"select null::int pdf_page,content quote,'chunk' record from library_document_chunks c join library_documents d on d.id=c.document_id where d.title='KITZUR' and content ilike %s limit 2"),('LM II',"select pdf_page_number pdf_page,literal_text quote,'page_literal' record from library_lmii_search_ready_v2 where literal_text ilike %s limit 2"),('LH',"select pdf_page,coalesce(resolution_quote,nominal_reference_quote,note_source_quote,fine_zone_quote,page_text) quote,search_record_type record from library_likutey_halajot_investigative_search_v1 where coalesce(resolution_quote,nominal_reference_quote,note_source_quote,fine_zone_quote,page_text,'') ilike %s limit 2"),('LM XV',"select pdf_page,coalesce(text_quote,raw_text) quote,'fine_zone' record from library_lm_xv_kdp_search_ready_v3 where coalesce(text_quote,raw_text,'') ilike %s limit 2"),('La Potencia',"select pdf_page,quote,search_record_type record from library_la_potencia_plegaria_investigative_search_v1 where quote ilike %s limit 3")]:
      await q.execute(sql,(f'%{term}%',))
      for h in await q.fetchall():hs.append({'work':work,'pdf_page':h['pdf_page'],'quote':snip(h['quote'],term),'record_type':h['record'],'evidence_type':'literal_same_page','warning':'pdf_page_null_for_kitzur_chunk' if work=='Kitzur' else None})
    uniq=[]
    for h in hs:
     if (h['work'],h['pdf_page'],h['quote']) not in {(z['work'],z['pdf_page'],z['quote']) for z in uniq}:uniq.append(h)
    relation='cross_work_literal_parallel' if len({h['work'] for h in uniq})>1 else 'no_cross_evidence';out.append({'id':x['id'],'question':x['question'],'hits':uniq,'cross_relation':relation})
    lines=[f"# {x['title']}",'','## Resumen breve',f"{len(uniq)} hallazgos literales; clasificación cruzada: `{relation}`.",'']
    for w in ['Kitzur','LM II','LH','LM XV','La Potencia']:
     lines+=[f'## {w}']+[f"- Página {h['pdf_page']}; `{h['evidence_type']}`; {h['quote'][:330]!r}" for h in uniq if h['work']==w] or ['- Sin evidencia literal recuperada.']
    lines+=['','## Qué se puede afirmar', '- Sólo se reportan apariciones literales y paralelos entre obras; no relaciones doctrinales.','','## Vacíos','- Un vacío de búsqueda no prueba ausencia en el corpus.']
    (D/'answers'/f"{x['id']}.md").write_text('\n'.join(lines)+'\n')
 (D/'cross_corpus_qa_results.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps({'questions':len(out),'with_hits':sum(bool(x['hits']) for x in out)}))
if __name__=='__main__':
 asyncio.run(main())
