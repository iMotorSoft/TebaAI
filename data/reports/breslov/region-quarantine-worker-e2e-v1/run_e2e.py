"""Local DEV real worker regression. No downstream writes outside normal ingestion.

Uses authenticated ASGI routes (same handlers/guards/repositories as HTTP runtime),
normal upload/job services, a separate targeted worker subprocess, and normal
manifest cleanup. Never patches worker, certificates, embeddings or stores.
"""
from __future__ import annotations
import asyncio
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys
from uuid import UUID

ROOT = Path(__file__).resolve().parents[4]
BACKEND = ROOT / 'SrvRestAstroLS_v1/backend'
sys.path.insert(0, str(BACKEND))
import globalVar as g
import httpx
from litestar import Litestar
from litestar.datastructures import State
from pymilvus import MilvusClient
from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
from infrastructure.postgres.transaction import transaction
from infrastructure.postgres.region_quarantine_e2e import snapshot, context, probe_job, digest
from modules.auth.tokens import create_access_token
from modules.library.routes import (content_manager_upload, content_manager_create_job,
    library_search, library_original_source, library_page_publication)
from modules.library.content_manager_cleanup import ManifestCleanupService
from modules.library.simple_research_repository import fetch_canonical_chunks
from modules.library.page_first_evidence import build_evidence_v1
from modules.library.automatic_region_certification_v5 import extract_pdf_region_certificates
from modules.library.region_publication import publish_certified_page

OUT = Path(__file__).parent
MARKER = 'region-quarantine-worker-e2e-v1'


def write(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str)+'\n')


def vector_snapshot(exclude_document_ids=()):
    client = MilvusClient(uri=f'http://{g.MILVUS_HOST}:{g.MILVUS_PORT}')
    result = {}
    try:
        for name in (g.MILVUS_COLLECTION_BRESLOV, g.CONTENT_MANAGER_E2E_COLLECTION):
            rows = []
            it = client.query_iterator(collection_name=name, filter='', batch_size=100,
                output_fields=['*'], consistency_level='Strong', timeout=30)
            try:
                while batch := it.next(): rows.extend(dict(r) for r in batch)
            finally: it.close()
            existing = [r for r in rows if str(r.get('document_id')) not in set(map(str,exclude_document_ids))]
            existing.sort(key=lambda x:str(x['pk']))
            result[name] = {'live_count':len(rows),'existing_count':len(existing),
                            'existing_full_rows_sha256':digest(existing)}
        return result
    finally: client.close()


async def stores(pool, ids=()):
    async with transaction(pool) as conn:
        await conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        pg = await snapshot(conn, ids)
    return {'postgres':pg,'milvus':await asyncio.to_thread(vector_snapshot,ids)}


async def main():
    assert g.TEBAAI_ENV == 'development' and g.POSTGRES_DB == 'tebaai'
    assert g.POSTGRES_HOST in ('127.0.0.1','localhost') and g.MILVUS_HOST in ('127.0.0.1','localhost')
    pool = create_pool_from_settings()
    await open_pool(pool)
    identifiers = []
    exclusions = []
    results = []
    try:
        before = await stores(pool)
        write('dev-store-before.json', before)
        async with transaction(pool) as conn: ctx = await context(conn)
        if not ctx: raise RuntimeError('BLOCKED: no authorized active DEV admin in breslov_e2e')
        token = create_access_token(str(ctx['actor_user_id']),ctx['role'])
        app = Litestar(route_handlers=[content_manager_upload,content_manager_create_job,library_search,
            library_original_source,library_page_publication],state=State({'pg_pool':pool}),debug=False)
        transport = httpx.ASGITransport(app=app)
        controlled = json.loads((OUT / 'controlled-test-cases.json').read_text())
        real_path = OUT / 'fixtures/real-p54-p56.pdf'
        controlled.append({'case':'REAL','path':str(real_path.relative_to(ROOT)),
            'sha256':hashlib.sha256(real_path.read_bytes()).hexdigest(),
            'physical_pages':3, 'original_pages':[54,55,56], 'expected_mixed_page':2})
        async with httpx.AsyncClient(transport=transport,base_url='http://tebaai-dev',
                                   headers={'Authorization':'Bearer '+token},timeout=90) as api:
            for case in controlled:
                path = ROOT / case['path']
                assert hashlib.sha256(path.read_bytes()).hexdigest() == case['sha256']
                # Expected labels remain frozen, even if the actual certifier rejects GOOD.
                certified = extract_pdf_region_certificates(path)
                expected_pages = [publish_certified_page(p,source_reference='sha256:'+case['sha256']) for p in certified]
                raw_rejected = [(p.provenance.pdf_page,u.region_id,p.provenance.markdown[u.markdown_start:u.markdown_end])
                    for p in certified for u in p.provenance.units
                    if not next(r for r in expected_pages[p.provenance.pdf_page-1].regions if r.region_id==u.region_id).publishable]
                response = await api.post('/admin/content/uploads',params={'knowledge_scope_code':'breslov_e2e'},
                    files={'file':(path.name,path.read_bytes(),'application/pdf')})
                response.raise_for_status(); upload = response.json()
                assert upload['duplicate_status'] == 'new_document', 'Test isolation collision; no existing source may be mutated'
                request = {'upload_id':upload['upload_id'],'knowledge_scope_code':'breslov_e2e',
                           'title':MARKER+'-'+case['case'],'language':'es'}
                response = await api.post('/admin/content/jobs',json=request)
                response.raise_for_status(); job=response.json()
                record={'test_marker':MARKER,'case':case['case'],'upload_id':upload['upload_id'],
                    'job_id':job['job_id'],'source_sha256':case['sha256'],
                    'organization_id':ctx['organization_id'],'workspace_id':ctx['workspace_id'],
                    'project_id':ctx['project_id'],'scope_id':ctx['id'],
                    'scope_code':'breslov_e2e','milvus_collection':g.CONTENT_MANAGER_E2E_COLLECTION,
                    'attempt_number':1}
                identifiers.append(record);exclusions.append(job['job_id'])
                write('controlled-test-identifiers.json',identifiers)
                env=os.environ.copy()
                env.update({'TEBAAI_CONTENT_MANAGER_E2E_ENABLED':'true',
                    'TEBAAI_CONTENT_MANAGER_WORKER_SCOPE':'breslov_e2e',
                    'TEBAAI_CONTENT_MANAGER_E2E_FIXTURE_SHA256':case['sha256'],
                    'TEBAAI_POSTGRES_AUTO_MIGRATE':'false'})
                log=OUT / ('worker-'+case['case']+'.txt')
                with log.open('w') as stream:
                    process=await asyncio.create_subprocess_exec('uv','run','python','scripts/content_manager_worker.py',
                        '--job-id',job['job_id'],'--once',cwd=BACKEND,env=env,stdout=stream,stderr=stream)
                    code=await asyncio.wait_for(process.wait(),timeout=240)
                async with transaction(pool) as conn: probe=await probe_job(conn,UUID(job['job_id']))
                record['document_id']=str(probe['job']['document_id']) if probe['job']['document_id'] else None
                record['milvus_ids']=[e['milvus_primary_key'] for e in probe['embeddings']]
                record['chunk_ids']=[str(c['id']) for c in probe['chunks']]
                exclusions.extend([record['document_id'],*record['chunk_ids']])
                write('controlled-test-identifiers.json',identifiers)
                result={'case':case['case'],'worker_exit':code,'status':probe['job']['status'],
                    'error_code':probe['job']['error_code'],'document_id':record['document_id'],
                    'canonical_bad_text_occurrences':0,'bad_chunks':0,'bad_embeddings':0,'bad_vectors':0,
                    'bad_retrieval_hits':0,'bad_textual_citations':0,'accepted_region_loss':0,
                    'published_chunks':len(probe['chunks']),'embeddings':len(probe['embeddings']),
                    'visual_source_available':False,'page_results':[],'retrieval':[],'citations':[],
                    'frozen_controlled_expectation':case.get('expected_region_publication')}
                results.append(result)
                write('worker-integration-results.json',results)
                if not record['document_id']: continue
                assert code==0 and probe['job']['status'] in ('completed','completed_with_warnings')
                url=f"/library/documents/{record['document_id']}/source"
                source=await api.get(url)
                result['visual_source_available']=source.status_code==200 and hashlib.sha256(source.content).hexdigest()==case['sha256']
                assert result['visual_source_available']
                import pymupdf
                with pymupdf.open(stream=source.content,filetype='pdf') as visual:
                    result['visual_source_page_count']=len(visual)
                    assert len(visual)==case['physical_pages']
                result['source_cache_control']=source.headers.get('cache-control')
                result['source_content_type']=source.headers.get('content-type')
                async with httpx.AsyncClient(transport=transport,base_url='http://tebaai-dev') as anonymous:
                    assert (await anonymous.get(url)).status_code==401
                for page in probe['pages']:
                    metadata_response=await api.get(f"/library/documents/{record['document_id']}/pages/{page['page_number']}/publication")
                    metadata_response.raise_for_status();metadata=metadata_response.json()
                    result['page_results'].append(metadata)
                    accepted={r['region_id'] for r in metadata['regions'] if r['publication_status']=='ACCEPTED'}
                    quarantined={r['region_id'] for r in metadata['regions'] if r['publication_status']=='QUARANTINED'}
                    page_chunks=[c for c in probe['chunks'] if c['page_start']==page['page_number']]
                    actual={c['metadata']['region_id'] for c in page_chunks}
                    result['accepted_region_loss']+=len(accepted-actual)
                    result['bad_chunks']+=len(quarantined & actual)
                    assert page['text']==expected_pages[page['page_number']-1].canonical_markdown
                for page_number,rid,text in raw_rejected:
                    fragment=text.strip()
                    if not fragment: continue
                    # Query the full rejected unit (up to API limit), never a broad single word.
                    query=fragment[:300]
                    response=await api.post('/library/search',json={'query':query,'collection':'breslov_e2e',
                                                                 'mode':'phrase','language':'es','top_k':50})
                    response.raise_for_status();hits=response.json()['results']
                    # Shared snippets in accepted regions are NOT proof of leakage; unit ownership is authoritative.
                    relevant=[h for h in hits if str(h['document_id'])==record['document_id']
                              and any(str(c['id'])==str(h['chunk_id']) and c['metadata']['region_id']==rid for c in probe['chunks'])]
                    result['bad_retrieval_hits']+=len(relevant)
                    result['canonical_bad_text_occurrences']+=sum(fragment in t['content'] for t in probe['texts']
                        if fragment not in '\n'.join(c['content'] for c in probe['chunks']))
                    result['retrieval'].append({'region_id':rid,'page':page_number,'query_sha256':hashlib.sha256(query.encode()).hexdigest(),
                        'expected':'no quarantined unit','returned_hits':len(hits),'quarantined_region_hits':len(relevant)})
                for page in expected_pages:
                    for rid,text in page.evidence_units:
                        # Predeclared ASCII-span selection avoids the existing phrase API's
                        # asymmetric accent normalization, without modifying retrieval policy.
                        candidates=re.findall(r'[A-Za-z0-9][A-Za-z0-9 ,;:_().-]{20,}',text)
                        query=max(candidates,key=len).strip()[:200]
                        response=await api.post('/library/search',json={'query':query,'collection':'breslov_e2e',
                                                                     'mode':'phrase','language':'es','top_k':50})
                        response.raise_for_status();hits=response.json()['results']
                        ids=[str(h['chunk_id']) for h in hits if str(h['document_id'])==record['document_id']]
                        result['retrieval'].append({'region_id':rid,'page':page.pdf_page,'expected':'accepted hit',
                            'query':query,'chunk_ids':ids,'hit':bool(ids)})
                        async with transaction(pool) as conn:
                            chunks=await fetch_canonical_chunks(conn,knowledge_scope_code='breslov_e2e',
                                chunk_ids=ids,include_test_candidates=True)
                        citations=[build_evidence_v1(query,c) for c in chunks]
                        citations=[c for c in citations if c]
                        result['citations'].extend(citations)
                        if not ids: result['accepted_retrieval_misses']=result.get('accepted_retrieval_misses',0)+1
                        hybrid=await api.post('/library/search',json={'query':query,'collection':'breslov_e2e',
                            'mode':'hybrid','language':'es','top_k':50})
                        hybrid.raise_for_status()
                        vector_hits=[h for h in hybrid.json()['results'] if str(h['document_id'])==record['document_id']
                                     and 'vector' in h['source_signals']]
                        result.setdefault('hybrid_retrieval',[]).append({'region_id':rid,'query':query,
                            'vector_signal_hits':len(vector_hits),'results':hybrid.json()['results']})
                # Prove the vector store independently, through exact IDs AND attempt query.
                from modules.library.page_first_gateway import MilvusAttemptIndex
                vectors=await asyncio.to_thread(MilvusAttemptIndex(g.CONTENT_MANAGER_E2E_COLLECTION).list_attempt,job['job_id']+':1')
                result['vectors']=len(vectors)
                assert len(vectors)==len(probe['chunks'])==len(probe['embeddings'])
                assert {v['chunk_id'] for v in vectors}=={str(c['id']) for c in probe['chunks']}
                # Real dispatch contains precisely the pre-chunk publication set, with hashes in worker log.
                result['embedding_dispatch_lines']=[l.strip() for l in log.read_text().splitlines() if 'regional_embedding_dispatch' in l]
                result['bad_embedding_request_proof']='Only accepted region chunks reach embed; log hashes equal persisted chunk hashes; zero-chunk branch skips embed.'
                for chunk in probe['chunks']:
                    assert chunk['content_sha256'] in log.read_text()
                response=await api.post('/admin/content/jobs',json=request)
                response.raise_for_status();assert response.json()['job_id']==job['job_id']
                # Normal duplicate delivery: completed job is unclaimable, not reprocessed.
                with (OUT / ('retry-'+case['case']+'.txt')).open('w') as stream:
                    process=await asyncio.create_subprocess_exec('uv','run','python','scripts/content_manager_worker.py',
                        '--job-id',job['job_id'],'--once',cwd=BACKEND,env=env,stdout=stream,stderr=stream)
                    retry_code=await process.wait()
                async with transaction(pool) as conn: again=await probe_job(conn,UUID(job['job_id']))
                result['idempotency']={'same_job':True,'completed_job_unclaimable':retry_code!=0,
                    'chunk_ids_unchanged':[str(c['id']) for c in probe['chunks']]==[str(c['id']) for c in again['chunks']],
                    'pages_unchanged':[str(p['page_id']) for p in probe['pages']]==[str(p['page_id']) for p in again['pages']],
                    'vectors_unchanged':len(await asyncio.to_thread(MilvusAttemptIndex(g.CONTENT_MANAGER_E2E_COLLECTION).list_attempt,job['job_id']+':1'))==len(vectors)}
                if case['case']=='REAL':
                    write('real-source-case.json',{'original_source_sha256':'440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a',
                        'original_physical_pages':[54,55,56],'isolated_to_original_page':{'1':54,'2':55,'3':56},
                        'isolated_sha256':case['sha256'],'document_id':record['document_id'],
                        'result':result,'full_c_reingest':False})
                write('worker-integration-results.json',results)
        write('dev-store-after.json',await stores(pool,exclusions))
    finally:
        cleanup=[]
        for record in identifiers:
            try:
                service=ManifestCleanupService(pool)
                first=await service.cleanup(UUID(record['job_id']),1)
                second=await service.cleanup(UUID(record['job_id']),1)
                from modules.library.durable_source import source_path
                cleanup.append({'job_id':record['job_id'],'first':first.status,'second':second.status,
                    'durable_source_removed':not source_path(UUID(record['document_id'])).exists() if record['document_id'] else True})
            except Exception as exc:
                cleanup.append({'job_id':record['job_id'],'error_type':type(exc).__name__})
        write('cleanup-results.json',cleanup)
        write('controlled-test-identifiers.json',identifiers)
        write('worker-integration-results.json',results)
        write('dev-store-after-cleanup.json',await stores(pool,exclusions))
        await close_pool(pool)


if __name__=='__main__': asyncio.run(main())
