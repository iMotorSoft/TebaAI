"""Pre-freeze integration diagnosis: real gateway helper and real DEV constraints.

All synthetic database writes are rolled back. No extraction/ingestion/vector
write is performed. This is not the frozen Foundation certification harness.
Run from backend with uv run python <absolute path>.
"""
import asyncio
import hashlib
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row
from pymilvus import Collection
import globalVar as cfg
from infrastructure.milvus.client import create_connection, close_connection, list_collections
from modules.library.page_first_gateway import PostgresMilvusPageFirstGateway
from modules.library.durable_source import source_path, file_sha256

R = Path(__file__).resolve().parent
C = 'ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa'
L = 'db200a31-b547-5668-d968-06d0ec36ad95'


def save(name, value):
    (R / name).write_text(json.dumps(value, indent=2, default=str) + '\n')


async def snapshot(conn):
    result = {}
    for name, sql, params in [
        ('document', 'SELECT * FROM library_documents WHERE id=%s', (C,)),
        ('logical', 'SELECT * FROM library_logical_documents WHERE id=%s', (L,)),
        ('generations', 'SELECT * FROM library_document_generations WHERE logical_document_id=%s ORDER BY id', (L,)),
        ('pointer', 'SELECT * FROM library_logical_document_active_generations WHERE logical_document_id=%s', (L,)),
        ('chunks', 'SELECT id,content_sha256,md5(content) AS actual_digest FROM library_document_chunks WHERE document_id=%s ORDER BY id', (C,)),
        ('pages', 'SELECT page_id,run_id,md5(text) AS actual_digest FROM library_pages_v2 WHERE document_id=%s ORDER BY page_id', (C,)),
    ]:
        result[name] = await (await conn.execute(sql, params)).fetchall()
    result['chunk_count'] = len(result['chunks'])
    p = source_path(UUID(C))
    result['durable_source_exists'] = p.is_file()
    result['durable_source_sha256'] = file_sha256(p) if p.is_file() else None
    return result


async def main():
    assert cfg.TEBAAI_ENV == 'development' and not cfg.is_tebaai_production()
    assert cfg.POSTGRES_HOST in {'127.0.0.1', 'localhost'} and cfg.POSTGRES_DB == 'tebaai'
    async with await psycopg.AsyncConnection.connect(cfg.get_tebaai_db_url_psql(), row_factory=dict_row, connect_timeout=5) as conn:
        before = await snapshot(conn)
        await conn.rollback()
        schema = await (await conn.execute("""SELECT conname, condeferrable, condeferred,
            pg_get_constraintdef(oid) AS definition FROM pg_constraint
            WHERE conrelid='library_document_generations'::regclass AND contype='f'
            ORDER BY conname""")).fetchall()
        await conn.rollback()
        create_connection()
        try:
            collections = list_collections()
            col = Collection(cfg.MILVUS_COLLECTION_BRESLOV)
            rows = col.query(expr=f'document_id == "{C}"', output_fields=['pk','chunk_id','content_sha256'], timeout=15)
            before['vector_count'] = len(rows)
            before['vector_metadata_digest'] = hashlib.sha256(json.dumps(sorted(rows, key=lambda r:r['pk']), sort_keys=True).encode()).hexdigest()
            save('preflight-results.json', {'postgres': 'AVAILABLE', 'database': cfg.POSTGRES_DB,
                'milvus': 'AVAILABLE', 'collection_present': cfg.MILVUS_COLLECTION_BRESLOV in collections,
                'generation_constraints': schema, 'status': 'DIAGNOSIS_IN_PROGRESS',
                'initial_probe_correction': 'Direct empty MILVUS_URI was not a valid probe; canonical infrastructure client connected successfully.'})
            save('current-c-before.json', before)
            results = []
            synthetic_ids = []
            with tempfile.NamedTemporaryFile(suffix='.pdf') as source:
                source.write(b'synthetic registration metadata only; not extracted')
                source.flush()
                for label, seed_run, bind_document in [
                    ('production_order', False, False),
                    ('run_exists_but_document_not_bound', True, False),
                    ('control_both_prerequisites_exist', True, True),
                ]:
                    collection, doc, run, logical = [uuid4() for _ in range(4)]
                    synthetic_ids.append(str(doc))
                    outcome = {'case': label, 'seed_run': seed_run, 'document_logical_id_prebound': bind_document,
                               'expected_product_registration': 'SUCCESS', 'committed': False}
                    try:
                        tenant = await (await conn.execute("SELECT organization_id, workspace_id, project_id, id AS knowledge_scope_id FROM knowledge_scopes WHERE knowledge_scope_code='breslov_primary'")).fetchone()
                        job = await (await conn.execute('SELECT id FROM content_manager_jobs LIMIT 1')).fetchone()
                        assert tenant and job
                        await conn.execute("INSERT INTO library_collections_legacy(id,code,name,default_language,is_active) VALUES(%s,%s,'V1R1 rolled-back synthetic','es',true)", (collection, 'v1r1-' + str(collection)))
                        sha = hashlib.sha256(str(doc).encode()).hexdigest()
                        await conn.execute("""INSERT INTO library_documents(id,collection_id,title,language,source_type,
                            source_filename,source_sha256,status,knowledge_scope_id,organization_id,workspace_id,project_id)
                            VALUES(%s,%s,'V1R1 synthetic','es','pdf','synthetic.pdf',%s,'draft',%s,%s,%s,%s)""",
                            (doc,collection,sha,tenant['knowledge_scope_id'],tenant['organization_id'],tenant['workspace_id'],tenant['project_id']))
                        if seed_run:
                            await conn.execute("INSERT INTO library_ingestion_runs_v2(run_id,document_id,pipeline_version,scope_code,status) VALUES(%s,%s,'publication_v1r1_synthetic','breslov_primary','started')", (run,doc))
                        if bind_document:
                            await conn.execute("""INSERT INTO library_logical_documents(id,collection_id,knowledge_scope_id,title,source_sha256)
                                VALUES(%s,%s,%s,'V1R1 synthetic',%s)""", (logical,collection,tenant['knowledge_scope_id'],sha))
                            await conn.execute('UPDATE library_documents SET logical_document_id=%s WHERE id=%s', (logical,doc))
                        request = SimpleNamespace(tenant=SimpleNamespace(**tenant), title='V1R1 synthetic',
                            source_sha256=sha, source_path=Path(source.name), job_id=job['id'],
                            attempt_number=1, pipeline_version='publication_v1r1_synthetic')
                        async with conn.cursor() as cur:
                            await PostgresMilvusPageFirstGateway._register_generation(None, cur,
                                request=request,document_id=doc,run_id=run,collection_id=collection)
                        outcome['actual'] = 'SUCCESS'
                    except psycopg.Error as exc:
                        outcome.update(actual='DATABASE_REJECTED',error_type=type(exc).__name__,
                            sqlstate=exc.sqlstate,constraint=exc.diag.constraint_name)
                    finally:
                        await conn.rollback()
                    results.append(outcome)
            after = await snapshot(conn)
            rows = col.query(expr=f'document_id == "{C}"', output_fields=['pk','chunk_id','content_sha256'], timeout=15)
            after['vector_count'] = len(rows)
            after['vector_metadata_digest'] = hashlib.sha256(json.dumps(sorted(rows,key=lambda r:r['pk']), sort_keys=True).encode()).hexdigest()
            leftovers = await (await conn.execute('SELECT count(*) AS n FROM library_documents WHERE id=ANY(%s::uuid[])', (synthetic_ids,))).fetchone()
            await conn.rollback()
            save('current-c-after.json', after)
            save('current-c-regression-results.json', {'database_and_vector_snapshot_unchanged':before==after,
                'chunks_before':before['chunk_count'],'chunks_after':after['chunk_count'],
                'vectors_before':before['vector_count'],'vectors_after':after['vector_count'],
                'retrieval_viewer_citation_lifecycle': 'NOT_RUN_EARLY_STOP',
                'C_REINGEST_EXECUTED':False,'C_EXTRACTION_EXECUTED':False,
                'C_EMBEDDINGS_REGENERATED':False,'C_VECTORS_REBUILT':False})
            defect = (results[0]['actual']=='DATABASE_REJECTED' and results[1]['actual']=='DATABASE_REJECTED' and results[2]['actual']=='SUCCESS')
            save('gateway-registration-results.json', {'phase':'PREFLIGHT_BEFORE_FREEZE',
                'technical_defect_reproduced':defect,'cases':results,'schema_constraints':schema,
                'synthetic_leftover_documents':leftovers['n'],'all_synthetic_transactions_rolled_back':True,
                'current_c_snapshot_unchanged':before==after,
                'root_cause':'persist_document_and_pages calls _register_generation before creating run_id; _register_generation inserts a composite document/logical FK before binding the document logical_document_id.',
                'control_note':'Harness-only prerequisites in rolled-back transactions; product files unmodified.'})
            print(json.dumps({'defect_reproduced':defect,'cases':results,'synthetic_leftovers':leftovers['n'],'current_c_unchanged':before==after},indent=2))
        finally:
            close_connection()

asyncio.run(main())
