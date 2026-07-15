"""Quick local cross-corpus literal probe."""
from __future__ import annotations
import argparse,asyncio,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from library_cross_corpus_investigative_qa import hits
import psycopg
from psycopg.rows import dict_row
from globalVar import POSTGRES_DSN
async def main():
 p=argparse.ArgumentParser();p.add_argument('--topic');p.add_argument('--reference');p.add_argument('--json',action='store_true');p.add_argument('--min-evidence');p.add_argument('--include-thematic',action='store_true');p.add_argument('--primary');p.add_argument('--cross');a=p.parse_args();term=a.topic or a.reference
 if not term:p.error('provide --topic or --reference')
 async with await psycopg.AsyncConnection.connect(POSTGRES_DSN,row_factory=dict_row) as c:
  async with c.cursor() as q:r=await hits(q,term)
 if a.min_evidence=='strong':r=[x for x in r if x['evidence_type_cross_corpus'] in ('literal_same_document_page','explicit_nominal_reference','note_source_context')]
 print(json.dumps(r,ensure_ascii=False,indent=2) if a.json else '\n'.join(f"{x['work']} p.{x.get('pdf_page')}: {x['quote'][:180]}" for x in r))
if __name__=='__main__':asyncio.run(main())
