"""Read-only per-document PG/Milvus/PDF audit after UI publication."""
import asyncio
import hashlib
import json
import sys
from pathlib import Path
from collections import Counter

OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(OUT.parents[3] / 'SrvRestAstroLS_v1/backend'))
import globalVar as g
import psycopg
from psycopg.rows import dict_row
from pymilvus import MilvusClient
import pymupdf

case = sys.argv[1]
books = json.loads((OUT / 'source-books.json').read_text())
book = next(b for b in books if b['label'].lower() == case)
pages = {'a':[187], 'b':[416], 'c':[1,10,51,53,55,56,143,200,270]}[case]
def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str))

async def main():
    assert g.ENV == 'development'
    job_id = json.loads((OUT / f'{case}-job-created.json').read_text())['job_id']
    client = MilvusClient(uri=f'http://{g.MILVUS_HOST}:{g.MILVUS_PORT}', timeout=20)
    try:
        async with await psycopg.AsyncConnection.connect(g.POSTGRES_DSN, row_factory=dict_row) as c:
            await c.execute('SET TRANSACTION READ ONLY')
            job = await (await c.execute('SELECT * FROM content_manager_jobs WHERE id=%s', (job_id,))).fetchone()
            did = job['document_id']
            doc = await (await c.execute('SELECT * FROM library_documents WHERE id=%s',(did,))).fetchone()
            chunks = await (await c.execute('SELECT id,chunk_uid,chunk_index,page_start,page_end,content,content_sha256,printed_page_label FROM library_document_chunks WHERE document_id=%s ORDER BY chunk_index',(did,))).fetchall()
            stored_pages = await (await c.execute('SELECT page_number,text,layout_notes FROM library_pages_v2 WHERE document_id=%s ORDER BY page_number',(did,))).fetchall()
            embeddings = await (await c.execute('SELECT e.chunk_id,e.milvus_primary_key,e.content_sha256,e.vector_status FROM library_chunk_embeddings e JOIN library_document_chunks c ON c.id=e.chunk_id WHERE c.document_id=%s',(did,))).fetchall()
            rows = []
            iterator = client.query_iterator(collection_name=g.MILVUS_COLLECTION_BRESLOV,
                filter='document_id == '+json.dumps(str(did)),output_fields=['pk','chunk_id','document_id','content_sha256','page_start','page_end','content_preview'],batch_size=500,consistency_level='Strong',timeout=30)
            try:
                while batch := iterator.next(): rows.extend(dict(r) for r in batch)
            finally: iterator.close()
            expected = {str(r['id']):r for r in chunks}
            found = Counter(r['chunk_id'] for r in rows)
            missing = len(set(expected)-set(found))
            orphans = len(set(found)-set(expected))
            duplicates = sum(n-1 for n in found.values() if n>1)
            assert missing == orphans == duplicates == 0
            assert len(chunks)==len(rows)==len(embeddings)
            assert len(stored_pages)==book['pages']
            assert doc['status']=='ready' and doc['source_sha256']==book['sha256']
            for r in rows:
                chunk=expected[r['chunk_id']]
                assert r['content_sha256']==chunk['content_sha256']
                assert r['page_start']==chunk['page_start'] and r['page_end']==chunk['page_end']
                assert chunk['content'].startswith(r['content_preview'])
            original = Path(book['source_path'])
            assert hashlib.sha256(original.read_bytes()).hexdigest()==book['sha256']
            pdf=pymupdf.open(original)
            samples=[]
            for page in pages:
                source=pdf[page-1]
                source.get_pixmap(matrix=pymupdf.Matrix(1.5,1.5)).save(OUT/f'{case}-pdf-{page}.png')
                canonical=next(r for r in stored_pages if r['page_number']==page)
                critical=[r for r in chunks if r['page_start']<=page<=r['page_end']]
                (OUT/f'{case}-pg-page-{page}.md').write_text(canonical['text'])
                (OUT/f'{case}-raw-page-{page}.txt').write_text(source.get_text())
                samples.append({'pdf_physical_page':page,'canonical':canonical,'chunks':critical})
            save(f'{case}-job-final.json',job)
            save(f'{case}-samples.json',samples)
            save(f'{case}-chunks.json',chunks)
            result={'status':'PASS','title':doc['title'],'sha256':doc['source_sha256'],
                'document_id':did,'job_id':job_id,'attempt':job['attempt_number'],
                'scope':'breslov_primary','pages':len(stored_pages),'chunks':len(chunks),'vectors':len(rows),
                'missing':missing,'orphans':orphans,'duplicates':duplicates,'publication':'ready',
                'chunk_lengths':{'min':min(len(r['content']) for r in chunks), 'max':max(len(r['content']) for r in chunks)},
                'timestamps':{'created':job['created_at'],'updated':job['updated_at']}}
            save(f'{case}-integrity.json',result)
            print(json.dumps(result,default=str))
    finally:client.close()
asyncio.run(main())
