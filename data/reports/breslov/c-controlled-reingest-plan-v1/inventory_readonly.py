"""Local DEV read-only evidence. No application lifecycle or worker imports.
Run: cd SrvRestAstroLS_v1/backend && .venv/bin/python ../../data/reports/breslov/c-controlled-reingest-plan-v1/inventory_readonly.py before
Only SELECT/SET TRANSACTION are permitted; server default_transaction_read_only
is set at connection establishment. Milvus calls are metadata/query only.
"""
import asyncio
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'SrvRestAstroLS_v1/backend'))
import globalVar as g
from psycopg import AsyncConnection
from psycopg.rows import dict_row
from pymilvus import MilvusClient

OUT = Path(__file__).parent
APPROVED_SHA = '440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, default=str, ensure_ascii=False) + '\n')


async def inventory(label):
    assert label in {'before', 'after'}
    assert g.TEBAAI_ENV == 'development' and not g.is_tebaai_production()
    assert g.POSTGRES_HOST in {'127.0.0.1', 'localhost'} and g.POSTGRES_DB == 'tebaai'
    assert g.MILVUS_HOST in {'127.0.0.1', 'localhost'} and not g.MILVUS_URI
    queries = []
    async with await AsyncConnection.connect(g.POSTGRES_DSN, row_factory=dict_row,
        connect_timeout=5, options='-c default_transaction_read_only=on -c statement_timeout=20000') as conn:
        await conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        async def select(sql, params=None):
            assert sql.lstrip().upper().startswith('SELECT ')
            queries.append({'sql': sql, 'params': params})
            return await (await conn.execute(sql, params)).fetchall()
        identity = await select("SELECT current_database() AS database, current_setting('transaction_read_only') AS read_only, current_setting('transaction_isolation') AS isolation, version() AS version")
        docs = await select('SELECT id,title,status,source_filename,source_path,source_uri,source_sha256,source_size_bytes,version_label,chunk_set_version,organization_id,workspace_id,project_id,knowledge_scope_id,collection_id,document_code,metadata,bibliographic_metadata,created_at,updated_at,archived_at FROM library_documents ORDER BY id')
        matched = [d for d in docs if d['source_sha256'] == APPROVED_SHA]
        assert len(matched) == 1, 'C source identity ambiguous'
        doc = matched[0]
        did = str(doc['id'])
        pg = {'captured_at': datetime.now(timezone.utc).isoformat(), 'identity': identity,
              'documents': docs, 'selected_document_id': did}
        statements = {
            'scopes': ('SELECT id,knowledge_scope_code,organization_id,workspace_id,status FROM knowledge_scopes ORDER BY id', None),
            'runs': ('SELECT * FROM library_ingestion_runs_v2 WHERE document_id=%s ORDER BY created_at,run_id', (did,)),
            'pages': ('SELECT page_id,run_id,document_id,page_number,char_count,extraction_method,confidence,layout_notes,md5(text) AS text_md5 FROM library_pages_v2 WHERE document_id=%s ORDER BY run_id,page_number', (did,)),
            'chunks': ('SELECT id,document_id,document_text_id,chunk_uid,chunk_index,content_sha256,content_length,page_start,page_end,chunk_set_version,metadata,bibliographic_metadata,reference_label,citable,created_at FROM library_document_chunks WHERE document_id=%s ORDER BY id', (did,)),
            'texts': ('SELECT id,document_id,content_sha256,content_length,page_count,text_format,text_role,extraction_method,extraction_metadata,created_at FROM library_document_texts WHERE document_id=%s ORDER BY created_at', (did,)),
            'embeddings': ('SELECT e.* FROM library_chunk_embeddings e JOIN library_document_chunks c ON c.id=e.chunk_id WHERE c.document_id=%s ORDER BY e.id', (did,)),
            'embedding_runs': ('SELECT * FROM library_embedding_runs ORDER BY started_at,id', None),
            'jobs': ('SELECT id,upload_id,document_id,title,status,current_stage,attempt_number,requested_status,created_at,started_at,finished_at,cleanup_status,collection_code,pipeline_version,diagnostic,technical_details FROM content_manager_jobs ORDER BY created_at,id', None),
            'attempts': ('SELECT id,job_id,attempt_number,status,started_at,finished_at,cleanup_status,recovery_action,failure_stage,error_code FROM content_manager_job_attempts ORDER BY started_at,id', None),
            'manifests': ('SELECT * FROM content_manager_ingestion_manifests ORDER BY started_at,id', None),
            'resources': ('SELECT * FROM content_manager_manifest_resources ORDER BY manifest_id,resource_type,resource_id', None),
            'uploads': ('SELECT id,filename,original_filename,sha256,page_count,temp_path,existing_document_id,cleanup_status,created_at FROM content_manager_uploads ORDER BY created_at,id', None),
            'orphan_chunks': ('SELECT c.id,c.document_id FROM library_document_chunks c LEFT JOIN library_documents d ON d.id=c.document_id WHERE d.id IS NULL', None),
            'orphan_pages': ('SELECT p.page_id,p.document_id,p.run_id FROM library_pages_v2 p LEFT JOIN library_documents d ON d.id=p.document_id LEFT JOIN library_ingestion_runs_v2 r ON r.run_id=p.run_id WHERE d.id IS NULL OR r.run_id IS NULL', None),
            'constraints': ("SELECT conrelid::regclass::text AS table_name,conname,pg_get_constraintdef(oid) AS definition FROM pg_constraint WHERE conrelid IN ('library_documents'::regclass,'library_document_chunks'::regclass,'library_pages_v2'::regclass) ORDER BY 1,2", None),
            'content_hashes': ("SELECT table_name, count(*) AS rows, md5(string_agg(row_hash, '' ORDER BY row_hash)) AS digest FROM (SELECT 'documents' AS table_name,md5(to_jsonb(d)::text) AS row_hash FROM library_documents d UNION ALL SELECT 'chunks',md5(to_jsonb(c)::text) FROM library_document_chunks c UNION ALL SELECT 'pages',md5(to_jsonb(p)::text) FROM library_pages_v2 p UNION ALL SELECT 'jobs',md5(to_jsonb(j)::text) FROM content_manager_jobs j UNION ALL SELECT 'embeddings',md5(to_jsonb(e)::text) FROM library_chunk_embeddings e UNION ALL SELECT 'runs',md5(to_jsonb(r)::text) FROM library_ingestion_runs_v2 r) s GROUP BY table_name ORDER BY table_name", None),
        }
        for name, (sql, params) in statements.items():
            pg[name] = await select(sql, params)
        await conn.rollback()
    save(f'postgres-{label}.json', pg)
    save(f'queries-{label}.json', queries)
    client = MilvusClient(uri=f'http://{g.MILVUS_HOST}:{g.MILVUS_PORT}')
    mv = {'captured_at': datetime.now(timezone.utc).isoformat(), 'collections': {}, 'methods': ['list_collections', 'describe_collection', 'get_load_state', 'get_collection_stats', 'query_iterator', 'close']}
    try:
        for name in sorted(client.list_collections(timeout=10)):
            if not name.startswith('tebaai_'):
                continue
            schema = client.describe_collection(name, timeout=10)
            state = str(client.get_load_state(name, timeout=10)['state'])
            fields = [f['name'] for f in schema['fields'] if f['name'] != 'embedding']
            info = {'schema': schema, 'load_state': state, 'stats': client.get_collection_stats(name, timeout=10)}
            if state.endswith('Loaded'):
                rows = []
                it = client.query_iterator(collection_name=name, filter='', batch_size=500,
                    output_fields=['*'], consistency_level='Strong', timeout=30)
                try:
                    while batch := it.next():
                        for r in batch:
                            r = dict(r)
                            # Capture vector bytes by digest, not report thousands of floats.
                            for key in list(r):
                                if isinstance(r[key], (list, tuple)) and len(r[key]) > 100:
                                    v = r.pop(key)
                                    r[key + '_sha256'] = digest(v)
                                    r[key + '_dimension'] = len(v)
                            r.pop('content_preview', None)
                            rows.append(r)
                finally:
                    it.close()
                rows.sort(key=lambda r: str(r.get('pk', r.get('id'))))
                info.update(records=rows, live_count=len(rows), records_sha256=digest(rows),
                            document_distribution=dict(Counter(str(r.get('document_id')) for r in rows)))
            else:
                info['live_inventory'] = 'NOT_QUERIED_UNLOADED_NO_LOAD_OR_FLUSH_ALLOWED'
            mv['collections'][name] = info
    finally:
        client.close()
    save(f'milvus-{label}.json', mv)
    source = {'document_id': did, 'approved_sha256': APPROVED_SHA, 'references': []}
    # External source identified by the approved source-books manifest, not filename alone.
    manifest = json.loads((ROOT / 'data/reports/breslov/2026-10-01-clean-corpus-hebrew-ingestion-v1/source-books.json').read_text())
    paths = {doc['source_path'], str(Path(g.CONTENT_MANAGER_STORAGE_DIR).resolve() / 'sources' / did / 'original.pdf')}
    paths.update(r['source_path'] for r in manifest if r['label'] == 'C' and r['sha256'] == APPROVED_SHA)
    paths.update(u['temp_path'] for u in pg['uploads'] if u['sha256'] == APPROVED_SHA)
    for path in sorted(p for p in paths if p):
        p = Path(path)
        info = {'path': path, 'exists': p.is_file()}
        if p.is_file():
            info.update(size_bytes=p.stat().st_size, sha256=hashlib.sha256(p.read_bytes()).hexdigest())
            import pymupdf
            with pymupdf.open(p) as pdf:
                info['pages'] = len(pdf)
        source['references'].append(info)
    save(f'source-{label}.json', source)
    print('READ_ONLY_INVENTORY_OK', label, did, len(pg['chunks']), len(pg['runs']))


if __name__ == '__main__':
    asyncio.run(inventory(sys.argv[1]))
