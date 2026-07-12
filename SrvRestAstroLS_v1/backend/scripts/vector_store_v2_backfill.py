#!/usr/bin/env python3
"""Development-only idempotent V2 page-vector backfill for pgvector and Milvus."""
from __future__ import annotations
import argparse, asyncio, hashlib, json, os
from pathlib import Path
import httpx, psycopg
from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections, utility
from globalVar import LITELLM_API_KEY, LITELLM_BASE_URL, MILVUS_HOST, MILVUS_PORT, RESEARCH_EMBEDDING_MODEL_ALIAS

TABLE='library_vector_embeddings_v2_dev'; COLLECTION='tebaai_breslov_chunks_v2_dev'
FIELDS=[FieldSchema('pk',DataType.VARCHAR,is_primary=True,max_length=64),FieldSchema('chunk_id',DataType.VARCHAR,max_length=64),FieldSchema('document_id',DataType.VARCHAR,max_length=64),FieldSchema('knowledge_scope_code',DataType.VARCHAR,max_length=64),FieldSchema('collection_code',DataType.VARCHAR,max_length=64),FieldSchema('run_id',DataType.VARCHAR,max_length=64),FieldSchema('language',DataType.VARCHAR,max_length=8),FieldSchema('page',DataType.INT64),FieldSchema('embedding_model',DataType.VARCHAR,max_length=128),FieldSchema('embedding_version',DataType.VARCHAR,max_length=32),FieldSchema('text_hash',DataType.VARCHAR,max_length=64),FieldSchema('text_preview',DataType.VARCHAR,max_length=1024),FieldSchema('embedding',DataType.FLOAT_VECTOR,dim=1536)]
def preview(text): return text.encode('utf-8')[:1024].decode('utf-8','ignore')
async def embeds(texts):
 async with httpx.AsyncClient(timeout=120) as c:
  r=await c.post(f'{LITELLM_BASE_URL}/v1/embeddings',headers={'Authorization':f'Bearer {LITELLM_API_KEY}'},json={'model':RESEARCH_EMBEDDING_MODEL_ALIAS,'input':texts});r.raise_for_status();return [x['embedding'] for x in r.json()['data']]
async def main(a):
 conf=dict(user=os.environ['DB_PG_USER'],password=os.environ['DB_PG_PASS'],host=os.environ.get('DB_PG_IP','localhost'),port=int(os.environ.get('DB_PG_PORT','5432')),dbname='tebaai')
 with psycopg.connect(**conf) as pg:
  with pg.cursor() as c:
   c.execute('CREATE EXTENSION IF NOT EXISTS vector')
   c.execute(f'''CREATE TABLE IF NOT EXISTS {TABLE} (chunk_id text PRIMARY KEY, document_id uuid NOT NULL, knowledge_scope_code text NOT NULL, collection_code text NOT NULL, run_id uuid NOT NULL, language text NOT NULL, page integer NOT NULL, embedding_model text NOT NULL, embedding_version text NOT NULL, text_hash text NOT NULL, text_preview text NOT NULL, embedding vector(1536) NOT NULL, created_at timestamptz default now(), updated_at timestamptz default now())''')
   c.execute(f'CREATE INDEX IF NOT EXISTS {TABLE}_scope_idx ON {TABLE}(knowledge_scope_code,run_id,document_id,language)')
   c.execute(f'CREATE INDEX IF NOT EXISTS {TABLE}_hnsw_idx ON {TABLE} USING hnsw (embedding vector_cosine_ops)')
   c.execute('SELECT document_id::text,scope_code FROM library_ingestion_runs_v2 WHERE run_id=%s',(a.run_id,)); run=c.fetchone(); assert run, 'run not found'
   c.execute('SELECT page_number,text FROM library_pages_v2 WHERE run_id=%s AND char_count>0 ORDER BY page_number',(a.run_id,)); pages=c.fetchall()
  pg.commit()
  if a.dry_run: return finish(a,{'status':'BACKFILL_DRY_RUN_OK','pages':len(pages)})
  connections.connect(alias='default',host=MILVUS_HOST,port=MILVUS_PORT,timeout=10)
  if COLLECTION not in utility.list_collections():
   col=Collection(COLLECTION,CollectionSchema(FIELDS));col.create_index('embedding',{'index_type':'HNSW','metric_type':'COSINE','params':{'M':16,'efConstruction':200}})
  else: col=Collection(COLLECTION)
  col.load(); inserted=0
  for i in range(0,len(pages),a.batch_size):
   batch=pages[i:i+a.batch_size]; vecs=await embeds([t[:6000] for _,t in batch]); rows=[]
   with pg.cursor() as c:
    for (page,text),vec in zip(batch,vecs):
     pk=hashlib.sha256(f'{a.run_id}:{page}'.encode()).hexdigest(); h=hashlib.sha256(text.encode()).hexdigest(); text_preview=preview(text)
     c.execute(f'''INSERT INTO {TABLE}(chunk_id,document_id,knowledge_scope_code,collection_code,run_id,language,page,embedding_model,embedding_version,text_hash,text_preview,embedding,updated_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::vector,now()) ON CONFLICT(chunk_id) DO UPDATE SET embedding=excluded.embedding,text_hash=excluded.text_hash,text_preview=excluded.text_preview,updated_at=now()''',(pk,run[0],a.scope,'breslov_test',a.run_id,'es',page,RESEARCH_EMBEDDING_MODEL_ALIAS,'v2',h,text_preview,'['+','.join(map(str,vec))+']'))
     rows.append({'pk':pk,'chunk_id':pk,'document_id':run[0],'knowledge_scope_code':a.scope,'collection_code':'breslov_test','run_id':a.run_id,'language':'es','page':page,'embedding_model':RESEARCH_EMBEDDING_MODEL_ALIAS,'embedding_version':'v2','text_hash':h,'text_preview':text_preview,'embedding':vec})
   pg.commit();col.upsert(rows);inserted+=len(rows)
  col.flush();connections.disconnect('default')
  return finish(a,{'status':'BACKFILL_BOTH_OK','pages':len(pages),'inserted_or_updated':inserted,'table':TABLE,'collection':COLLECTION})
def finish(a,r):a.json_out.parent.mkdir(parents=True,exist_ok=True);a.json_out.write_text(json.dumps(r,indent=2));print(json.dumps(r));return 0
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--run-id',required=True);p.add_argument('--scope',required=True);p.add_argument('--batch-size',type=int,default=64);p.add_argument('--dry-run',action='store_true');p.add_argument('--json-out',type=Path,required=True);raise SystemExit(asyncio.run(main(p.parse_args())))
