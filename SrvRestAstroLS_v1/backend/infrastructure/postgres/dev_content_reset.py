"""Explicit local DEV content reset; no DDL and no platform-row mutations.

Run the scripts/dev_content_reset.py entrypoint while application/worker writers
are stopped. Inventory is the default. Apply requires an unchanged manifest and
its SHA-256. Milvus-first compensating strategy: on failure PG is rolled back;
a partial vector deletion is reported and an inventory must be regenerated.
"""
from __future__ import annotations

import hashlib
import json
import socket
from collections import Counter
from pathlib import Path

from psycopg import sql

# Exhaustive, reviewed allowlist: never infer deletion from a table prefix.
CONTENT_TABLES = frozenset("""
content_manager_cleanup_events content_manager_ingestion_manifests
content_manager_job_attempts content_manager_job_transitions content_manager_jobs
content_manager_manifest_resources content_manager_uploads
library_ai_zone_candidates_v2 library_chunk_embeddings library_concept_mentions_v2
library_content_nodes_v2 library_content_relations_v2 library_content_units_v2
library_document_chunks library_document_references library_document_texts
library_document_wiki_v2 library_documents library_embedding_runs library_ingestion_runs_v2
library_internal_relations_v2 library_la_potencia_plegaria_fine_zones_v1
library_la_potencia_plegaria_nominal_reference_resolution_v1
library_la_potencia_plegaria_nominal_references_v1
library_la_potencia_plegaria_note_source_units_v1 library_la_potencia_plegaria_page_blocks_v1
library_la_potencia_plegaria_pages_v1 library_la_potencia_plegaria_structural_classifications_v1
library_likutey_halajot_fine_zones_v1 library_likutey_halajot_nominal_reference_resolution_v1
library_likutey_halajot_nominal_references_v1 library_likutey_halajot_note_source_units_v1
library_literal_spans_v2 library_lm_xv_kdp_block_roles_v1 library_lm_xv_kdp_fine_zones_v1
library_lm_xv_kdp_page_blocks_v1 library_lm_xv_kdp_pages_v1
library_lm_xv_kdp_structural_classifications_v1 library_page_anchors_v2
library_page_structural_classifications_v2 library_pages_v2 library_promotion_events
library_sections_v2 library_semantic_units_v2 library_source_references_v2
library_validation_runs library_vector_embeddings_v2_dev
""".split())
PRESERVED_TABLES = frozenset("""
auth_identities auth_sessions knowledge_scopes library_collections_legacy
library_multilingual_terms_v2 organization_members organizations project_members
projects schema_migrations users workspace_members workspaces
""".split())
VECTOR_COLLECTIONS = frozenset("""
tebaai_breslov_chunks_v1 tebaai_content_manager_e2e_v1 tebaai_breslov_chunks_v2_dev
tebaai_breslov_test_chunks_v1 tebaai_breslov_bookqa_v2_kitzur_test_pages_v1
tebaai_breslov_bm25_test_v2 tebaai_breslov_bm25_test_v3
""".split())
CONFIRMATION = "DELETE_ALL_TEBAAI_LOCAL_DEV_DOCUMENT_CONTENT"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


def guard_config(g):
    if (g.ENV != "development" or g.is_tebaai_production()
        or g.POSTGRES_HOST not in {"localhost", "127.0.0.1"}
        or g.POSTGRES_DB != "tebaai" or g.POSTGRES_PORT != 5432
        or g.MILVUS_HOST not in {"localhost", "127.0.0.1"}
        or g.MILVUS_PORT != 19530 or g.MILVUS_URI):
        raise ValueError("Reset requires exact local DEV PostgreSQL/Milvus configuration")


def guard_offline():
    for port in (7008, 3008):
        with socket.socket() as sock:
            sock.settimeout(1)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                raise ValueError("Stop DEV application writers before reset")
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            args = (proc / 'cmdline').read_bytes().split(b'\0')
        except (OSError, PermissionError):
            continue
        if any(b'content_manager_worker' in arg for arg in args):
            raise ValueError("A content-manager worker is running")


def deletion_order(tables, edges):
    pending = set(tables)
    if any(c not in pending and p in pending for c, p in edges):
        raise ValueError("A preserved table references content; reset refused")
    result = []
    while pending:
        leaves = sorted(t for t in pending if not any(c != p and p == t and c in pending for c, p in edges))
        if not leaves:
            raise ValueError("Cyclic content FK graph; reset refused")
        result.extend(leaves)
        pending.difference_update(leaves)
    return result


async def pg_inventory(conn):
    tables = [r['tablename'] for r in await (await conn.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")).fetchall()]
    if set(tables) != CONTENT_TABLES | PRESERVED_TABLES:
        raise ValueError("Database table inventory changed; review explicit allowlists")
    edges = await (await conn.execute("""SELECT conrelid::regclass::text child,
        confrelid::regclass::text parent,pg_get_constraintdef(oid) definition
        FROM pg_constraint WHERE contype='f' AND connamespace='public'::regnamespace ORDER BY 1,2,3""")).fetchall()
    order = deletion_order(CONTENT_TABLES, [(r['child'], r['parent']) for r in edges])
    rows = {}
    for table in tables:
        # Hash rows without exposing identities, passwords or sessions in evidence.
        hashes = await (await conn.execute(sql.SQL(
            "SELECT md5(to_jsonb(t)::text) hash FROM {} t ORDER BY 1").format(sql.Identifier(table)))).fetchall()
        rows[table] = {'count': len(hashes), 'sha256': digest(hashes),
                       'action': 'DELETE' if table in CONTENT_TABLES else 'PRESERVE'}
    columns = await (await conn.execute("""SELECT table_name,column_name,data_type,column_default,is_nullable
        FROM information_schema.columns WHERE table_schema='public' ORDER BY table_name,ordinal_position""")).fetchall()
    indexes = await (await conn.execute("SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='public' ORDER BY 1,2")).fetchall()
    views = await (await conn.execute("SELECT viewname,definition FROM pg_views WHERE schemaname='public' ORDER BY 1")).fetchall()
    functions = await (await conn.execute("""SELECT p.oid::regprocedure::text name,pg_get_functiondef(p.oid) definition
        FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
        WHERE n.nspname='public' AND p.prokind IN ('f','p') ORDER BY 1""")).fetchall()
    identity = await (await conn.execute("""SELECT current_database() db,inet_server_addr()::text server,
        inet_server_port() port,system_identifier::text system_identifier
        FROM pg_control_system()""")).fetchone()
    documents = await (await conn.execute("SELECT id,title,status,source_path,source_filename,source_sha256 FROM library_documents ORDER BY id")).fetchall()
    statuses = {}
    for table in ('library_documents', 'content_manager_jobs', 'content_manager_job_attempts'):
        statuses[table] = await (await conn.execute(sql.SQL(
            "SELECT status,count(*) count FROM {} GROUP BY status ORDER BY status").format(sql.Identifier(table)))).fetchall()
    orphans = {}
    for table in ('library_pages_v2', 'library_document_chunks', 'content_manager_jobs'):
        orphans[table] = (await (await conn.execute(sql.SQL("""SELECT count(*) count FROM {} t
            LEFT JOIN library_documents d ON d.id=t.document_id WHERE d.id IS NULL""").format(sql.Identifier(table)))).fetchone())['count']
    uploads = await (await conn.execute("SELECT id,temp_path FROM content_manager_uploads ORDER BY id")).fetchall()
    return {'identity': identity, 'tables': rows, 'schema_sha256': digest([columns, edges, indexes, views, functions]),
            'foreign_keys': edges, 'delete_order': order, 'documents': documents,
            'statuses': statuses, 'orphans': orphans, 'uploads': uploads}


def vector_inventory(client, document_ids):
    names = sorted(client.list_collections(timeout=20))
    if {n for n in names if n.startswith('tebaai_')} != VECTOR_COLLECTIONS:
        raise ValueError("TebaAI vector collection inventory changed; review allowlist")
    result = {}
    for name in sorted(VECTOR_COLLECTIONS):
        schema = client.describe_collection(name, timeout=20)
        fields = schema['fields']
        pk = next(f['name'] for f in fields if f.get('is_primary'))
        selected = [f['name'] for f in fields if f['name'] in {pk, 'document_id', 'collection_code', 'knowledge_scope_code', 'chunk_id'}]
        was_loaded = str(client.get_load_state(name, timeout=20)['state']).endswith('Loaded')
        if not was_loaded:
            # A historical empty collection has no index and cannot be loaded.
            # Flush first: physical row_count == 0 proves no stored entities.
            # This is NOT used for nonzero stats (which include tombstones).
            client.flush(collection_name=name, timeout=30)
            stats = client.get_collection_stats(name, timeout=20)
            if int(stats['row_count']) != 0:
                raise ValueError("Nonempty unloaded collection: inventory refused")
            result[name] = {'schema_sha256': digest(schema), 'primary_key': pk,
                            'ids': [], 'records_sha256': digest([]), 'live_count': 0,
                            'stats': stats, 'proof': 'flushed_physical_entity_count_zero',
                            'scope_distribution': {}, 'document_distribution': {}, 'unowned': 0}
            continue
        records = []
        iterator = None
        try:
            iterator = client.query_iterator(collection_name=name, batch_size=500, filter='',
                                             output_fields=selected, consistency_level='Strong', timeout=30)
            while batch := iterator.next():
                records.extend(dict(r) for r in batch)
        finally:
            if iterator:
                iterator.close()
        records.sort(key=lambda r: str(r[pk]))
        ids = [r[pk] for r in records]
        result[name] = {'schema_sha256': digest(schema), 'primary_key': pk, 'ids': ids,
                        'records_sha256': digest(records), 'live_count': len(records),
                        'stats': client.get_collection_stats(name, timeout=20),
                        'scope_distribution': dict(Counter(str(r.get('knowledge_scope_code', r.get('collection_code', '<absent>'))) for r in records)),
                        'document_distribution': dict(Counter(str(r.get('document_id', '<absent>')) for r in records)),
                        'unowned': sum(not r.get('document_id') or str(r.get('document_id')) not in document_ids for r in records)}
    return {'all_collection_names': names, 'collections': result}


def storage_inventory(repo, pg):
    # External original PDFs and evidence are not runtime-managed content storage.
    # README and .gitkeep are platform documentation, not corpus.
    roots = [repo / 'data/processed', repo / 'data/source', Path('/tmp/tebaai_content_manager')]
    files = []
    for root in roots:
        if root.is_symlink():
            raise ValueError("Managed storage root is a symlink")
        if not root.exists():
            continue
        for p in sorted(root.rglob('*')):
            if p.is_symlink():
                raise ValueError("Symlink in managed storage")
            if p.is_file() and p.name not in {'README.md', '.gitkeep'}:
                files.append({'path': str(p), 'size': p.stat().st_size,
                              'sha256': hashlib.sha256(p.read_bytes()).hexdigest()})
    managed = {f['path'] for f in files}
    unexplained = [r['temp_path'] for r in pg['uploads'] if r['temp_path'] and Path(r['temp_path']).exists() and r['temp_path'] not in managed]
    if unexplained:
        raise ValueError("Existing upload outside reviewed storage roots")
    return {'roots': list(map(str, roots)), 'files': files,
            'external_source_paths_preserved': sorted({r['source_path'] for r in pg['documents'] if r['source_path'] and r['source_path'] not in managed})}


def assert_preserved(before, after):
    if before['identity'] != after['identity'] or before['schema_sha256'] != after['schema_sha256']:
        raise ValueError("Database identity/schema changed")
    if any(before['tables'][t] != after['tables'][t] for t in PRESERVED_TABLES):
        raise ValueError("Platform rows changed")


async def delete_pg(conn, before):
    for table in before['delete_order']:
        await conn.execute(sql.SQL('DELETE FROM {}').format(sql.Identifier(table)))
    after = await pg_inventory(conn)
    assert_preserved(before, after)
    if any(after['tables'][t]['count'] for t in CONTENT_TABLES):
        raise ValueError("Content did not reach zero")
    return after
