"""Interactive literal-only probe across the five loaded Breslov corpora."""
import argparse,asyncio,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));from library_cross_corpus_potencia_qa import snip
import psycopg
from psycopg.rows import dict_row
from globalVar import POSTGRES_DSN
async def main():
 p=argparse.ArgumentParser();p.add_argument('--topic');p.add_argument('--reference');p.add_argument('--json',action='store_true');p.add_argument('--min-evidence');a=p.parse_args();term=a.topic or a.reference
 if not term:p.error('provide --topic or --reference')
 sqls=[('Kitzur',"select null::int pdf_page,content quote,'chunk' source from library_document_chunks c join library_documents d on d.id=c.document_id where d.title='KITZUR' and content ilike %s limit 5"),('LM II',"select pdf_page_number pdf_page,literal_text quote,'library_lmii_search_ready_v2' source from library_lmii_search_ready_v2 where literal_text ilike %s limit 5"),('LH',"select pdf_page,coalesce(resolution_quote,nominal_reference_quote,note_source_quote,fine_zone_quote,page_text) quote,'library_likutey_halajot_investigative_search_v1' source from library_likutey_halajot_investigative_search_v1 where coalesce(resolution_quote,nominal_reference_quote,note_source_quote,fine_zone_quote,page_text,'') ilike %s limit 5"),('LM XV',"select pdf_page,coalesce(text_quote,raw_text) quote,'library_lm_xv_kdp_search_ready_v3' source from library_lm_xv_kdp_search_ready_v3 where coalesce(text_quote,raw_text,'') ilike %s limit 5"),('La Potencia',"select pdf_page,quote,'library_la_potencia_plegaria_investigative_search_v1' source from library_la_potencia_plegaria_investigative_search_v1 where quote ilike %s limit 5")]
 rows=[]
 async with await psycopg.AsyncConnection.connect(POSTGRES_DSN,row_factory=dict_row) as c:
  async with c.cursor() as q:
   for work,sql in sqls:
    await q.execute(sql,(f'%{term}%',));rows += [{'work':work,'pdf_page':r['pdf_page'],'quote':snip(r['quote'],term),'evidence_type':'literal_same_page','source':r['source'],'warning':'pdf_page_null_for_kitzur_chunk' if work=='Kitzur' else None} for r in await q.fetchall()]
 print(json.dumps(rows,ensure_ascii=False,indent=2) if a.json else '\n'.join(f"{r['work']} p.{r['pdf_page']}: {r['quote'][:160]}" for r in rows))
asyncio.run(main())
