#!/usr/bin/env python3
"""Inventory by default. Apply only a current, hash-confirmed local DEV manifest."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import globalVar as g
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from pymilvus import MilvusClient
from infrastructure.postgres.dev_content_reset import (
    CONFIRMATION, CONTENT_TABLES, assert_preserved, delete_pg, digest,
    guard_config, guard_offline, pg_inventory, storage_inventory, vector_inventory,
)

REPO = Path(__file__).resolve().parents[3]


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        f.write('\n')


async def main(args):
    guard_config(g)
    guard_offline()
    if args.apply and args.confirm != CONFIRMATION:
        raise ValueError('Exact destructive confirmation required')
    if args.output.exists():
        raise ValueError('Output already exists; evidence will not be overwritten')
    expected = None
    if args.apply:
        raw = args.apply.read_bytes()
        if hashlib.sha256(raw).hexdigest() != args.manifest_sha256:
            raise ValueError('Manifest hash does not match')
        expected = json.loads(raw)
    conn = await psycopg.AsyncConnection.connect(g.POSTGRES_DSN, connect_timeout=5, row_factory=dict_row)
    client = MilvusClient(uri=f'http://{g.MILVUS_HOST}:{g.MILVUS_PORT}', timeout=20)
    try:
        async with conn:
            if args.apply:
                # Freeze the entire reviewed dataset before the last inventory.
                await conn.execute("SET LOCAL lock_timeout='5s'")
                await conn.execute(sql.SQL('LOCK TABLE {} IN ACCESS EXCLUSIVE MODE').format(
                    sql.SQL(',').join(sql.Identifier(t) for t in sorted(CONTENT_TABLES))))
            else:
                await conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            pg = await pg_inventory(conn)
            vectors = await asyncio.to_thread(vector_inventory, client, {str(r['id']) for r in pg['documents']})
            storage = storage_inventory(REPO, pg)
            current = {'version': 1, 'environment': g.ENV, 'postgres': pg, 'milvus': vectors, 'storage': storage}
            if not args.apply:
                save(args.output, current)
                print('Manifest:', args.output, 'SHA256:', hashlib.sha256(args.output.read_bytes()).hexdigest())
                print('Documents:', pg['tables']['library_documents']['count'], 'Pages:', pg['tables']['library_pages_v2']['count'], 'Chunks:', pg['tables']['library_document_chunks']['count'])
                return
            if digest(current) != digest(expected):
                raise ValueError('Live inventory differs from authorized manifest; regenerate before apply')
            guard_offline()
            journal = args.output.with_suffix('.journal.json')
            save(journal, {'phase': 'milvus_first_started', 'manifest_sha256': args.manifest_sha256})
            # Exact PK deletion includes historical/unowned vectors, not only current documents.
            for name, item in vectors['collections'].items():
                for start in range(0, len(item['ids']), 500):
                    await asyncio.to_thread(client.delete, collection_name=name,
                                            ids=item['ids'][start:start + 500], timeout=30)
                await asyncio.to_thread(client.flush, collection_name=name, timeout=30)
            zero_vectors = await asyncio.to_thread(vector_inventory, client, set())
            if any(r['live_count'] for r in zero_vectors['collections'].values()):
                raise ValueError('Milvus did not reach zero; PostgreSQL deletion refused')
            if vectors['all_collection_names'] != zero_vectors['all_collection_names'] or any(
                r['schema_sha256'] != zero_vectors['collections'][n]['schema_sha256']
                for n, r in vectors['collections'].items()):
                raise ValueError('Milvus structure changed; PostgreSQL deletion refused')
            zero_pg = await delete_pg(conn, pg)
            # File hashes were confirmed above. Never remove directories/schema/code.
            for item in storage['files']:
                p = Path(item['path'])
                if p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest() != item['sha256']:
                    raise ValueError('Storage file changed; PG transaction will roll back')
                p.unlink()
            zero_storage = storage_inventory(REPO, zero_pg)
            if zero_storage['files']:
                raise ValueError('Managed storage did not reach zero')
            assert_preserved(pg, zero_pg)
        # Context exit has committed PostgreSQL. Report only after commit succeeded.
        save(args.output, {'gate': 'CORPUS_ZERO_DATA_VERIFIED', 'auth_works': 'NOT_YET_VALIDATED',
                          'manifest_sha256': args.manifest_sha256, 'postgres': zero_pg,
                          'milvus': zero_vectors, 'storage': zero_storage, 'production_modified': False})
        print('CORPUS_ZERO_DATA_VERIFIED; authentication still requires UI verification')
    finally:
        client.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--apply', type=Path)
    p.add_argument('--manifest-sha256')
    p.add_argument('--confirm')
    a = p.parse_args()
    try:
        asyncio.run(main(a))
    except Exception as exc:
        # Never emit credentials from connection exceptions.
        reason = str(exc) if isinstance(exc, ValueError) else 'inspect safely before retry'
        print(f'RESET FAILED CLOSED: {type(exc).__name__}; {reason}', file=sys.stderr)
        raise SystemExit(1)
