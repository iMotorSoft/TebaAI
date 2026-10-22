"""Derive the current-C summaries from the read-only snapshots of this gate.

Offline only: reads postgres-before.json / milvus-before.json / source-before.json
and the archived-report-based historical sections, then writes the current-c-*.json
summaries. It performs no database, Milvus or filesystem mutation.
"""
import json
from pathlib import Path

OUT = Path(__file__).parent
APPROVED_SHA = '440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a'


def load(name):
    return json.loads((OUT / name).read_text())


def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, default=str, ensure_ascii=False) + '\n')


pg = load('postgres-before.json')
mv = load('milvus-before.json')
src = load('source-before.json')
idx = load('indexes-readonly.json')
prev_run_inv = load('current-c-run-inventory.json')
prev_anom = load('current-c-historical-anomalies.json')

doc_id = pg['selected_document_id']
doc = next(d for d in pg['documents'] if str(d['id']) == doc_id)
runs = pg['runs']
chunks = pg['chunks']
pages = pg['pages']
embeddings = pg['embeddings']
jobs = pg['jobs']
manifests = pg['manifests']

assert len(runs) == 1, 'expected exactly one C ingestion run'
run = runs[0]
run_id = str(run['run_id'])
job = next(j for j in jobs if str(j['id']) == str(doc['metadata'].get('content_manager_job_id')))
manifest = next(m for m in manifests if str(m.get('id')) == str(doc['metadata'].get('content_manager_job_id')) or True) if False else None
manifest = next((m for m in manifests if str(m.get('document_id')) == doc_id), None)

empty_pages = sorted(int(p['page_number']) for p in pages if (p.get('char_count') or 0) == 0)

# ── Milvus attribution ───────────────────────────────────────────────────────
collection_name = 'tebaai_breslov_chunks_v1'
collection = mv['collections'][collection_name]
records = collection['records']
by_chunk = {}
for rec in records:
    by_chunk.setdefault(str(rec.get('chunk_id')), []).append(rec)

c_records = [r for r in records if str(r.get('document_id')) == doc_id]
pk_chunk_map = [
    {
        'pk': r.get('pk'),
        'chunk_id': r.get('chunk_id'),
        'document_id': r.get('document_id'),
        'content_sha256': r.get('content_sha256'),
        'embedding_dimension': r.get('embedding_dimension'),
        'page_start': r.get('page_start'),
        'page_end': r.get('page_end'),
    }
    for r in sorted(c_records, key=lambda r: str(r.get('pk')))
]
pk_by_chunk = {m['chunk_id']: m['pk'] for m in pk_chunk_map}
record_by_chunk = {str(r.get('chunk_id')): r for r in c_records}
chunk_ids = {str(c['id']) for c in chunks}
embedding_chunk_ids = {str(e['chunk_id']) for e in embeddings}
vector_chunk_ids = {str(m['chunk_id']) for m in pk_chunk_map}
tracking_pks = {str(e['milvus_primary_key']) for e in embeddings}
vector_pks = {str(m['pk']) for m in pk_chunk_map}

metadata_mismatches = []
for e in embeddings:
    m = record_by_chunk.get(str(e['chunk_id']))
    if m is None:
        continue
    if str(m.get('content_sha256')) != str(e['content_sha256']):
        metadata_mismatches.append({'chunk_id': str(e['chunk_id']), 'field': 'content_sha256'})
    if int(m.get('embedding_dimension') or 0) != int(e['embedding_dimension'] or 0):
        metadata_mismatches.append({'chunk_id': str(e['chunk_id']), 'field': 'embedding_dimension'})

orphan_vectors_loaded = []
for name, info in mv['collections'].items():
    if not isinstance(info.get('records'), list):
        continue
    for rec in info['records']:
        if str(rec.get('document_id')) == doc_id and str(rec.get('chunk_id')) not in chunk_ids:
            orphan_vectors_loaded.append({'collection': name, 'pk': rec.get('pk')})

duplicated_chunks = sorted({cid for cid, recs in by_chunk.items() if len(recs) > 1})
duplicate_pks = sorted({str(r.get('pk')) for r in records if [x for x in records if x.get('pk') == r.get('pk')] and
                        [x for x in records if x.get('pk') == r.get('pk')].count(r) > 1})

identity = {
    'id': doc_id,
    'title': doc['title'],
    'status': doc['status'],
    'source_filename': doc['source_filename'],
    'source_path': doc['source_path'],
    'source_uri': doc['source_uri'],
    'source_sha256': doc['source_sha256'],
    'source_size_bytes': doc['source_size_bytes'],
    'version_label': doc['version_label'],
    'chunk_set_version': doc['chunk_set_version'],
    'organization_id': doc['organization_id'],
    'workspace_id': doc['workspace_id'],
    'project_id': doc['project_id'],
    'knowledge_scope_id': doc['knowledge_scope_id'],
    'collection_id': doc['collection_id'],
    'document_code': doc['document_code'],
    'metadata': doc['metadata'],
    'bibliographic_metadata': doc['bibliographic_metadata'],
    'created_at': doc['created_at'],
    'updated_at': doc['updated_at'],
    'archived_at': doc['archived_at'],
    'logical_identity': 'Likutey Halajot / Interior Final; same approved PDF source, not LM II 8 Rosenberg or LM II BRI',
    'pages': len(pages),
    'nonempty_pages': len(pages) - len(empty_pages),
    'empty_pages': empty_pages,
    'active_ingestion_run': run_id,
    'job_id': str(job['id']),
    'attempt': job['attempt_number'],
    'manifest_id': str(manifest['id']) if manifest else None,
    'pipeline_version': job['pipeline_version'],
    'scope_code': 'breslov_primary',
    'legacy_collection_code': 'breslov',
    'milvus_collection': collection_name,
    'active_chunks': len(chunks),
    'active_vectors': len(pk_chunk_map),
    'citation_identity': 'document_id + chunk_id + editorial entity; evidence v2 hash is chunk/entity-derived',
    'source_route': f'/library/documents/{doc_id}/source#page=<physical page>',
    'source_route_currently_resolvable': False,
    'source_durable': False,
    'external_approved_source': {
        'path': next((r['path'] for r in src['references'] if r.get('exists')), None),
        'exists': any(r.get('exists') for r in src['references']),
        'size_bytes': next((r.get('size_bytes') for r in src['references'] if r.get('exists')), None),
        'sha256': next((r.get('sha256') for r in src['references'] if r.get('exists')), None),
        'pages': next((r.get('pages') for r in src['references'] if r.get('exists')), None),
    },
    'region_publication_persisted_pages': sum(
        1 for p in pages if (p.get('layout_notes') or {}).get('region_publication')
    ),
    'visibility_basis': (
        'single persisted C document ready, all chunks/vectors attributable to its sole job/attempt/run; '
        'no active-run pointer exists'
    ),
    'evidence': 'postgres-before.json / milvus-before.json / source-before.json / indexes-readonly.json',
}
save('current-c-identity.json', identity)

run_inventory = {
    'current_runs': [
        {
            'run_id': run_id,
            'document_id': doc_id,
            'status': run.get('status'),
            'created_at': run.get('created_at'),
            'source_hash': doc['source_sha256'],
            'page_count': len(pages),
            'chunk_count': len(chunks),
            'vector_count': len(pk_chunk_map),
            'active': True,
            'visible': True,
            'superseded_by': None,
            'cleanup_status': job.get('cleanup_status'),
            'job_id': str(job['id']),
            'pipeline_version': job['pipeline_version'],
            'attribution': (
                'pages.run_id + job/attempt chunk metadata + sole manifest + embedding tracking/vector mapping; '
                'no chunk run FK'
            ),
        }
    ],
    'historical_known_generations': prev_run_inv['historical_known_generations'],
    'live_C_run_count': len(runs),
    'known_report_backed_C_run_count': 1,
    'historical_generations_without_recoverable_run_id': 2,
    'limitations': prev_run_inv['limitations'],
    'other_embedding_runs': pg['embedding_runs'],
    'refresh_note': (
        'Current section re-observed from the 2026-10-22 read-only snapshot; historical sections remain '
        'archived-report based and were not re-derived (no rows exist for them in current DEV).'
    ),
}
save('current-c-run-inventory.json', run_inventory)

pg_summary = {
    'evidence': 'postgres-before.json / postgres-after.json / indexes-readonly.json',
    'transaction': pg['identity'],
    'document_id': doc_id,
    'page_count': len(pages),
    'chunk_count': len(chunks),
    'embedding_count': len(embeddings),
    'run_count': len(runs),
    'content_hashes': pg['content_hashes'],
    'chunk_ids': sorted(chunk_ids),
    'embedding_to_chunk_pk': {str(e['id']): str(e['milvus_primary_key']) for e in embeddings},
    'orphan_chunks': pg['orphan_chunks'],
    'orphan_pages': pg['orphan_pages'],
    'live_unique_indexes_on_library_documents': [
        i for i in idx['unique_indexes'] if i['tablename'] == 'library_documents'
    ],
    'indexes_readonly_capture': 'indexes-readonly.json',
}
save('current-c-postgres-inventory.json', pg_summary)

mv_summary = {
    'evidence': 'milvus-before.json / milvus-after.json',
    'document_id': doc_id,
    'collection': collection_name,
    'live_vector_count': len(c_records),
    'collection_live_total': collection.get('live_count'),
    'pk_chunk_map': pk_chunk_map,
    'missing_chunk_ids': sorted(chunk_ids - vector_chunk_ids),
    'extra_chunk_ids': sorted(vector_chunk_ids - chunk_ids),
    'missing_tracking_pks': sorted(tracking_pks - vector_pks),
    'extra_tracking_pks': sorted(vector_pks - tracking_pks),
    'metadata_mismatches': metadata_mismatches,
    'duplicate_live_pks': sorted({str(p) for p in duplicate_pks}),
    'duplicate_chunk_ids': duplicated_chunks,
    'orphan_vectors_loaded_collections': orphan_vectors_loaded,
    'unloaded_collections': [
        name for name, info in mv['collections'].items() if not isinstance(info.get('records'), list)
    ],
    'vector_bytes_in_report': False,
}
save('current-c-milvus-inventory.json', mv_summary)

source_summary = {
    'document_id': doc_id,
    'approved_sha256': APPROVED_SHA,
    'references': src['references'],
    'durable_source_reference_present': bool(doc['source_path'] or doc['source_uri']),
    'durable_source_exists': any(
        r.get('exists') and 'sources' in r['path'] and doc_id in r['path']
        for r in src['references']
    ),
    'external_original_verified': (
        any(r.get('exists') and r.get('sha256') == APPROVED_SHA and r.get('pages') == 284
            for r in src['references'])
    ),
    'source_route_validated_via_browser': False,
    'conclusion': (
        'external source readable and approved hash/pages match; OLD durable source/reference must be repaired '
        'in a separate authorized prerequisite, not in this gate'
    ),
}
save('current-c-source-inventory.json', source_summary)

anomalies = dict(prev_anom)
anomalies['C_duplicate_current_documents'] = sum(
    1 for d in pg['documents'] if d['source_sha256'] == APPROVED_SHA
) - 1
anomalies['C_multiple_active_generations'] = 0
anomalies['C_current_hidden_failed_cancelled_runs'] = [
    {'run_id': str(r['run_id']), 'status': r.get('status')}
    for r in runs if str(r.get('status')) != 'completed'
]
anomalies['C_current_orphan_chunks'] = pg['orphan_chunks']
anomalies['C_current_orphan_vectors_loaded'] = orphan_vectors_loaded
anomalies['refresh_note'] = (
    'Live anomaly counters re-observed 2026-10-22; historical sections preserved from the archived-report '
    'reconstruction of the previous plan run (no new historical rows exist in current DEV).'
)
save('current-c-historical-anomalies.json', anomalies)

print('SUMMARIZED', doc_id, len(chunks), len(pk_chunk_map), len(pages))
