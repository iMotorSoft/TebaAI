"""Frozen V2 harness. Run from backend: uv run python <absolute path> preflight|certification.
Real committed synthetic PostgreSQL switches. No ingestion, extraction or vector API.
"""
import asyncio
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

sys.path[:0] = [str(Path.cwd()), str(Path.cwd() / 'tests')]
from modules.library import generation as g
from test_generation_foundation import _connection
from test_generation_rollback_remediation import assert_generic_cleanup_rejected

R = Path(__file__).resolve().parent
C = 'ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa'
CL = 'db200a31-b547-5668-d968-06d0ec36ad95'
MODE = sys.argv[1]
assert MODE in ('preflight', 'certification')

def save(name, value):
    if MODE == 'preflight' and not name.startswith('preflight-'):
        name = 'preflight-' + name
    (R / name).write_text(json.dumps(value, indent=2, default=str) + '\n')

async def all_rows(conn, sql, p=None):
    async with conn.cursor() as cur:
        await cur.execute(sql, p)
        return await cur.fetchall()

async def current_c(conn):
    return {
        'document': await all_rows(conn, 'SELECT * FROM library_documents WHERE id=%s', (C,)),
        'logical': await all_rows(conn, 'SELECT * FROM library_logical_documents WHERE id=%s', (CL,)),
        'generations': await all_rows(conn, 'SELECT * FROM library_document_generations WHERE logical_document_id=%s ORDER BY id', (CL,)),
        'pointer': await all_rows(conn, 'SELECT * FROM library_logical_document_active_generations WHERE logical_document_id=%s', (CL,)),
        'audit': await all_rows(conn, 'SELECT * FROM library_generation_activation_audit WHERE logical_document_id=%s ORDER BY id', (CL,)),
    }

async def run():
    tag = ('PREFLIGHT-V2-' if MODE == 'preflight' else 'CERT-V2-') + str(uuid4())
    collection, logical, cross_logical = [str(uuid4()) for _ in range(3)]
    ids, docs = {}, {}
    atomicity = []
    identifiers = {'tag': tag, 'mode': MODE, 'collection_id': collection,
                   'logical_document_id': logical, 'cross_logical_document_id': cross_logical,
                   'generations': ids, 'documents': docs, 'created_at': datetime.now(timezone.utc).isoformat()}
    async with _connection() as conn, _connection() as observer:
        # Independent observer uses READ COMMITTED and explicit commits to avoid stale snapshots.
        before_c = await current_c(observer)
        assert before_c['document'] and before_c['logical'] and before_c['pointer']
        await observer.commit()
        columns = await all_rows(conn, """SELECT table_name,column_name,data_type FROM information_schema.columns
            WHERE table_schema='public' AND table_name IN
            ('library_logical_documents','library_document_generations',
             'library_logical_document_active_generations','library_generation_activation_audit',
             'library_documents','library_collections_legacy','content_manager_jobs',
             'content_manager_job_resources') ORDER BY table_name,ordinal_position""")
        types = {(r['table_name'],r['column_name']):r['data_type'] for r in columns}
        for table, cols in {
            'library_logical_documents':['id','collection_id'],
            'library_document_generations':['id','logical_document_id','document_id'],
            'library_logical_document_active_generations':['logical_document_id','generation_id','expected_generation_id'],
            'library_generation_activation_audit':['logical_document_id','from_generation_id','to_generation_id','expected_generation_id'],
        }.items():
            for col in cols: assert types[table,col] == 'uuid', (table,col)
        indexes = await all_rows(conn,"SELECT indexname,indexdef FROM pg_indexes WHERE tablename='library_document_generations'")
        assert any('UNIQUE INDEX' in r['indexdef'] and "status = 'ACTIVE'" in r['indexdef'] for r in indexes)
        fks = await all_rows(conn, """SELECT conrelid::regclass::text AS table_name,conname,
            pg_get_constraintdef(oid) AS definition FROM pg_constraint WHERE contype='f'
            AND conrelid IN ('library_document_generations'::regclass,
              'library_logical_document_active_generations'::regclass) ORDER BY conname""")
        assert any('logical_document_id, generation_id' in r['definition'] for r in fks)
        binding = await g.fetch_one(conn, """SELECT pg_typeof(%(uuid)s)::text AS uuid_bind,
            pg_typeof(%(text)s::text)::text AS text_bind, pg_typeof(%(text)s::text::uuid)::text AS cast_bind,
            (%(uuid)s = %(text)s::text::uuid) AS equal""", {'uuid':uuid4(), 'text':str(uuid4())})
        assert binding['uuid_bind']=='uuid' and binding['text_bind']=='text' and binding['cast_bind']=='uuid'
        if MODE == 'preflight':
            save('preflight-schema.json', {'SCHEMA_AVAILABLE':'YES','EXPECTED_TYPES':'YES','columns':columns,'foreign_keys':fks,'indexes':indexes})
            save('preflight-postgres-binding.json', {'UUID_TEXT_BINDING_PREFLIGHT':'PASS', 'probe':binding,
                'fixture_parameter_types':'str UUIDs for production API; separate text collection code binding',
                'casts':'explicit ::text then ::uuid in binding probe; production uses column type inference',
                'expected_active_generation_id':'str UUID -> expected_generation_id uuid column',
                'v1_fix':'collection id and code are separate named parameters; no repeated UUID/text binding'})
        await conn.commit()
        async def state():
            return {'generations': await all_rows(conn,'SELECT * FROM library_document_generations WHERE logical_document_id=%s ORDER BY id',(logical,)),
                    'pointer':await all_rows(conn,'SELECT * FROM library_logical_document_active_generations WHERE logical_document_id=%s',(logical,)),
                    'audit':await all_rows(conn,'SELECT * FROM library_generation_activation_audit WHERE logical_document_id=%s ORDER BY id',(logical,))}
        async def observe(label):
            rows = await all_rows(observer,'SELECT id,status FROM library_document_generations WHERE logical_document_id=%s ORDER BY id',(logical,))
            pointer = await g.resolve_active_generation_id(observer,logical)
            active = [str(r['id']) for r in rows if r['status']=='ACTIVE']
            assert len(active)==1 and active[0]==str(pointer)
            atomicity.append({'label':label,'active_ids':active,'pointer':pointer})
            await observer.commit()
        rollback_calls = set()
        async def switch(name, expected, operation='CUTOVER'):
            def profile(frame,event,arg):
                if event=='call':
                    module=frame.f_globals.get('__name__','')
                    if module.startswith('modules.library'):
                        rollback_calls.add(module+'.'+frame.f_code.co_name)
            if operation=='ROLLBACK': sys.setprofile(profile)
            try:
                result = await g.activate_generation(conn,logical_document_id=logical,
                    expected_active_generation_id=ids[expected] if expected else None,
                    new_generation_id=ids[name],operation=operation)
            finally:
                if operation=='ROLLBACK': sys.setprofile(None)
            assert all(c.startswith('modules.library.generation.') for c in rollback_calls), rollback_calls
            # Observer must see old consistent committed state while switch is uncommitted.
            if expected: await observe('before commit '+operation+' '+name)
            await conn.commit()
            await observe('after commit '+operation+' '+name)
            return result
        async def reject(name,expected,operation='ROLLBACK',error=g.GenerationPreconditionError):
            before = await state()
            try:
                await g.activate_generation(conn,logical_document_id=logical,
                    expected_active_generation_id=ids[expected],new_generation_id=ids[name],operation=operation)
            except error as exc:
                detail={'result':'REJECTED','exception':type(exc).__name__,'operation':operation,'target':ids[name]}
            else: raise AssertionError('Illegal activation accepted: '+name+' '+operation)
            assert await state()==before
            await conn.commit()
            await observe('rejected '+name+' '+operation)
            return detail
        try:
            await g.execute(conn,"""INSERT INTO library_collections_legacy(id,code,name,default_language,is_active)
                VALUES (%(id)s,%(code)s,'V2 synthetic','es',true)""",{'id':collection,'code':tag})
            for lid in (logical,cross_logical):
                await g.execute(conn,"""INSERT INTO library_logical_documents(id,collection_id,title,source_sha256)
                    VALUES (%(id)s,%(collection)s,%(title)s,%(sha)s)""",
                    {'id':lid,'collection':collection,'title':tag,'sha':lid})
            for name,status in [('OLD','CANDIDATE'),('NEW','CANDIDATE'),('ARBITRARY','INACTIVE'),
                                ('NEVER','INACTIVE'),('BUILDING','BUILDING'),('FAILED','FAILED'),
                                ('G1','CANDIDATE'),('G2','CANDIDATE'),('B','CANDIDATE'),('CROSS','CANDIDATE')]:
                document = str(uuid4()); docs[name]=document
                lid = cross_logical if name=='CROSS' else logical
                await g.execute(conn,"""INSERT INTO library_documents(id,collection_id,title,language,source_type,
                    source_filename,source_size_bytes,source_sha256,status)
                    VALUES (%(id)s,%(collection)s,%(title)s,'es','pdf','synthetic.pdf',1,%(sha)s,'test_candidate')""",
                    {'id':document,'collection':collection,'title':tag,'sha':lid})
                row = await g.register_generation(conn,logical_document_id=lid,document_id=document,
                    pipeline_version=name,source_sha256=lid,status=status)
                ids[name]=str(row['id'])
            save('certification-fixture-identifiers.json', identifiers)
            await conn.commit()
            await switch('OLD',None)
            initial = await state()
            assert str(initial['pointer'][0]['generation_id'])==ids['OLD']
            cutover = await switch('NEW','OLD')
            assert cutover['result']=='APPLIED'
            old = await g.get_generation(conn,ids['OLD'])
            new = await g.get_generation(conn,ids['NEW'])
            assert old['status']=='INACTIVE' and old['retention_hold'] and new['status']=='ACTIVE'
            await assert_generic_cleanup_rejected(old)
            from modules.library.content_manager_cleanup import ManifestCleanupService
            from modules.library.page_first_gateway import E2EIsolationError
            from globalVar import CONTENT_MANAGER_E2E_SCOPE, CONTENT_MANAGER_E2E_COLLECTION
            from unittest.mock import AsyncMock
            import pytest
            service = ManifestCleanupService(None, index_factory=lambda *args: (_ for _ in ()).throw(AssertionError('vector access forbidden')))
            service._load = AsyncMock(return_value={
                'scope_code':CONTENT_MANAGER_E2E_SCOPE,'collection_code':CONTENT_MANAGER_E2E_COLLECTION,
                'document_status':'test_candidate','generation_status':new['status'],
                'generation_retention_hold':new['retention_hold']})
            with pytest.raises(E2EIsolationError,match='ACTIVE generation'):
                await service.cleanup(uuid4(),1)
            assert await g.cleanup_protected_generations(conn,docs['OLD'])
            assert await g.cleanup_protected_generations(conn,docs['NEW'])
            save('positive-cutover-results.json',{'result':'PASS','switch':cutover,'old':old,'new':new,'initial_pointer':ids['OLD']})
            save('cleanup-protection-results.json',{'retained_old_cleanup':'REJECTED','active_cleanup':'REJECTED',
                'method':'real ManifestCleanupService guard with synthetic row metadata adapter; vector access forbidden; real protection query'})
            save('arbitrary-inactive-negative-control.json',await reject('ARBITRARY','NEW'))
            await g.set_retention_hold(conn,ids['NEVER'],hold=True)
            await conn.commit()
            save('never-active-negative-control.json',await reject('NEVER','NEW'))
            for name in ('BUILDING','FAILED'):
                save(name.lower()+'-negative-control.json',{'checks':[await reject(name,'NEW',op) for op in ('CUTOVER','ROLLBACK')]})
            save('cross-document-negative-control.json',{'checks':[await reject('CROSS','NEW',op) for op in ('CUTOVER','ROLLBACK')]})
            save('cross-operation-negative-control.json',{'checks':[await reject('B','NEW','ROLLBACK'),await reject('OLD','NEW','CUTOVER')]})
            save('stale-cas-negative-control.json',await reject('B','OLD','CUTOVER',g.GenerationConflictError))
            rollback = await switch('OLD','NEW','ROLLBACK')
            assert rollback['result']=='APPLIED'
            old = await g.get_generation(conn,ids['OLD']); new = await g.get_generation(conn,ids['NEW'])
            assert old['status']=='ACTIVE' and new['status']=='INACTIVE'
            save('positive-rollback-results.json',{'result':'PASS','switch':rollback,'old':old,'new':new,
                'reingest_calls':0,'extraction_calls':0,'embedding_calls':0,'vector_rebuild_calls':0,
                'basis':'Python call profiler around real rollback: only modules.library.generation functions allowed',
                'observed_library_calls':sorted(rollback_calls)})
            save('stale-rollback-negative-control.json',await reject('OLD','NEW','ROLLBACK',g.GenerationConflictError))
            before = await state()
            idem = await switch('OLD','OLD','ROLLBACK')
            assert idem['result']=='IDEMPOTENT' and await state()==before
            # Preserve documented CUTOVER retry semantics even for original expected-active.
            idem2 = await switch('OLD','NEW','CUTOVER')
            assert idem2['result']=='IDEMPOTENT' and await state()==before
            save('idempotency-results.json',{'result':'PASS','rollback':idem,'cutover':idem2,'duplicate_audit':False})
            audit = (await state())['audit']
            for origin,target,op in [('OLD','NEW','CUTOVER'),('NEW','OLD','ROLLBACK')]:
                matches=[a for a in audit if str(a['from_generation_id'])==ids[origin] and str(a['to_generation_id'])==ids[target]]
                assert len(matches)==1
                a=matches[0]
                assert a['operation']==op and a['result']=='APPLIED' and str(a['expected_generation_id'])==ids[origin]
            save('audit-results.json',{'result':'PASS','operations_distinguishable':True,'rows':audit})
            await switch('G1','OLD'); await switch('G2','G1')
            historical = await reject('OLD','G2')
            eligible = await switch('G1','G2','ROLLBACK')
            save('non-immediate-history-negative-control.json',{'result':'PASS','historical':historical,'immediate':eligible})
            if MODE=='preflight':
                save('preflight-positive-flow.json',{'certifying':False,'cutover':'operational','rollback':'operational','fixture':identifiers})
                save('preflight-negative-fixtures.json',{'certifying':False,'constructible':list(ids),'negative_controls_operational':True})
            save('atomicity-results.json',{'result':'PASS','method':'independent READ COMMITTED observer before/after every switch commit; unique ACTIVE schema constraint','observations':atomicity})
        finally:
            await conn.rollback()
            # Exact-ID fixture teardown only, not generic cleanup; retained synthetic rows intentionally dismantled.
            # Audit is retained by schema design (no FK); never delete audit.
            await g.execute(conn,'DELETE FROM library_logical_document_active_generations WHERE logical_document_id IN (%(a)s,%(b)s)',{'a':logical,'b':cross_logical})
            await g.execute(conn,'DELETE FROM library_document_generations WHERE logical_document_id IN (%(a)s,%(b)s)',{'a':logical,'b':cross_logical})
            for document in docs.values():
                await g.execute(conn,'DELETE FROM library_documents WHERE id=%(id)s AND collection_id=%(collection)s',{'id':document,'collection':collection})
            await g.execute(conn,'DELETE FROM library_logical_documents WHERE id IN (%(a)s,%(b)s)',{'a':logical,'b':cross_logical})
            await g.execute(conn,'DELETE FROM library_collections_legacy WHERE id=%(id)s',{'id':collection})
            await conn.commit()
            remaining={}
            for table,col,values in [('library_logical_documents','id',[logical,cross_logical]),
                                     ('library_document_generations','logical_document_id',[logical,cross_logical]),
                                     ('library_documents','collection_id',[collection])]:
                count=0
                for value in values:
                    row=await g.fetch_one(conn,f'SELECT count(*) AS n FROM {table} WHERE {col}=%(id)s',{'id':value})
                    count+=row['n']
                remaining[table]=count
            assert not any(remaining.values())
            save('cleanup.json' if MODE=='preflight' else 'certification-cleanup.json',{'result':'PASS','remaining':remaining,'audit_retained':True,'fixture':identifiers})
            after_c=await current_c(observer)
            assert before_c==after_c
            save('current-c-readonly-check.json',{'result':'PASS','document_id':C,'logical_document_id':CL,
                'before':before_c,'after':after_c,'postgresql_writes_by_gate':0,'milvus_writes_by_gate':0,
                'pointer_modified':False,'reingest':False,'extraction':False,'embedding_generation':False,'vector_rebuild':False})
    print(MODE+' lifecycle PASS '+tag)

asyncio.run(run())
