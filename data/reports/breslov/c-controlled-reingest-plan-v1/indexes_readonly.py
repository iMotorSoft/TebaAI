"""Read-only PostgreSQL index/constraint probe for the C reingest plan gate.

Usage (from SrvRestAstroLS_v1/backend):
    .venv/bin/python ../../data/reports/breslov/c-controlled-reingest-plan-v1/indexes_readonly.py

SELECT-only, server-enforced read-only transaction. No DDL, no DML, no locks.
Purpose: prove which live uniqueness constraints block a parallel same-source
document and which indexes support reconciliation queries.
"""
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'SrvRestAstroLS_v1/backend'))
import globalVar as g
from psycopg import AsyncConnection
from psycopg.rows import dict_row

OUT = Path(__file__).parent
TABLES = (
    'library_documents',
    'library_document_chunks',
    'library_document_texts',
    'library_pages_v2',
    'library_ingestion_runs_v2',
    'library_chunk_embeddings',
    'content_manager_jobs',
    'content_manager_ingestion_manifests',
    'content_manager_manifest_resources',
    'content_manager_job_attempts',
    'content_manager_uploads',
)


async def main() -> None:
    assert g.TEBAAI_ENV == 'development' and not g.is_tebaai_production()
    assert g.POSTGRES_HOST in {'127.0.0.1', 'localhost'} and g.POSTGRES_DB == 'tebaai'
    payload = {'captured_at': datetime.now(timezone.utc).isoformat(), 'queries': []}

    async def select(sql, params=None):
        assert sql.lstrip().upper().startswith('SELECT ')
        payload['queries'].append({'sql': sql, 'params': params})
        return await (await conn.execute(sql, params)).fetchall()

    async with await AsyncConnection.connect(
        g.POSTGRES_DSN,
        row_factory=dict_row,
        connect_timeout=5,
        options='-c default_transaction_read_only=on -c statement_timeout=20000',
    ) as conn:
        await conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        payload['indexes'] = await select(
            "SELECT tablename, indexname, indexdef FROM pg_indexes "
            "WHERE schemaname='public' AND tablename = ANY(%s) ORDER BY tablename, indexname",
            (list(TABLES),),
        )
        payload['unique_indexes'] = await select(
            "SELECT tablename, indexname, indexdef FROM pg_indexes "
            "WHERE schemaname='public' AND tablename = ANY(%s) "
            "AND indexdef LIKE 'CREATE UNIQUE%%' ORDER BY tablename, indexname",
            (list(TABLES),),
        )
        payload['check_constraints'] = await select(
            "SELECT conrelid::regclass::text AS table_name, conname, "
            "pg_get_constraintdef(oid) AS definition "
            "FROM pg_constraint WHERE conrelid::regclass::text = ANY(%s) "
            "AND contype IN ('c','u') ORDER BY 1,2",
            (list(TABLES),),
        )
        payload['c_document_indexes_on_sha'] = await select(
            "SELECT indexname, indexdef FROM pg_indexes "
            "WHERE schemaname='public' AND tablename='library_documents' "
            "AND indexdef LIKE '%source_sha256%' ORDER BY indexname"
        )
        payload['document_status_counts'] = await select(
            "SELECT status, count(*) AS documents FROM library_documents GROUP BY status ORDER BY status"
        )
        payload['chunk_orphan_check'] = await select(
            "SELECT count(*) AS chunks_without_document FROM library_document_chunks c "
            "LEFT JOIN library_documents d ON d.id=c.document_id WHERE d.id IS NULL"
        )
        payload['page_orphan_check'] = await select(
            "SELECT count(*) AS pages_without_run FROM library_pages_v2 p "
            "LEFT JOIN library_ingestion_runs_v2 r ON r.run_id=p.run_id WHERE r.run_id IS NULL"
        )
        await conn.rollback()
    (OUT / 'indexes-readonly.json').write_text(
        json.dumps(payload, indent=2, default=str, ensure_ascii=False) + '\n'
    )
    print('INDEXES_READONLY_OK', len(payload['indexes']), 'indexes',
          len(payload['unique_indexes']), 'unique')


if __name__ == '__main__':
    asyncio.run(main())
